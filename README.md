# 🤖 Jarvis — AI Voice Assistant with ML Inventory Intelligence

A personal, Jarvis-style voice assistant built in Python that gives a daily briefing — weather, tasks, client orders and deliveries — and includes a **Business Activity** screen powered by the stockout prediction pipeline from my MSc AI dissertation.

> Related project: [MSc-Dissertation-ML-RPA-inventory-automation](https://github.com/<your-username>/MSc-Dissertation-ML-RPA-inventory-automation) — an intelligent automation framework combining XGBoost stockout forecasting with UiPath RPA replenishment.

---

## ✨ Features

- **Voice interaction** — talk to Jarvis and get spoken responses
- **Daily briefing** — weather, today's tasks, and pending client orders/deliveries
- **AI conversation** — powered by the Google Gemini API (free tier)
- **Business Activity screen** — runs the dissertation's XGBoost stockout model for today's date and shows which products are at risk
- **Risk classification** — products flagged as **HIGH / MEDIUM / LOW** stockout risk, plus expiry-based promotion suggestions
- **Manager-in-the-loop** — no automatic emails; you tell Jarvis which alerts have been actioned and it keeps track

---

## 🧠 How the ML integration works

```
Inventory data (CSV)
        │
        ▼
stockout_pipeline.py  ──►  xgboost_final.pkl  (trained in the dissertation)
        │
        ▼
Daily predictions: stockout probability per product (3-day horizon)
        │
        ▼
Jarvis "Business Activity" screen  ──►  Manager reviews & confirms actions by voice
```

The model was trained on a 44,000+ row retail dataset with Mauritius-specific demand patterns (salary peaks, school seasons, public holidays, cyclone closures, promotions). On the Jul–Oct 2026 test window, XGBoost achieved **83.67% accuracy** and **88.76% recall** at the deployed threshold.

---

## 🛠️ Tech Stack

| Area | Tools |
|---|---|
| Language | Python 3.x |
| AI | Google Gemini API |
| Machine Learning | XGBoost, pandas, scikit-learn, joblib |
| Voice | `<speech-recognition library>`, `<text-to-speech library>` |
| Weather | `<weather API>` |
| UI | `<GUI library, e.g. Tkinter / CustomTkinter>` |
| Platform | Windows, VS Code |

---

## 📁 Project Structure

```
jarvis/
├── main.py                  # Entry point
├── stockout_pipeline.py     # Daily inference using the trained model
├── models/
│   └── xgboost_final.pkl    # Trained XGBoost model from the dissertation
├── data/
│   └── inventory.csv        # Inventory dataset
├── .env.example             # API key template
├── requirements.txt
└── README.md
```

---

## 🚀 Getting Started

1. **Clone the repository**
   ```bash
   git clone https://github.com/<your-username>/<repo-name>.git
   cd <repo-name>
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Add your API keys** — create a `.env` file:
   ```
   GEMINI_API_KEY=your_gemini_key
   WEATHER_API_KEY=your_weather_key
   ```

4. **Run Jarvis**
   ```bash
   python main.py
   ```

---

## 🔮 Future Improvements

- Automated monthly model retraining
- Connecting to live inventory data instead of CSV
- Mobile companion app
- Multi-language support (English / French / Kreol)

---

## 👩‍💻 Author

**Aishani (Aish)** — Software Engineer · MSc Artificial Intelligence, University of Mauritius

📍 Mauritius · [LinkedIn](<your-linkedin-url>) · [GitHub](https://github.com/<your-username>)
