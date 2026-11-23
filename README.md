# JARVIS

Your personal assistant: weather where you are, your plan for the day, and client orders and deliveries.

## Setup (about 5 minutes)

1. **Install Python 3.10+**, then open a terminal in this folder:
   ```
   python -m venv venv
   venv\Scripts\activate          # Windows
   source venv/bin/activate       # Mac/Linux
   pip install -r requirements.txt
   ```
   If `pyaudio` fails on Windows, run `pip install pipwin` then `pipwin install pyaudio`. You can still type to Jarvis without a mic.

2. **Get a free Gemini API key** at https://aistudio.google.com/apikey. Copy `.env.example` to `.env` and paste it after `GEMINI_API_KEY=`.
   To use Claude instead, set `JARVIS_PROVIDER=claude` and fill in `ANTHROPIC_API_KEY`.

3. **Run it:**
   ```
   python app.py                  # the glowing orb window (the full Jarvis experience)
   python jarvis.py --briefing    # daily update in the terminal
   python jarvis.py               # chat by typing in the terminal
   python jarvis.py --voice       # talk to it in the terminal
   ```

## Running it from VS Code

1. Go to **File → Open Folder** and pick the `jarvis` folder.
2. Install the **Python** extension (by Microsoft) if VS Code asks.
3. Open a terminal with **Terminal → New Terminal** and run the setup commands from step 1 above. Wait for the installs to finish.
4. Press **Ctrl+Shift+P** and choose **Python: Select Interpreter**, then pick the one that shows `venv`.
5. Press **F5** and choose **JARVIS (orb)**. The window opens and Jarvis greets you out loud.

Then:
- **Say "Hello Jarvis".** Jarvis welcomes you and gives the briefing: weather, today's tasks, pending orders and tomorrow's deliveries. Each dashboard flies in as it's spoken.
- **Say "Jarvis, ..." followed by a question**, e.g. "Jarvis, add a call with the supplier tomorrow at 10". The matching dashboard pops up with the answer.
- **Click the orb or press Space** to talk without saying "Jarvis". It turns teal while listening.
- **Say "clear screen"** to hide the dashboards.
- **Type in the box** and press Enter if you'd rather type.
- **Say "goodbye"** to close it.

Orb colours: **cyan** means standing by, **teal** means listening, **blue** means thinking. While speaking, it pulses with the real loudness of the voice.

To preview the orb without running anything, open `ui/orb.html#demo` in Chrome or Edge.

### If something doesn't work
- **Blank window on Windows:** install "Microsoft Edge WebView2 Runtime". It's usually already on Windows 10 and 11.
- **Orb works but there's no voice:** the voice needs internet. Check your connection. The reply text still shows on screen.
- **It doesn't hear you:** check that the mic is allowed under Windows Settings → Privacy → Microphone.
- **Wrong city:** set `JARVIS_LAT`, `JARVIS_LON` and `JARVIS_CITY` in `.env`.
- **Change the voice:** set `JARVIS_VOICE` in `.env`, for example `en-GB-ThomasNeural` or `en-US-AndrewNeural`.

## Things you can say

- "What's the weather like?" / "Will it rain today?"
- "What's my plan today?" / "Add a meeting with the supplier tomorrow at 10"
- "Which deliveries are due today?" / "Anything overdue?"
- "New order: Sample Client B, 3 starter kits, deliver Monday to Curepipe"
- "Mark order 1003 as delivered"

## Your data

| File | What's in it |
|---|---|
| `data/orders.csv` | Client orders. It opens in Excel, so you can edit it there too. The sample rows are placeholders; replace them with your real clients. |
| `data/plan.json` | Your tasks. Add them by voice ("Jarvis, add a client meeting today at 9 PM") or edit the file. The samples are dated 26 Sep 2026. |

## Connect Google Calendar (optional)

1. In Google Cloud Console, create a project and enable the **Google Calendar API**.
2. Create **OAuth client ID** credentials (type: Desktop app) and download the JSON file.
3. Save it here as `credentials.json`. The first run opens a browser window to sign in. After that, Jarvis includes your calendar events in the plan.

## Daily briefing on autopilot

- **Windows:** in Task Scheduler, create a daily task that runs `venv\Scripts\python.exe jarvis.py --briefing --voice` at 7:30.
- **Mac/Linux:** add a crontab line: `30 7 * * * cd /path/to/jarvis && venv/bin/python jarvis.py --briefing --voice`

## Adding new abilities

Every ability is one Python function plus a tool description. To add one:

1. Write the function in `tools/`.
2. Add its description to `TOOLS` and its function to `HANDLERS` in `jarvis.py`.

Claude decides when to use each tool on its own.
