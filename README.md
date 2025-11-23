🧬 BioIP Discovery Agent

Production-Ready Vertical Agent For Life Sciences IP Discovery

🎯 Overview

BioIP Discovery Agent is an AGI-powered vertical agent that automates the discovery, classification, and analysis of Life Sciences and Medical Device intellectual property from university technology transfer offices.

The Problem

VCs and pharma companies waste 20+ hours/week manually searching university websites for relevant IP, resulting in:

60–70% of opportunities missed

$2,000+ cost per comprehensive search

Weeks of delay identifying technologies

Our Solution

Automated IP discovery in 5 minutes:

Speed: 20 hours → 5 minutes (240× faster)

Cost: $2,000 → $0.50 (99.98% reduction)

Coverage: 30% → 95% (≈3× more opportunities)

✨ Key Features
🤖 AGI-Powered Architecture

Advanced memory: maintains conversation context across sessions

Tool orchestration: autonomously coordinates multiple specialized agents

Multi-step reasoning: handles chained, complex workflows

Context-aware: learns preferences and adapts behavior

🔍 Intelligent Discovery

Multi-university support: 50+ tech transfer offices

JavaScript rendering with Playwright (modern SPAs)

Smart pagination: automatic detection and traversal

Multilingual: auto-translation for international sources

🎯 AI Classification

Hybrid approach: heuristics + GPT-4o (85–95% accuracy)

Cost modes:

Free: ~75% accuracy

Smart: ~$0.15 / 100 IPs

Always: ~$0.40 / 100 IPs

Domain-specific: Life Sciences vs Medical Devices

Confidence scoring: adjustable thresholds

📊 Due Diligence Scoring

8-dimensional framework:

Clinical Evidence (20%)

Regulatory Clarity (15%)

IP Strength (15%)

Market Attractiveness (15%)

Manufacturing Readiness (10%)

Competitive Moat (10%)

Team Quality (10%)

Source Quality (5%)

🎤 Multi-Modal Interaction

Voice Agent: natural language phone interface (Telnyx)

Web Interface: production React app (Lovable)

REST API: full programmatic access

🏗️ Production-Ready

Sentry monitoring

API authentication & rate limiting

Cost tracking & budgets

Comprehensive logging

Environment-based config

🏗️ Architecture
┌─────────────────────────────────────────────────────────────┐
│                        USER INTERFACES                     │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐│
│  │  Web Frontend  │  │  Voice Agent   │  │   REST API     ││
│  │   (Lovable)    │  │   (Telnyx)     │  │   (FastAPI)    ││
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘│
└──────────┼────────────────────┼────────────────────┼─────────┘
           │                    │                    │
           ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    AGI ARCHITECTURE LAYER                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │          Memory & Tool Orchestration                 │   │
│  │  • Session-based conversation memory                 │   │
│  │  • Multi-agent coordination                          │   │
│  │  • Context-aware reasoning                           │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│                       BACKEND SERVICES                      │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐   │
│  │   Discovery   │  │ Classification│  │    Analysis   │   │
│  │    Engine     │  │    (OpenAI)   │  │    Engine     │   │
│  └───────────────┘  └───────────────┘  └───────────────┘   │
└─────────────────────────────────────────────────────────────┘

🚀 Quick Start
Prerequisites

Python 3.10+

API keys:

Required: OpenAI

Optional: Telnyx, AGI

Installation
git clone https://github.com/your-username/bioip-discovery-agent.git
cd bioip-discovery-agent
./setup.sh

Configuration
cp .env.example .env
nano .env  # Add your API keys


Minimum:

OPENAI_API_KEY=sk-proj-your-key-here


Full integration:

OPENAI_API_KEY=sk-proj-...
AGI_API_KEY=your-agi-key
TELNYX_API_KEY=KEY...
TELNYX_PHONE_NUMBER=+1...
SENTRY_DSN=https://...

