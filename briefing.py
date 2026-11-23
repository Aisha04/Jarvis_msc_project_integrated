"""The "Hello Jarvis" briefing.

Builds a list of segments. Each segment = one dashboard panel + what Jarvis says
while that panel is on screen. Built locally (no AI call), so it is fast and
never uses up your free API quota.
"""
import os
from datetime import date, timedelta

from tools import weather, planner, orders


def full_name():
    return os.getenv("JARVIS_NAME", "Aishani")


def short_name():
    return os.getenv("JARVIS_SHORT_NAME", "Aish")


def spoken_time(hhmm):
    """'21:00' -> '9 PM', '21:30' -> '9:30 PM'"""
    h, m = map(int, hhmm.split(":"))
    suffix = "AM" if h < 12 else "PM"
    h12 = (h + 11) % 12 + 1
    return f"{h12} {suffix}" if m == 0 else f"{h12}:{m:02d} {suffix}"


def join_and(parts):
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + ", and " + parts[-1]


def plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


# ---------------- each section ----------------

def weather_segment():
    w = weather.get_weather()
    now, today = w["now"], w["today"]
    text = (f"Weather. It's {round(now['temperature_c'])} degrees and {now['condition']} "
            f"in {w['location']}. Today's high is {round(today['high_c'])}, "
            f"with a low of {round(today['low_c'])}")
    rain = today.get("rain_chance_pct") or 0
    text += f", and a {rain} percent chance of rain." if rain >= 30 else ", and it should stay dry."
    return {"panel": "weather", "data": w, "text": text}


def tasks_segment():
    plan = planner.get_plan()
    items = [dict(i) for i in plan["tasks"]]
    cal = plan["calendar_events"]
    if isinstance(cal, list):  # Google Calendar events, if connected
        for e in cal:
            items.append({"title": e["title"], "time": None if e["time"] == "all day" else e["time"], "done": False})
    items.sort(key=lambda i: i.get("time") or "00:00")

    todo = [i for i in items if not i.get("done")]
    if not todo:
        text = f"Tasks for today, {short_name()}. Your schedule is clear."
    else:
        phrases = [i["title"] + (f" at {spoken_time(i['time'])}" if i.get("time") else "") for i in todo]
        text = f"Tasks for today, {short_name()}. You have {join_and(phrases)}."
    return {"panel": "tasks", "data": {"date": plan["date"], "items": items}, "text": text}


def orders_segment():
    pending = orders.get_orders("pending")
    n = pending["count"]
    text = f"Orders. You have {plural(n, 'order', 'orders')} pending." if n else "Orders. Nothing pending right now."
    overdue = orders.get_orders("overdue")["count"]
    if overdue:
        text += f" {plural(overdue, 'order is', 'orders are')} overdue."
    return {"panel": "orders", "data": pending, "text": text}


def deliveries_segment():
    tomorrow = orders.get_orders("tomorrow")
    due = [o for o in tomorrow["orders"] if o["status"] not in ("delivered", "cancelled")]
    n = len(due)
    text = (f"Deliveries. You have {plural(n, 'delivery', 'deliveries')} due tomorrow."
            if n else "Deliveries. Nothing is due for delivery tomorrow.")
    day = (date.today() + timedelta(days=1)).isoformat()
    return {"panel": "deliveries", "data": {"date": day, "orders": due}, "text": text}


def build():
    """Return the full briefing, skipping any section that fails (e.g. no internet for weather)."""
    segments = [{"panel": None, "data": None,
                 "text": f"Welcome back {full_name()}. Here are the updates for you."}]
    for make in (weather_segment, tasks_segment, orders_segment, deliveries_segment):
        try:
            segments.append(make())
        except Exception as e:
            print(f"[briefing] {make.__name__}: {e}")
    segments.append({"panel": None, "data": None,
                     "text": f"That's everything for now, {short_name()}. Anything else?"})
    return segments


# ---------------- wake phrase ----------------

WAKE_NAMES = ("jarvis", "jarvi", "javis", "jervis", "travis", "jarvas")  # common mis-hearings
GREETINGS = ("hello", "hi", "hey", "hallo", "helo", "good morning", "good evening", "good afternoon",
             "morning", "evening", "update", "briefing", "brief me")


def heard_wake(text):
    t = text.lower()
    return any(n in t for n in WAKE_NAMES)


def is_briefing_request(text):
    t = text.lower().strip(" .!?,")
    if t in ("briefing", "updates", "my updates"):
        return True
    return heard_wake(t) and any(g in t for g in GREETINGS)


def strip_wake(text):
    """'Jarvis, what's the weather' -> "what's the weather" """
    t = text
    for n in WAKE_NAMES:
        i = t.lower().find(n)
        if i != -1:
            t = (t[:i] + t[i + len(n):])
            break
    return t.strip(" ,.!?")
