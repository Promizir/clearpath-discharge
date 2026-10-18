# ClearPath — Discharge Coordination

Copy-ready submission content for AMD Developer Hackathon: ACT III. The linked platform guide specifies a title up to 50 characters, summary up to 255 characters, and long description of at least 100 words. The content below fits those limits. [Official submission guide](https://lablab.ai/ai-articles/hackathon-guidelines)

## Project title

ClearPath — Discharge Coordination

## Short description

A discharge coordination prototype that brings a reviewable patient draft, pharmacy findings, and billing discrepancies into one versioned workflow, with explicit human approval and persistent records.

## Long description

Hospital discharge spans clinical documentation, medication review, and billing. Each participant needs to know which information has been reviewed and whether a finding still applies after a change.

ClearPath demonstrates a shared discharge workflow for a hospital discharge coordinator. A clinician's note and proposed medicines are combined with a synthetic patient record. DeepSeek-V4-Flash, accessed through the configured AMD Radeon API, prepares a summary and review notes. Doctor approval is attached to a specific revision. Once approved, pharmacy and billing workers run concurrently through Model Context Protocol (MCP) tools and return structured findings.

The demonstration includes an exact medication/allergy matching rule and a comparison of recorded consumable usage with billed quantities. Results distinguish a completed check with findings from a check that failed to run. An edit invalidates approval and existing findings, preventing results from an earlier revision from being silently reused. SQLite preserves workflow snapshots across application restarts.

The implementation uses Python, FastAPI, Pydantic, FastMCP, asyncio, and SQLite. The core workflow can be exercised locally through the API and command-line examples; the browser interface provides a visual demonstration of the same workflow.

This is a synthetic-data prototype. The AMD inference path has returned a valid draft in a real synthetic-input run. The pharmacy and billing checks remain deterministic. No clinical effectiveness or hospital-outcome claims are made. The pharmacy rule is deliberately narrow, not a clinical medication safety system. The workflow supports review; it does not authorize discharge. Real EHR connections, authenticated clinical approvals, insurer integrations, and production clinical validation remain future work.

## Problem and intended user

**Problem:** Discharge information and checks span multiple responsibilities. When a draft changes, teams need an explicit way to recognize outdated approvals and findings.

**Primary user:** A hospital discharge coordinator overseeing the status of a patient's discharge preparation.

**Supporting users:** Clinicians reviewing draft content, pharmacy reviewers examining medication findings, and billing staff resolving quantity discrepancies.

**Value proposition:** One visible workflow links each review and finding to the content it actually checked.

## Technology tags

Python; FastAPI; Pydantic; Model Context Protocol (MCP); FastMCP; SQLite; asyncio; AMD Radeon API; DeepSeek-V4-Flash; Generative AI; Workflow Automation; Healthcare; Human-in-the-loop; HTML; CSS; JavaScript.

Use AI or a specific hardware/provider tag only if the submitted build actually uses it and you can demonstrate it.

## Selected challenge

**Track 2 — Health and Wellbeing (partner: Vibe Generation).** This track includes healthcare administration and discharge communication. The event requires a meaningful AMD-powered workload in the demonstrated product. The official FAQ permits the AMD Token Factory API. [Official event brief](https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-iii)

**AMD API live verification completed.** On 18 October 2026, the configured Radeon API endpoint returned a schema-valid `DeepSeek-V4-Flash` draft in 60,814 ms. The draft remained awaiting doctor review. See `amd-execution-evidence.json` for synthetic output and request timing. This establishes a successful configured-endpoint call, not independent hardware attestation or a performance benchmark. Final eligibility is determined by the organizers.

The optional Evolus partner track is not targeted by this submission.

## Architecture in one paragraph

A browser sends validated requests to a FastAPI application. The application invokes a versioned workflow that controls approval and check execution. Workers call FastMCP tools to retrieve the synthetic patient record, evaluate the demonstration pharmacy rule, and compare billed and used quantities. asyncio coordinates independent checks, and SQLite persists the workflow snapshot. Pydantic validates inputs and results across these boundaries.

## What is implemented versus planned

| Implemented baseline | Planned / not claimed |
| --- | --- |
| Synthetic patient record and verified AMD API summary generation | Real EHR / FHIR integration |
| Revision-bound simulated doctor approval | Authenticated clinical identities |
| Concurrent pharmacy and billing checks | Validated comprehensive clinical decision support |
| Exact demo allergy rule and quantity discrepancies | Dose, interaction, and brand-name evaluation |
| Persistent workflow snapshots and stale-result rejection | Multi-process production deployment and full audit history |
| Local API, demos, and browser workflow | Insurer eligibility / authorization integrations |
| Explicit human review | Autonomous discharge clearance |

## Before submitting

- [ ] Confirm the deadline and platform timezone; submit before 14:00 Asia/Dubai on 18 October 2026 if that is the actual cutoff.
- [ ] Select **Track 2 — Health and Wellbeing** in the platform.
- [x] Exercise the AMD API summary path and record the model and synthetic output.
- [ ] Enter title, short/long descriptions, and technology tags.
- [x] Public GitHub repository: https://github.com/Promizir/clearpath-discharge
- [ ] Add the demo application platform and live application URL; local run instructions alone do not fill those fields. [Official event submission list](https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-iii)
- [ ] Upload `cover.png` (or another supported format).
- [ ] Upload `ClearPath-pitch.pdf`, or the editable PPTX if the platform prefers it.
- [ ] Record and upload the actual working demo using `DEMO_SCRIPT.md`; keep the video within 5 minutes and under 300 MB, and test link permissions. [Official submission guide](https://lablab.ai/ai-articles/hackathon-guidelines)
- [ ] Replace any team/author fields requested by the platform.
- [ ] Verify that no credentials, local databases, or real patient records are included.
- [ ] Open every submitted link in a signed-out browser.
- [ ] Submit and retain the platform's confirmation.

## Artifact guide

- `cover.svg`: editable vector cover.
- `cover.png`: 1600 × 900 cover for upload.
- `pitch.html`: standalone slide deck; arrow keys navigate, or print all slides to landscape PDF with browser headers/footers disabled.
- `ClearPath-pitch.pdf`: seven-slide presentation ready to upload.
- `ClearPath-pitch.pptx`: editable seven-slide PowerPoint deck.
- `DEMO_SCRIPT.md`: timed narration and recording steps.
- `ClearPath-demo-baseline.mp4`: recorded working browser flow, 2 minutes 1 second, about 2.5 MB, with synthetic narration. This baseline does not demonstrate AMD inference; replace it with a verified AMD recording before claiming the AMD workload.
- **Use `ClearPath-demo-AMD.mp4` for the submission:** verified AMD-backed browser workflow, 1 minute 58 seconds, about 2.7 MB, with synthetic narration. The baseline video is only an earlier local fallback.
- `ClearPath-source.zip`: source archive excluding credentials, local databases, environments, and browser caches.
- `ClearPath-presentation.zip`: cover, slides, video, and submission copy.
- `VERIFICATION.md`: completed checks and outstanding verification.
- `build_assets.py`: reproducible local generator for the visual assets.

The local AMD demo video and live API verification are complete. Video-link upload, platform challenge selection, external prototype/source links, and final platform submission remain outstanding. A local file is not an uploaded video link.
