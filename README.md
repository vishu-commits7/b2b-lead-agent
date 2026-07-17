# LeadAgent.io — Enterprise B2B Lead Intelligence Platform

Autonomous lead discovery, ICP scoring, contact enrichment, multi-touch outreach, and CRM export — built to sell as a SaaS or white-label deployment.

## What It Does

1. **Discover** — Finds B2B companies via Serper (Google search API)
2. **Scrape** — Pulls live website copy for analysis
3. **Qualify** — Gemini AI scores each lead 0–100 against your ICP
4. **Enrich** — Identifies likely decision makers and email patterns (Pro+)
5. **Outreach** — Generates personalized email + LinkedIn notes + 3-touch sequences (Pro+)
6. **Export** — HubSpot, Salesforce, and standard CSV/JSON
7. **API** — REST API for programmatic pipeline runs (Pro+)

## Pricing Tiers (Built-In)

| Plan | Price | Runs/mo | Leads/run | API | Enrichment | Sequences |
|------|-------|---------|-----------|-----|------------|-----------|
| Starter | Free | 5 | 5 | ❌ | ❌ | ❌ |
| Professional | $497/mo | 100 | 20 | ✅ | ✅ | ✅ |
| Enterprise | $2,497/mo | Unlimited | 50 | ✅ | ✅ | ✅ |

White-label enterprise deployments: **$25k–$75k** one-time (custom quote).

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env        # Add your API keys
streamlit run login.py
```

Sign up → configure API keys in Settings → launch pipeline from Home.

## Environment Variables

See `.env.example`. Required:

- `GEMINI_API_KEY` — [Google AI Studio](https://aistudio.google.com/)
- `SERPER_API_KEY` — [Serper.dev](https://serper.dev/)

Optional:

- `STRIPE_*` — Live subscription billing
- `ADMIN_EMAILS` — Comma-separated admin emails
- `RESEND_API_KEY` — Live email sending

## REST API

```bash
uvicorn api.server:app --port 8000
```

```bash
curl -X POST http://localhost:8000/api/v1/runs \
  -H "Authorization: Bearer la_your_key" \
  -H "Content-Type: application/json" \
  -d '{"niche": "B2B SaaS", "city": "Austin", "num_leads": 5}'
```

Generate API keys from **API Access** page (Pro+ required).

## Docker

```bash
docker compose up --build
```

- App: http://localhost:8501
- API: http://localhost:8000

## Project Structure

```
b2b-lead-agent/
├── login.py              # Entry point — auth gate
├── main.py               # Home dashboard — pipeline + results
├── pages/                # Analytics, Settings, Pricing, Admin, API
├── api/server.py         # FastAPI REST API
├── services/             # Pipeline, CRM export, billing, plans
├── models/schemas.py     # Pydantic data models
├── database.py           # SQLite persistence
├── auth.py               # Password hashing
└── config.py             # Plans, pricing, AI config
```

## How to Sell This

### SaaS ($497–$2,497/mo)
Deploy on Render/Railway/Fly.io, connect Stripe, drive traffic via LinkedIn/cold email to agencies and SDR teams.

### White-Label ($25k–$75k)
Rebrand for agencies: custom domain, their logo, dedicated instance. Charge setup + monthly support.

### API Licensing
Sell API access to CRM tools, sales engagement platforms, or marketing agencies building on top.

## Admin

Set `ADMIN_EMAILS=you@company.com` in `.env` to access the Admin console (user management, audit log, MRR estimate).

## License

Proprietary — configure licensing before resale.
