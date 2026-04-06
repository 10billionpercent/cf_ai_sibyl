#PROMPTS.md

This project was developed using AI-assisted coding. Prompts were used to accelerate implementation while maintaining full control over architecture, logic, and system design.

Below are condensed and structured versions of the prompts used.

---

##1. Runtime LLM Prompts (Core Intelligence)

This section contains the actual prompts used at runtime for AI-based job evaluation and reasoning.

These prompts define how the system:

- evaluates internship relevance
- generates reasoning
- identifies missing skills
- expresses uncertainty

They are the core of the system’s decision-making behavior.

---

###Job Matching Prompt

(To be added)

---

###Resume Interpretation Prompt

(To be added)

---

###Scoring & Reasoning Prompt

(To be added)

---

###Output Formatting Prompt

(To be added)

---

###Uncertainty Handling Prompt

(To be added)

---

##2. Development Prompts

###Core System Design

"Design an AI agent that autonomously discovers and evaluates internship opportunities. The system should include job fetching, filtering, scoring, explainability, logging, and user feedback integration."

---

###Resume Parsing

"Parse a resume PDF and extract structured data including role, skills, and technologies. Output clean JSON suitable for downstream matching."

---

###Job Fetching (Ashby + Greenhouse)

"Create async Python functions using httpx to fetch job listings from Ashby and Greenhouse APIs. Normalize responses into a consistent structure. Handle failures gracefully and include request delays."

---

###Internship Filtering

"Filter job listings to include only internships using title-based keyword matching (intern, internship). Ensure case-insensitive filtering and avoid false positives."

---

###Job Matching (LLM Core)

"Given a candidate profile and a job, evaluate relevance using an LLM. Return structured output:

- score (0–10)
- reasoning (why it matches)
- matched_skills
- missing_skills
- uncertainty

Ensure explainability and avoid generic responses."

---

###Decision Logic

"Convert LLM score into actionable categories:

- ≥ 8 → High match
- 6–8 → Medium match
- < 6 → Ignore

Ensure decisions are consistent and interpretable."

---

###Telegram Bot Messaging

"Format job matches into clean Telegram messages with:

- match score
- role and company
- reasoning (why)
- missing skills
- uncertainty
- apply link

Messages should be concise, readable, and actionable."

---

###Feedback System

"Design a feedback mechanism using inline buttons (Good, Bad, Close, Ignore). Capture user feedback and store it for future analysis and system improvement."

---

###MongoDB Integration

"Store structured job and resume data in MongoDB. Persist only meaningful data (e.g., user-approved jobs) to optimize storage and signal quality."

---

###Cloudflare D1 Logging

"Design SQL schema to log all evaluated jobs and system events. Include score, reasoning, uncertainty, and timestamps. Ensure logs enable traceability and debugging."

---

###Logging Integration

"Integrate logging into the pipeline without disrupting core logic. Log:

- all evaluated jobs (job_logs)
- system events (event_logs)

Ensure minimal overhead and clean structure."

---

###System Architecture

"Structure the system as a modular pipeline:

fetch → normalize → filter → match → decide → notify → log

Ensure separation of concerns and scalability."

---

###Explainability Principles

"Ensure the AI system is not a black box. Every decision must include:

- reasoning
- missing skills
- uncertainty

The system should assist, not replace, human decision-making."

---

###AI Usage Philosophy

"Use AI as a reasoning layer, not just a generator. Prioritize clarity, structure, and usefulness over verbosity."

---

###Additional Development Prompts (Condensed)

- "Generate async job fetchers using httpx with retry and delay logic"
- "Normalize API responses into a consistent job schema"
- "Design a logging system using Cloudflare D1 with SQL schema"
- "Integrate logging into an existing FastAPI pipeline without breaking functionality"
- "Format Telegram messages for clarity and readability"
- "Create structured LLM outputs for job matching"

---

##Final Note

This system was built iteratively using AI-assisted development, with a focus on:

- real-world usability
- explainable decision-making
- modular architecture
- continuous improvement via feedback
