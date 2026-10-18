# ClearPath: 90-second demo

**Submit `ClearPath-demo-AMD.mp4`.** It records the real AMD-backed browser workflow with synthetic narration (1:58, about 2.7 MB, 1600 × 900, H.264/AAC). Full audio/video decoding passed. The baseline video is an earlier fallback. The shorter script below is available if you prefer to record your own voice.

The event-linked [official submission guide](https://lablab.ai/ai-articles/hackathon-guidelines) asks for a video link, duration within 5 minutes, and size under 300 MB. It recommends a 16:9 cover. The accessible guide does not specify a mandatory video container/codec; MP4 is a practical export choice, subject to the upload form. Our 90-second target fits the published duration.

**Event:** AMD Developer Hackathon: ACT III. **Selected challenge:** Track 2 — Health and Wellbeing. **AMD API live verification completed:** DeepSeek-V4-Flash generates the draft through the configured Radeon API; the browser displays provider/model evidence. Credentials are not recorded.

## Preparation

1. Start the application from the repository root:
   `.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000`
2. Open the browser interface at `http://127.0.0.1:8000/`. If the UI is not present in your build, use `http://127.0.0.1:8000/docs` and the five workflow endpoints.
3. Use patient `PT-402`, proposed medication `Amoxicillin`, and note: `Prepare a discharge draft for clinician review. Confirm follow-up instructions before release.`
4. Rehearse creation, approval, running checks, editing the note, and returning to the saved workflow. Use a new workflow for the final take.
5. Do not show `.env`, terminal history with credentials, or actual patient records.

## Timed narration and screen actions

| Time | Screen action | Narration |
| --- | --- | --- |
| 00–10 | Show title, then browser dashboard | “ClearPath helps a discharge coordinator see what has been reviewed, what needs attention, and whether findings still match the latest draft.” |
| 10–25 | Show synthetic patient input and create a draft | “Here is our synthetic patient. We enter a clinician note and proposed medication. DeepSeek-V4-Flash, accessed through the configured AMD Radeon API, prepares a summary for human review.” |
| 25–37 | Approve revision 1 | “Approval belongs to a specific revision. The workflow requires this review before checks run, so an unreviewed draft cannot silently move forward.” |
| 37–57 | Run checks; point to both results | “Pharmacy and billing run concurrently through MCP tools. The demo pharmacy rule flags the planted medication-allergy match. Billing identifies two missing gauze units and one missing stapler. These are findings for review, not automatic corrections or clinical clearance.” |
| 57–72 | Edit note; show revision 2 and cleared results | “If the note changes, a new revision is created. The previous approval and findings are cleared. A worker result from an older revision is rejected rather than attached to the new content.” |
| 72–83 | Reload saved workflow, or show saved ID | “SQLite preserves the workflow across restarts. FastAPI, Pydantic, and explicit state rules keep the same structured contract from browser to tool result.” |
| 83–90 | Return to overview | “ClearPath makes discharge preparation reviewable. Our next step is validated integrations with real clinical systems, while people remain responsible for approval.” |

## Recording notes

- If you only reload the page, say “the workflow remains available”; demonstrate a server restart if you specifically narrate a restart recovery.
- Do not claim a measured time saving, accuracy rate, revenue increase, real insurer approval, AMD execution, or model usage unless the final implementation supplies that evidence.
- Keep the actual video under the platform's limit. A clear 90-second recording is preferable to reading every implementation detail.
- If a provider is integrated before recording, update the draft sentence to name the actual demonstrated provider and model. Keep deterministic checks distinct from model generation.

## Upload metadata

**Video title:** ClearPath — A Reviewable Discharge Workflow

**Video description:** Synthetic-data demonstration of a versioned hospital discharge workflow, concurrent MCP pharmacy and billing checks, and persistent state. Prototype for coordination and human review; not clinical clearance.
