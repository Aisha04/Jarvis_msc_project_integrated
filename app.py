"""
JARVIS - animated dashboard window.

Run:  python app.py        (or press F5 in VS Code and pick "JARVIS (orb)")

Say "Hello Jarvis"   -> welcome + briefing; each dashboard flies in as it is spoken
Say "Jarvis, <question>" or click the orb / press Space and ask anything
Type in the box       -> same as speaking
"""
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import webview

import jarvis                      # loads .env, holds the AI brain + tools
import briefing
import voice
from tools import planner, orders

UI = Path(__file__).resolve().parent / "ui" / "orb.html"
ALWAYS_LISTEN = os.getenv("JARVIS_ALWAYS_LISTEN", "1") != "0"


class Jarvis:
    def __init__(self):
        self.window = None
        self.history = []
        self.busy = threading.Lock()
        self.force_listen = False     # next phrase is a command (Space / click / "Jarvis?")
        self.running = True
        self.pool = ThreadPoolExecutor(max_workers=3)

    # ---------------- page bridge ----------------
    def js(self, call, *args):
        if self.window:
            try:
                self.window.evaluate_js(f"jarvis.{call}({', '.join(json.dumps(a, default=str) for a in args)})")
            except Exception as e:
                print(f"[ui] {e}")

    # ---------------- voice ----------------
    @staticmethod
    def prepare(text):
        """Synthesize speech ahead of time. Returns (path, sound, envelope) or None if offline."""
        try:
            path = voice.synthesize(text)
            sound, env = voice.load(path)
            return path, sound, env
        except Exception as e:
            print(f"[voice] no audio for this line, showing text only: {e}")
            return None

    def play(self, text, prepared):
        if prepared:
            path, sound, env = prepared
            self.js("speak", env, text)
            voice.play(sound)
            voice._cleanup(path)
        else:                                   # no voice: still show the words
            self.js("speak", [], text)
            time.sleep(min(9, 0.065 * len(text)))

    def say(self, text):
        if text:
            self.play(text, self.prepare(text))
        self.js("setState", "idle")

    # ---------------- briefing ----------------
    def run_briefing(self):
        self.js("setState", "thinking")
        self.js("clearPanels")
        segments = briefing.build()
        # synthesize every segment in parallel so there are no gaps between them
        futures = [self.pool.submit(self.prepare, s["text"]) for s in segments]
        for seg, fut in zip(segments, futures):
            ready = fut.result()
            if seg["panel"]:
                self.js("panel", seg["panel"], seg["data"])
                time.sleep(0.35)                # let the panel start flying in first
            self.play(seg["text"], ready)
        self.js("setState", "idle")

    # ---------------- panels from AI tool calls ----------------
    def on_tool(self, name, args, out):
        if name == "get_weather":
            self.js("panel", "weather", out)
        elif name in ("get_plan", "add_plan_item", "mark_plan_done"):
            plan = planner.get_plan(args.get("day") if name == "get_plan" else None)
            self.js("panel", "tasks", {"date": plan["date"], "items": plan["tasks"]})
        elif name == "get_orders":
            view = args.get("view", "today")
            if view == "tomorrow":
                self.js("panel", "deliveries", {"date": _tomorrow(), "orders": out["orders"]})
            else:
                labels = {"pending": "PENDING", "open": "OPEN", "overdue": "OVERDUE",
                          "today": "DUE TODAY", "week": "THIS WEEK", "all": "IN TOTAL"}
                self.js("panel", "orders", {**out, "label": labels.get(view, view.upper())})
        elif name in ("add_order", "update_order_status"):
            self.js("panel", "orders", {**orders.get_orders("pending"), "label": "PENDING"})

    # ---------------- handling a request ----------------
    def handle(self, text):
        if not self.busy.acquire(blocking=False):
            return
        try:
            self.js("you", text)
            low = text.lower().strip(" .!?")
            if briefing.is_briefing_request(text):
                self.run_briefing()
            elif low in ("clear", "clear screen", "close panels", "jarvis clear"):
                self.js("clearPanels")
                self.say("Done.")
            else:
                self.js("setState", "thinking")
                try:
                    reply = jarvis.ask(self.history, briefing.strip_wake(text) or text)
                except Exception as e:
                    print(f"[brain] {e}")
                    reply = "I can't reach my AI brain right now. Check the API key in your .env file and your internet."
                    self.history.clear()
                print(f"You: {text}\nJARVIS: {reply}\n")
                self.say(reply)
            if low in ("goodbye", "bye", "goodbye jarvis", "bye jarvis", "shut down", "exit"):
                time.sleep(0.3)
                self.running = False
                self.window.destroy()
        finally:
            self.busy.release()

    # ---------------- microphone loop ----------------
    def listen_loop(self):
        while self.running:
            if self.busy.locked() or not (ALWAYS_LISTEN or self.force_listen):
                time.sleep(0.15)
                continue
            forced = self.force_listen
            try:
                heard = voice.listen(timeout=4, phrase_limit=10)
            except Exception as e:
                print(f"[mic] {e}")
                if self.force_listen:
                    self.force_listen = False
                    self.js("setState", "idle")
                time.sleep(2)
                continue
            if self.busy.locked():                 # Jarvis started talking meanwhile
                continue
            forced = forced or self.force_listen

            if forced:
                self.force_listen = False
                if heard:
                    self.handle(heard)
                else:
                    self.js("setState", "idle")
            elif heard and briefing.heard_wake(heard):
                print(f"[heard] {heard}")
                if briefing.is_briefing_request(heard) or briefing.strip_wake(heard):
                    self.handle(heard)
                else:                              # just "Jarvis?"
                    with self.busy:
                        self.say(f"Yes, {briefing.short_name()}?")
                    self.force_listen = True
                    self.js("setState", "listening")

    # ---------------- startup ----------------
    def on_loaded(self):
        voice.init()
        self.js("hud", {"ai": jarvis.PROVIDER,
                        "mic": "Say “Hello Jarvis”" if ALWAYS_LISTEN else "Press Space to talk"})
        time.sleep(2.4)                            # let the boot animation play
        with self.busy:
            self.say(f"Systems online. Say hello whenever you're ready, {briefing.short_name()}.")
        threading.Thread(target=self.listen_loop, daemon=True).start()


def _tomorrow():
    from datetime import date, timedelta
    return (date.today() + timedelta(days=1)).isoformat()


class Api:
    """Functions the page can call (window.pywebview.api.*)."""
    def __init__(self, j):
        self._j = j

    def send_text(self, text):
        threading.Thread(target=self._j.handle, args=(text,), daemon=True).start()

    def start_listening(self):
        if self._j.busy.locked():
            return
        self._j.force_listen = True
        self._j.js("you", "")
        self._j.js("setState", "listening")


def main():
    j = Jarvis()
    jarvis.TOOL_HOOK = j.on_tool
    j.window = webview.create_window(
        "JARVIS", str(UI), js_api=Api(j),
        width=1280, height=800, min_size=(1000, 680), background_color="#02040a",
    )
    j.window.events.loaded += lambda: threading.Thread(target=j.on_loaded, daemon=True).start()
    webview.start()
    j.running = False


if __name__ == "__main__":
    main()
