# Voyage trip planner

A small FastAPI trip planner for a product analytics class project. The main interface is served at `/`. Visitors can enter a structured trip brief or a free-text request, generate a plan, download a PDF, copy the result, and rate it. The existing LangGraph workflow can call place search, weather, cost, and currency tools. Prices and travel details are estimates; verify them before booking.

## Run locally

Use Python 3.11 or 3.12.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env_example .env
# Fill in either GROQ_API_KEY or GOOGLE_API_KEY in .env.
# The tested configuration is MODEL_PROVIDER=groq and GROQ_MODEL=openai/gpt-oss-20b.
.venv/bin/uvicorn main:app --reload --port 8000
```

Open `http://localhost:8000`. `/health` is the Render health check. The legacy Streamlit client is not used by the deployment.

## Analytics setup

The browser asks visitors to opt in before loading any analytics SDK. Its consent choice is stored in local storage; the footer lets them change it. No prompt text, itinerary text, or email is sent as an event property. Browser-side project IDs are served by `/analytics-config`; never put service secrets there.

Add these environment variables for the platforms you want to compare:

The existing GA4 measurement ID from the project is already set in `render.yaml`; replace it if your class uses a different GA4 property.

| Platform | Variable | Where to find it |
| --- | --- | --- |
| Google Analytics 4 | `GA_MEASUREMENT_ID` | Web data stream measurement ID (`G-...`) |
| Mixpanel | `MIXPANEL_TOKEN` | Project token |
| Amplitude | `AMPLITUDE_API_KEY` | Project API key |
| PostHog | `POSTHOG_PROJECT_TOKEN`, `POSTHOG_HOST` | Project token and ingestion host (US or EU) |

All four receive the same explicit events from `analytics.js`. Automatic click, form, and session recording are disabled to avoid collecting trip text. Analytics project IDs are public browser credentials by design; LLM keys remain server-side.

LangSmith tracing is off in `.env_example` because traces can contain trip requests. Enable it separately only if your study needs debugging traces and you have told participants.

| Event | Trigger | Useful question |
| --- | --- | --- |
| `page_view` | Consent granted on the planner page | How many opted-in visitors arrived? |
| `planner_opened` | Planner enters the viewport | What share reached the planner? |
| `destination_selected` | Destination card clicked | Which featured destination attracts interest? |
| `example_prompt_clicked` | Example prompt clicked | Do examples help people start? |
| `plan_started` | Valid trip request submitted | How many people try planning? |
| `plan_generated` | Non-empty result returned | What is the generation completion rate and latency? |
| `plan_failed` | Empty, HTTP, or network failure | Where does the funnel fail? |
| `plan_downloaded` | PDF link clicked | Do users save their plans? |
| `plan_copied` | Copy succeeds | Do users reuse the plan elsewhere? |
| `plan_feedback_submitted` | Helpful / Needs work clicked | How useful do users find results? |

Suggested metrics for the class report:

1. **Planner reach:** unique users with `planner_opened` ÷ unique users with `page_view`.
2. **Start rate:** unique users with `plan_started` ÷ unique users with `planner_opened`.
3. **Completion rate:** successful `plan_generated` events ÷ (`plan_generated` + `plan_failed`) events. Use event counts here so multiple attempts are represented.
4. **Save rate:** unique users with `plan_downloaded` or `plan_copied` ÷ unique users with `plan_generated`.
5. **Helpful rate:** `helpful` feedback ÷ all `plan_feedback_submitted` events.
6. **Median generation time:** median `duration_seconds` on `plan_generated`; segment by `source`, `budget_tier`, or `duration_days`.

Use the same date range, timezone, consent population, and definitions in GA4, Mixpanel, Amplitude, and PostHog. Build a funnel `page_view → planner_opened → plan_started → plan_generated → plan_downloaded` in each tool. Some browsers block analytics scripts, so these counts are directional rather than a census of all visitors. Do not count your own local testing: no platform keys are needed locally.

## Deploy on Render

1. Push this branch to your GitHub repository.
2. In Render, create a Blueprint from the repository; `render.yaml` defines the Python web service and `/health` check.
3. Set `GROQ_API_KEY` (or change `MODEL_PROVIDER` to `google` and set `GOOGLE_API_KEY`). Set other tool API keys as available.
4. Set the four analytics variables above. Use the host shown in your PostHog project settings if it is not the US host.
5. After deployment, visit `/health`, generate one plan, verify PDF download, then confirm each configured provider receives `page_view`, `plan_started`, and `plan_generated` in its live event debugger.

Render's free filesystem is ephemeral, so generated PDFs can disappear after a restart or redeploy. For the class study, ask users to download them immediately. Durable saved plans would require object storage.

Do not commit `.env`; it is ignored by Git. Keep API keys in Render's environment settings. For traffic from friends, monitor provider quotas and Render logs; the Google free tier may rate limit repeated tool-driven requests.
