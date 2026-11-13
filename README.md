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

## Version B

The existing `/` experience remains Version A. Visit `/version-b` for the new discovery and planning experience. It has destination details with verified location photos, a guided trip brief, AI generated itineraries, alternative plans, targeted day and activity changes, budget alternatives, an itinerary assistant, weather forecasts and indoor alternatives, curated nearby attractions for the four featured destinations, photo and place context for identifiable attractions, photo-rich PDF export, sharing, local device saving, light/dark themes, and mobile navigation. Costs and routes are estimates; verify them before booking. Weather forecasts cover the next five days, which may differ from travel dates.

Version B researches destinations with the existing `TAVILY_API_KEY`, chooses named hotels and restaurants from retrieved sources, drafts route themes, and writes and validates each day. It tries the configured Groq model first and can use the Google key as a fallback. Automatic model retries are disabled so quota errors do not stall requests. If an individual day is incomplete or rate-limited after a bounded attempt, that day uses a clearly marked research fallback. If both providers are unavailable before planning starts, the API returns a prompt 503 with a quota message. Hotel rates are shown only when an indexed result names the same property and explicitly identifies a nightly room rate; these are indicative snippets, not live inventory or bookable quotes. The local-spend total includes known activity estimates and a sourced room-rate floor when available, and states what is excluded. Weather requires `OPENWEATHERMAP_API_KEY`. Place summaries and photos are retrieved from Wikipedia and Wikimedia Commons without a new key. A photo is omitted if the place or its license credit cannot be matched reliably. Image credits and Wikimedia file links appear beside photos and in the PDF. Saved trips currently stay in the visitor's browser and are not synchronized across devices. Events from the two routes carry `experiment_variant` (`A` or `B`), but randomized A/B assignment has not been implemented.

## Analytics setup

The browser asks visitors to opt in before loading any analytics SDK. Its consent choice is stored in local storage; the footer lets them change it. No prompt text, itinerary text, or email is sent as an event property. Browser-side project IDs are served by `/analytics-config`; never put service secrets there.

Add these environment variables for the platforms you want to compare:

The existing GA4 measurement ID from the project is already set in `render.yaml`; replace it if your class uses a different GA4 property.

| Platform | Variable | Where to find it |
| --- | --- | --- |
| Google Analytics 4 | `GA_MEASUREMENT_ID` | Web data stream measurement ID (`G-...`) |
| Mixpanel | `MIXPANEL_TOKEN` | Project token |
| Mixpanel region (optional) | `MIXPANEL_API_HOST` | Leave unset for a US project; EU: `https://api-eu.mixpanel.com`; India: `https://api-in.mixpanel.com` |
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
| `travel_source_opened` | Version B hotel or restaurant source opened | Do researched stay and dining suggestions attract interest? |

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

Render's free filesystem is ephemeral, so generated PDFs can disappear after a restart or redeploy. For the class study, ask users to download them immediately. Version B saved trips use Supabase; generated PDF files still need durable object storage if they must remain downloadable later.

Do not commit `.env`; it is ignored by Git. Keep API keys in Render's environment settings. For traffic from friends, monitor provider quotas and Render logs; the Google free tier may rate limit repeated tool-driven requests.
# Version B decision features

## My bookings

Version B has a separate booking workspace for flights, trains, hotels, and activities. Travelers can upload a text-based PDF or an image, review the extracted details, correct them, and save a local timeline. A deterministic checker flags missing dates/references, reversed dates, overlapping hotels, differing traveler names, and arrival after checkout. These are review prompts, not provider-side booking verification. Files are processed in memory and are not persisted by the server; only the saved booking fields are stored in that browser's localStorage. No email connection is required.

Extraction uses the existing `GROQ_API_KEY` for text interpretation. Images additionally require `GOOGLE_API_KEY` for vision. The optional `BOOKING_VISION_MODEL` defaults to `gemini-2.5-flash-lite`. If the provider quota is unavailable or a scanned PDF has no text, travelers can still enter details manually. Do not upload real sensitive travel documents to a public class demo without the traveler's agreement.

Booking analytics events: `booking_add_started`, `booking_upload_started`, `booking_extraction_completed`, `booking_extraction_failed`, `booking_saved`, `booking_review_opened`, `booking_corrected`, `booking_check_completed`, `booking_issue_reviewed`, and `booking_deleted`.

## Before You Book

