# Sibyl — AI Internship Scout (cf_ai_sibyl)

Sibyl is an autonomous, explainable AI agent that discovers and evaluates internship opportunities tailored to your profile.

Instead of manually searching through job boards, Sibyl continuously scans niche sources, evaluates opportunities using AI reasoning, and delivers only the most relevant matches.

This project was built as part of the Cloudflare AI Application assignment.

---

# ✨ What Sibyl Does

Sibyl automatically:

* Scans niche internship sources
* Cleans and normalizes job listings
* Removes duplicates
* Evaluates opportunities using AI
* Explains reasoning and uncertainty
* Scores opportunities based on your profile
* Sends alerts via Telegram
* Stores decisions and logs for transparency

---

# 🧠 Core Philosophy

Sibyl is built around:

* Explainable AI (no black-box decisions)
* Personalization (resume-driven matching)
* Automation (no manual searching)
* Transparency (logged reasoning)
* Assistive Intelligence (human-in-the-loop)

---

# ⚙️ System Architecture

Scheduler (GitHub Actions)
↓
Fetcher → Processor → Scorer → Decision Engine
↓
Cloudflare Workers AI (LLM)
↓
Cloudflare D1 (Logs & Memory)
↓
Telegram Bot (User Interface)
↓
User Feedback → Continuous Improvement

---

# 🤖 AI Decision Output Example

```json
{
  "score": 8.7,
  "reason": "Strong UI/Frontend alignment",
  "matched_skills": ["React", "UI"],
  "missing_skills": ["Next.js"],
  "uncertainty": "Job description lacks frontend depth details"
}
```

---

# 📡 Data Sources

Sibyl scans:

* Hacker News (Who is Hiring)
* NoDesk
* WorkWithIndies
* GitHub Opportunities
* Additional niche sources (planned)

These sources provide:

* Lower competition
* Higher signal opportunities
* Startup-focused roles

---

# 🧾 Resume-Driven Personalization

Users can upload a resume:

Sibyl extracts:

* Skills
* Role preferences
* Interests
* Experience level

This allows Sibyl to adapt scoring to the user profile.

---

# 🧠 Explainable AI Logging

Every decision is logged in Cloudflare D1:

* Score
* Reasoning
* Missing skills
* Uncertainty
* Source
* Timestamp
* Profile snapshot

This enables:

* Transparency
* Debugging
* Continuous improvement
* Trustworthy AI

---

# 📲 Telegram Interface

Example Alert:

🔥 8.9 MATCH — Frontend Intern @ Startup

Why:
• Strong UI alignment
• Matches profile

Missing:
• Next.js

Uncertainty:
• JD unclear about frontend depth

Remote: Yes
Apply: link

Feedback buttons:

👍 Good
👎 Bad
🤏 Close
🚫 Ignore

---

# 🧠 Feedback Loop

User feedback improves future scoring:

* Good → strengthen signals
* Bad → weaken signals
* Ignore → deprioritize

Sibyl learns continuously.

---

# 🧰 Tech Stack

* Cloudflare Workers AI — LLM reasoning
* Cloudflare D1 — Logging & memory
* GitHub Actions — Scheduler / automation
* Python — Agent logic
* Telegram Bot — User interface
* APIs / scraping — Data collection

---

# 🚀 Running Sibyl

(Initial setup — will evolve)

1. Clone repository

```
git clone https://github.com/yourusername/cf_ai_sibyl.git
cd cf_ai_sibyl
```

2. Install dependencies

```
pip install -r requirements.txt
```

3. Configure environment variables

Create `.env`

```
TELEGRAM_BOT_TOKEN=
CLOUDFLARE_API_KEY=
D1_DATABASE_ID=
```

4. Run agent

```
python main.py
```

---

# 📁 Project Structure

```
cf_ai_sibyl/
│
├── agent/
│   ├── fetcher.py
│   ├── processor.py
│   ├── scorer.py
│   ├── decision.py
│
├── database/
│   ├── d1.py
│
├── telegram/
│   ├── bot.py
│
├── main.py
├── README.md
├── PROMPTS.md
```

---

# 🎯 Why Sibyl

Most job searching tools are:

* Manual
* Noisy
* Inefficient

Sibyl is:

* Autonomous
* Explainable
* Personalized
* Lightweight

Sibyl is designed to assist, not replace, human decision-making.

---

# 🧠 Cloudflare AI Requirements

This project includes:

* LLM (Cloudflare Workers AI)
* Workflow (GitHub Actions + Agent Pipeline)
* User Input (Telegram Interface)
* Memory (Cloudflare D1)

---

# 📌 Status

Current Stage: MVP Development

Planned:

* Web dashboard
* Feedback learning improvements
* More data sources
* Better ranking model

---

# 📜 License

MIT

---

# 👤 Author

Built by Shreya
AI-native internship discovery system
