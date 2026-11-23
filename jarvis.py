"""
JARVIS - personal assistant for Aish.

  python jarvis.py              chat by typing
  python jarvis.py --voice      talk to it (mic + speaker)
  python jarvis.py --briefing   one-shot daily briefing: weather, plan, deliveries
"""
import argparse
import json
import os
from datetime import datetime

from dotenv import load_dotenv

from tools import weather, planner, orders

load_dotenv()

# Which AI powers Jarvis (set JARVIS_PROVIDER in .env):
#   gemini -> Google Gemini, free tier (GEMINI_API_KEY)
#   claude -> Anthropic Claude API, paid (ANTHROPIC_API_KEY)
#   ollama -> free model running on your own PC
PROVIDER = os.getenv("JARVIS_PROVIDER", "gemini").lower()
DEFAULT_MODELS = {"gemini": "gemini-3.8-flash", "claude": "claude-sonnet-5", "ollama": "llama3.1"}
MODEL = os.getenv("JARVIS_MODEL") or DEFAULT_MODELS.get(PROVIDER, "gemini-3.8-flash")

if PROVIDER == "claude":
    from anthropic import Anthropic
    client = Anthropic()
else:
    from openai import OpenAI
    if PROVIDER == "ollama":
        client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
    else:
        client = OpenAI(base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                        api_key=os.getenv("GEMINI_API_KEY"))

# ---------------- tools Jarvis can use ----------------

TOOLS = [
    {
        "name": "get_weather",
        "description": "Current weather and today's forecast at the user's location.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_plan",
        "description": "Tasks and calendar events for a day.",
        "input_schema": {
            "type": "object",
            "properties": {"day": {"type": "string", "description": "YYYY-MM-DD, default today"}},
        },
    },
    {
        "name": "add_plan_item",
        "description": "Add a task or event to the user's plan.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "day": {"type": "string", "description": "YYYY-MM-DD, default today"},
                "time": {"type": "string", "description": "HH:MM, optional"},
                "notes": {"type": "string"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "mark_plan_done",
        "description": "Mark a plan item as done by id.",
        "input_schema": {
            "type": "object",
            "properties": {"item_id": {"type": "integer"}},
            "required": ["item_id"],
        },
    },
    {
        "name": "get_orders",
        "description": "Client orders by delivery date or status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "view": {"type": "string",
                         "enum": ["today", "tomorrow", "week", "pending", "open", "overdue", "all"]},
                "client": {"type": "string", "description": "optional client name filter"},
            },
        },
    },
    {
        "name": "add_order",
        "description": "Record a new client order.",
        "input_schema": {
            "type": "object",
            "properties": {
                "client": {"type": "string"},
                "item": {"type": "string"},
                "qty": {"type": "integer"},
                "delivery_date": {"type": "string", "description": "YYYY-MM-DD"},
                "phone": {"type": "string"},
                "address": {"type": "string"},
            },
            "required": ["client", "item", "qty", "delivery_date"],
        },
    },
    {
        "name": "update_order_status",
        "description": "Change an order's status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "status": {"type": "string",
                           "enum": ["pending", "confirmed", "out_for_delivery",
                                    "delivered", "cancelled"]},
            },
            "required": ["order_id", "status"],
        },
    },
]

HANDLERS = {
    "get_weather": lambda **k: weather.get_weather(),
    "get_plan": planner.get_plan,
    "add_plan_item": planner.add_plan_item,
    "mark_plan_done": planner.mark_plan_done,
    "get_orders": orders.get_orders,
    "add_order": orders.add_order,
    "update_order_status": orders.update_order_status,
}