Version B includes an evidence-led travel offer checker in place of the route navigator. Visitors enter a property or tour name, destination, optional HTTPS listing URL, price, contact number, payment method, and seller claims. The backend queries SerpApi Maps, Tavily Search, and (when a listing URL is given) Tavily Extract in parallel. It compares place names, website domains, and phone numbers, and presents each finding with a source. Unverified information stays **unconfirmed**; the tool never certifies an offer as safe or fraudulent.

Set `SERPAPI_API_KEY` and `TAVILY_API_KEY` as server-side environment variables locally and on Render. These already exist in the local `.env`. Neither key is published to the browser. A check uses search/extraction allowance from those services. The app does not store submitted offers. For a public deployment, keep sample/tester inputs non-sensitive and monitor provider usage.

Product analytics events: `offer_workspace_viewed`, `offer_check_started`, `offer_check_completed`, `offer_check_failed`, `offer_evidence_opened`, and `offer_feedback_submitted`. No listing URL, property name, contact detail, or seller claim is sent in analytics event properties.

## Version B accounts and saved trips

Version B now requires a Supabase account before its features can be used. Users can register with email/password or continue with Google. New generated trips are saved automatically, and **My trips** loads every saved itinerary for the signed-in user. Itinerary changes update the same record. The `trips` table is protected by row-level security so users can access only their own records. Booking timelines remain browser-local for now and are isolated by account on each device; they are not synced across devices. The parked Version A remains an unchanged experiment baseline.

To finish setup:

1. Create a Supabase project. In its SQL Editor, run [`supabase-trips.sql`](supabase-trips.sql) once.
2. Copy the **Project URL** and **publishable/anon key** from Project Settings → API. Add them to local `.env` and Render as `SUPABASE_URL` and `SUPABASE_ANON_KEY`. Never use a service-role key here.
3. In Supabase Authentication → URL Configuration, set the site URL to the deployed VOYAGE URL and add `https://ai-trip-planner-3-wpbu.onrender.com/version-b` and `http://127.0.0.1:8765/version-b` as redirect URLs.
4. For Google sign-in, create a Google OAuth web client in Google Cloud. In Google Cloud, add the **Supabase callback URL** shown under Supabase Authentication → Providers → Google as an authorized redirect URI. Paste the Google client ID and secret into that Supabase provider configuration. The browser never receives the Google client secret.
5. Ensure email/password is enabled in Supabase Authentication → Providers → Email. If email confirmation is enabled, users must confirm before signing in. Configure SMTP for reliable delivery to external testers.
6. Deploy the updated app, register a test account, generate a trip, sign out, sign back in, and verify it appears in **My trips**. Repeat with a second account to check isolation.

The public `SUPABASE_ANON_KEY` is designed for browser use. `GROQ_API_KEY`, `TAVILY_API_KEY`, `SERPAPI_API_KEY`, and any Google AI key remain server-only. Do not put service-role keys in the browser or Git.

## Version A/B measurement in GA4

Share `https://ai-trip-planner-3-wpbu.onrender.com/experiment` with testers. The server assigns A or B at random with equal probability, stores the assignment in a 30-day cookie, and redirects to `/` (A) or `/version-b` (B). Existing direct URLs stay available. Only visits through this entry link carry `experiment_id=voyage_ab_v1` in opted-in analytics; direct visits are excluded from the randomized comparison. Each opted-in assigned page load sends `experiment_exposure` and `page_view` with `experiment_variant` (`A` or `B`). Other feature events carry the same fields. Internal Version B navigation sends `view_changed` so it does not inflate page views.

In GA4, create event-scoped custom dimensions for `experiment_variant` and `experiment_id` under Admin → Data display → Custom definitions. In Explore → Free form, filter `Event name = experiment_exposure` and `Experiment ID = voyage_ab_v1`, put Experiment Variant in Rows, and Total users in Values. This is the consented-user split. Compare conversions with a funnel `experiment_exposure → plan_started → plan_generated`, broken down by Experiment Variant. Allow 24–48 hours for custom dimensions to become available in standard reporting. Keep the same date range for both variants. The allocation is random but observed counts need not be exactly 50/50, especially with a small class sample. Version B also requires an account, so interpret conversion differences as the effect of the whole product experience, including sign-in.

Do not mix synthetic test events with this production property. For a presentation mockup, use a separate GA4 test property or clearly label an external illustrative dataset as simulated. Report the real production counts separately.
