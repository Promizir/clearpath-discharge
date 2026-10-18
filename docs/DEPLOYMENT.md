# Publish ClearPath

These files prepare deployment; they do not establish an existing public URL.
Never upload `.env`, `runtime/`, or `.venv/`.

## Public GitHub repository

Use account `Promizir` and create a public repository `clearpath-discharge`.
Upload source, `static/`, `tests/`, `docs/`, and submission artifacts. Extract the
prepared source archive first; upload browsable files, not only the ZIP.

## Hugging Face Docker Space

1. Sign in and create a public Space named `clearpath-discharge`.
2. Choose **Docker**, with the blank template.
3. Upload the source, including `Dockerfile`, `requirements.txt`, `README.md`,
   `mock_ehr.json`, all root Python modules, and `static/`.
4. In settings, add `AI_PROVIDER=AMD`, `AMD_BASE_URL`, and `AMD_MODEL` as variables.
   Add `AMD_API_KEY` as a **secret**.
5. Wait for the build; create a draft, approve it, and run the checks.
6. Confirm the model label, pharmacy finding, and two billing discrepancies.
7. Test the public URL in a signed-out browser.

The README declares Docker and port 7860; the container uses UID 1000. Runtime
secrets reach the server through environment variables. Ordinary container disk
is ephemeral across Space restarts; durable hosting needs configured storage.
[Hugging Face Docker Spaces documentation](https://huggingface.co/docs/hub/spaces-sdks-docker)

## Render alternative

Open [Deploy to Render](https://render.com/deploy?repo=https://github.com/Promizir/clearpath-discharge)
and create a Blueprint from the public repository. Supply the private AMD key;
the model, endpoint, and `AI_PROVIDER=AMD` are preconfigured. The blueprint uses Docker and
the `/health` endpoint. Check current plan, storage, and sleep behavior before
judging. [Render Blueprint reference](https://render.com/docs/blueprint-spec)

## Local Docker

```text
docker build -t clearpath-discharge .
docker run --rm -p 7860:7860 --env-file .env clearpath-discharge
```

Open `http://localhost:7860`. This command uses disposable container storage.
For durability, mount a writable volume and set `DATABASE_PATH` onto that volume.
Docker's `--env-file` expects unquoted values; dotenv's quoted syntax should not
be copied unchanged into a Docker environment file.

## Final checks

- `/health` returns `status: ok`; judges can open the dashboard.
- A real model call produces a visibly labeled AMD draft.
- Approval unlocks both checks; edits invalidate previous results and AI text.
- The public configuration endpoint contains no credentials.
- Submission copy describes only demonstrated functionality.

This anonymous synthetic demo does not authenticate professional identities.
Do not enter real patient information or treat workflow IDs as authorization.