def system_prompt():
    now = datetime.now().astimezone()
    return (
        f"You are JARVIS, {os.getenv('JARVIS_NAME', 'Aishani')}'s personal assistant. Be concise, warm and a little witty. "
        f"Address the user as {os.getenv('JARVIS_SHORT_NAME', 'Aish')}. "
        "'Pending orders' means orders with status pending or confirmed (use view 'pending'). Answers may be spoken aloud, so avoid markdown and long lists; "
        "use short natural sentences. Use your tools for anything about weather, the plan for the day, "
        "or client orders and deliveries - never guess. Before changing an order or the plan, "
        "confirm the details if anything is ambiguous. "
        f"Current local time: {now.strftime('%A %d %B %Y, %H:%M %Z')}."
    )


TOOL_HOOK = None  # the orb window sets this so tool results pop up as dashboard panels


def run_tool(name, args):
    try:
        out = HANDLERS[name](**args)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
    if TOOL_HOOK:
        try:
            TOOL_HOOK(name, args, out)
        except Exception as e:
            print(f"[panel] {e}")
    return out


def ask(history, text):
    """Send one user turn, let the AI call tools as needed, return the final reply."""
    if PROVIDER == "claude":
        return _ask_claude(history, text)
    return _ask_openai_style(history, text)


def _ask_claude(history, text):
    history.append({"role": "user", "content": text})
    while True:
        resp = client.messages.create(
            model=MODEL, max_tokens=1024, system=system_prompt(),
            tools=TOOLS, messages=history,
        )
        history.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if b.type == "text")

        results = []
        for block in resp.content:
            if block.type == "tool_use":
                out = run_tool(block.name, block.input)
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(out, default=str),
                })
        history.append({"role": "user", "content": results})


def _openai_tools():
    tools = []
    for t in TOOLS:
        fn = {"name": t["name"], "description": t["description"]}
        if t["input_schema"].get("properties"):
            fn["parameters"] = t["input_schema"]
        tools.append({"type": "function", "function": fn})
    return tools


def _ask_openai_style(history, text):
    """Gemini and Ollama both speak the OpenAI chat format."""
    history.append({"role": "user", "content": text})
    for _ in range(8):  # safety limit on tool rounds
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": system_prompt()}] + history,
            tools=_openai_tools(),
        )
        msg = resp.choices[0].message
        calls = msg.tool_calls or []
        entry = {"role": "assistant", "content": msg.content or ""}
        if calls:
            entry["tool_calls"] = [
                {"id": c.id, "type": "function",
                 "function": {"name": c.function.name, "arguments": c.function.arguments or "{}"}}
                for c in calls
            ]
        history.append(entry)
        if not calls:
            return msg.content or ""

        for c in calls:
            try:
                args = json.loads(c.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            out = run_tool(c.function.name, args)
            history.append({"role": "tool", "tool_call_id": c.id,
                            "content": json.dumps(out, default=str)})
    return "Sorry Aish, that took too many steps. Could you ask it another way?"


# ---------------- voice (optional) ----------------

def make_voice():
    import voice
    return voice.listen, voice.speak


# ---------------- main ----------------

BRIEFING = ("Give me my daily briefing: the weather where I am, my plan for today, "
            "and today's client deliveries plus anything overdue.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--voice", action="store_true")
    p.add_argument("--briefing", action="store_true")
    a = p.parse_args()

    listen, speak = (make_voice() if a.voice else (None, None))
    say = speak or (lambda t: None)
    history = []

    if a.briefing:
        reply = ask(history, BRIEFING)
        print(f"JARVIS: {reply}")
        say(reply)
        return

    print("JARVIS online. Say 'briefing' for your daily update, 'exit' to quit.")
    while True:
        text = listen() if listen else input("\nYou: ").strip()
        if not text:
            continue
        if a.voice:
            print(f"You: {text}")
        if text.lower() in {"exit", "quit", "bye", "goodbye"}:
            say("Goodbye, Aish.")
            break
        if text.lower() == "briefing":
            text = BRIEFING
        reply = ask(history, text)
        print(f"JARVIS: {reply}")
        say(reply)


if __name__ == "__main__":
    main()
