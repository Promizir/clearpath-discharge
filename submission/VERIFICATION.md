# Verification status

Local verification on 18 October 2026 (Asia/Dubai):

- **52 automated tests passed.** Covers input validation, MCP tools, revision
  approval, stale-result rejection, concurrent execution, cancellation,
  partial failures, save failure, restore behavior, inference response parsing,
  sanitized provider errors, and the public-demo AI request budget.
- **Browser workflow passed in Chrome.** Created and approved a workflow, ran
  both checks, verified the allergy finding and two billing discrepancies,
  downloaded a report, restored after reload, and invalidated results on edit.
- **Mobile layout passed at 390 px.** No horizontal overflow; screenshots saved.
- **No browser JavaScript errors** occurred in the browser test.
- **Seven-slide pitch** verified, including an actual dashboard screenshot.
- **Baseline MP4** generated: 121.24 seconds, 1600 × 900, H.264 video and AAC
  synthetic narration, approximately 2.5 MB. Full audio/video decoding passed;
  the pharmacy/billing scene was visually inspected. It does not demonstrate AMD.
- **Final AMD MP4** generated and decoded successfully: 118.28 seconds,
  1600 × 900, H.264/AAC, about 2.7 MB. The recorded browser successfully generated
  an AMD draft, approved it, ran checks, invalidated it after an edit, and restored
  revision 2 on reload. Synthetic narration is used.

Tests use synthetic data. Unit tests mock the HTTP inference boundary; they are
not evidence of AMD execution, clinical effectiveness, or production readiness.

- **Linux container verified:** Docker build succeeded. The running container
  passed health, draft creation, approval, pharmacy, and billing checks. Its saved
  approved workflow and findings were restored after a container restart.
- **Public source published:** https://github.com/Promizir/clearpath-discharge

Still pending:

- Hosted app, video-link upload, and final submission.

Reproduce unit tests with `python -m unittest discover -s tests -v` and browser
checks with `python scripts/qa_dashboard.py --url http://127.0.0.1:8000`.

## Live model verification

`scripts/verify_amd.py` successfully called the configured AMD Radeon API on
18 October 2026. DeepSeek-V4-Flash returned a valid summary and review notes in
60,814 ms. The draft remained `AWAITING_DOCTOR_REVIEW`. The synthetic response
is saved in `amd-execution-evidence.json`; credentials are excluded. This is one
integration check, not a latency benchmark, clinical evaluation, or independent
attestation of the provider's hardware.
