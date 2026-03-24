# MARS — Multi-Agent Research System

MARS is an AI-powered research assistant that works like a team of specialists, not a single chatbot. You give it a research question, your papers, and your data — and it puts multiple AI agents to work in parallel, each tackling a different part of the problem.

Built for academic researchers who want more than a ChatGPT summary.

---

## What Makes MARS Different?

When you ask ChatGPT or Claude a research question, you get one brain working serially — it reads everything, thinks about it, and gives you a response. That's useful, but it's limited.

MARS works differently. It dispatches **five specialist agents** that each focus on what they do best:

| Agent | Role | What It Does |
|-------|------|-------------|
| **Literature Agent** | Reviews your papers | Extracts findings, identifies themes, flags gaps, rates relevance |
| **Data Agent** | Analyzes your data | Runs statistics, finds patterns, checks data quality, suggests further analyses |
| **Hypothesis Agent** | Generates hypotheses | Proposes testable hypotheses with rationale and predicted outcomes |
| **Critique Agent** | Quality control | Challenges the other agents' work — finds weaknesses, biases, and blind spots |
| **Synthesis Agent** | Writes the report | Combines everything into a structured, publication-ready research report |

### How They Work Together

```
Phase 1 (Parallel):     Literature ───┐
                         Data ─────────┤──→ Phase 2: Critique ──→ Phase 3: Synthesis
                         Hypothesis ───┘
```

The first three agents run **simultaneously** — they don't wait for each other. Once all three finish, the Critique agent reviews their combined output. Finally, the Synthesis agent pulls everything together into a coherent report.

You watch all of this happen in real-time through the dashboard.

---

## Quick Start

### Prerequisites

- Python 3.11 or higher
- Node.js 18 or higher
- That's it! MARS runs on free local AI models by default (no API key needed)

### Setup (one time)

```bash
git clone https://github.com/vishnuskulkarni/mars-v2.git
cd mars-v2
./scripts/setup.sh
```

The setup script will install Ollama (free, local AI) and download the model automatically.

### Launch

```bash
./scripts/start.sh
```

Open **http://localhost:5173** in your browser. That's it.

### Want higher quality output? (Optional)

MARS can also use Claude (Anthropic) for higher quality analysis. Edit `.env`:
```
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-key-here
```

---

## How to Use MARS

1. **Type your research question** — Be specific. "How does sleep quality affect cognitive performance in college students?" works better than "sleep and cognition."

2. **Upload your literature** — Drag and drop PDF files of relevant papers into the Literature section. MARS will extract and analyze their content.

3. **Upload your data** — Drag and drop CSV or Excel files into the Data section. MARS will run statistical analyses automatically.

4. **Launch** — Click "Launch Analysis" and watch the agents work. You'll see a live dashboard showing each agent's progress and streaming output.

5. **Explore the report** — When all agents finish, you get a structured report. You can also click into each agent's individual output to see their full reasoning.

6. **Download** — Export the report as a Markdown file for your records or further editing.

---

## Architecture

```
Browser (React)                    Backend (FastAPI + Python)
┌──────────────────┐              ┌──────────────────────────┐
│                  │   REST API   │                          │
│  Research Input  ├──────────────┤  Orchestrator            │
│  File Upload     │              │    ├─ Literature Agent    │
│                  │   SSE Stream │    ├─ Data Agent          │
│  Agent Dashboard ├──────────────┤    ├─ Hypothesis Agent    │
│  (live updates)  │              │    ├─ Critique Agent      │
│                  │              │    └─ Synthesis Agent     │
│  Report Viewer   │              │                          │
└──────────────────┘              │  All agents call Claude  │
                                  │  API (Anthropic)         │
                                  └──────────────────────────┘
```

---

## Configuration

All settings are in the `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `ollama` | `ollama` (free, local) or `anthropic` (paid, cloud) |
| `OLLAMA_MODEL` | `qwen2.5:7b` | Which Ollama model to use |
| `ANTHROPIC_API_KEY` | — | Your Anthropic API key (only needed if provider is `anthropic`) |
| `CLAUDE_MODEL` | `claude-opus-4-6` | Which Claude model to use (only if provider is `anthropic`) |
| `MAX_FILE_SIZE_MB` | `50` | Maximum file size for uploads |
| `MAX_FILES` | `20` | Maximum number of files per session |
| `PORT` | `8000` | Backend server port |

---

## Project Structure

```
mars/
├── backend/           # FastAPI server + agent logic
│   ├── agents/        # Individual agent implementations
│   ├── prompts/       # System prompts for each agent
│   └── utils/         # File parsing, report export
├── frontend/          # React + Vite + Tailwind UI
│   └── src/
│       ├── components/  # UI components
│       └── hooks/       # React hooks (SSE, sessions)
├── data/              # Uploaded files (per session)
├── reports/           # Generated reports
└── scripts/           # Setup and startup scripts
```

---

## Tech Stack

- **Backend:** Python, FastAPI, Anthropic SDK
- **Frontend:** React, Vite, Tailwind CSS
- **AI:** Ollama + Qwen 2.5 (free, local) by default — optionally Claude (Anthropic) for higher quality
- **Communication:** Server-Sent Events (SSE) for real-time streaming

---

## Roadmap

- [x] v1 — Core agent pipeline + web UI
- [ ] v2 — Deep research agent (auto-fetches papers from the web)
- [ ] v3 — Meta-optimization agent (tunes each agent's focus per question)
- [ ] Deployment — Hosted version for lab-wide access

---

## Contributing

MARS is built for the LISH and D^3 research labs. If you're a lab member and want to contribute:

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes
4. Open a Pull Request

---

## License

MIT