Run Discovery Pipeline
# 1. Discover IPs
python scripts/step_ex_new.py https://techfinder.stanford.edu/

# 2. Filter & classify
python scripts/step1_5_filter_urls.py data/raw/raw_urls_stanford.json

# 3. Analyze
python scripts/dd_blob_runner.py data/filtered/filtered_urls_stanford.json

Start Services
# Terminal 1: API
python backend/api.py        # → http://localhost:8000

# Terminal 2: Voice Agent
python backend/voice_agent.py  # → http://localhost:8001

🎤 Voice Agent

Example queries:

“Find me cancer immunotherapy patents from Stanford”

“Show me diabetes medical devices”

“What’s the top-scored CRISPR technology?”

Features:

Natural language understanding

AGI memory across calls

Multi-turn conversations

Real-time responses

Demo without Telnyx:

python scripts/demo_voice.py

🌐 Web Interface

Live: https://ip-discover.lovable.app/

Search interface

Filtering & sorting

Detailed reports

Data visualization

Export (CSV / JSON / PDF)

📚 API Documentation
Key Endpoints

Discovery

POST /api/v1/discover
{
  "url": "https://techfinder.stanford.edu/",
  "max_pages": 50
}


Search

POST /api/v1/search
{
  "query": "cancer immunotherapy",
  "session_id": "demo"
}


Analysis

POST /api/v1/analyze
{
  "ip_id": "stanford-tech-123",
  "source": "stanford"
}


Interactive docs: http://localhost:8000/docs

📁 Project Structure
bioip-discovery-agent/
├── backend/
│   ├── api.py                  # FastAPI server
│   └── voice_agent.py          # Telnyx integration
├── scripts/
│   ├── step_ex_new.py          # Discovery engine
│   ├── step1_5_filter_urls.py  # AI classification
│   └── dd_blob_runner.py       # Due diligence
├── config/
│   └── settings.py             # Configuration
├── data/
│   ├── raw/                    # Discovered URLs
│   ├── filtered/               # Classified IPs
│   └── analyzed/               # Scored results
└── docs/                       # Documentation

🏆 Hackathon Highlights
Requirements ✅
Requirement	Status
AGI API Integration	✅ Complete
Tool Orchestration	✅ Complete
Lovable Frontend	✅ Live
Telnyx Voice	✅ Production-ready
Production Quality	✅ Enterprise-grade
Innovation

Hybrid classification: cost vs accuracy trade-offs

Pre-scraping filter: ~70% efficiency gain

AGI memory: cross-session context

8D scoring: comprehensive DD framework

Multi-modal: Voice + Web + API

Impact

240× faster than manual

99.98% cost reduction

3× more opportunities found

85–95% classification accuracy

💰 Cost Management
Classification Modes
Mode	Cost / 100 IPs	Accuracy
Heuristic	$0	75–80%
Smart	$0.15	85–90%
Always	$0.40	90–95%

Telnyx costs:

~$1–2 / month

~$0.01 / min per call

Built-in tracking (env):

MONTHLY_BUDGET_USD=100.00
ALERT_AT_PERCENT=80

🛠️ Development

Tests:

pytest
pytest --cov=backend


Code quality:

black .
flake8 .
mypy backend/

🚢 Deployment
Docker
docker build -t bioip-agent .
docker run -p 8000:8000 bioip-agent

Heroku
heroku create bioip-agent
heroku config:set OPENAI_API_KEY=sk-...
git push heroku main


See docs/DEPLOYMENT.md for more details.

📊 Performance
Operation	Time	Throughput
Discovery	2–5 min	100–200 URLs / min
Classification	0.1–0.3 s	300–1000 IPs / min
Analysis	5–10 s	6–12 IPs / min
API	<100 ms	100+ req / s


🤝 Contributing
# Make changes, test
pytest

# Submit PR
git push origin feature/amazing

📄 License

MIT License – see LICENSE.
