"""Record the actual browser workflow, with local synthetic narration, to MP4.

Requires Windows SAPI, Chrome, playwright, its ffmpeg install, and imageio-ffmpeg.
Run against an already-running app. Uses a real model if the app is configured.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import time
import wave

import imageio_ffmpeg
from playwright.sync_api import sync_playwright, expect


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "submission" / "video-work"


def narration(scenes):
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "scenes.json").write_text(json.dumps(scenes), encoding="utf-8")
    script = r'''
$ErrorActionPreference='Stop'
$clearPathVideoDir=$env:CLEARPATH_VIDEO_DIR
$clearPathScenes=Get-Content -Raw -LiteralPath (Join-Path $clearPathVideoDir 'scenes.json') | ConvertFrom-Json
$clearPathVoice=New-Object -ComObject SAPI.SpVoice
$clearPathVoice.Voice=$clearPathVoice.GetVoices('Name=Microsoft Zira Desktop').Item(0)
$clearPathVoice.Rate=0
for ($clearPathIndex=0; $clearPathIndex -lt $clearPathScenes.Count; $clearPathIndex++) {
  $clearPathStream=New-Object -ComObject SAPI.SpFileStream
  $clearPathStream.Format.Type=22
  $clearPathStream.Open((Join-Path $clearPathVideoDir "$clearPathIndex.wav"),3,$false)
  $clearPathVoice.AudioOutputStream=$clearPathStream
  [void]$clearPathVoice.Speak($clearPathScenes[$clearPathIndex].speech)
  $clearPathStream.Close()
}
'''
    environment = dict(os.environ, CLEARPATH_VIDEO_DIR=str(WORK))
    result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", script], env=environment, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr)
    for index, scene in enumerate(scenes):
        with wave.open(str(WORK / f"{index}.wav"), "rb") as audio:
            scene["duration"] = audio.getnframes() / audio.getframerate() + 3


def caption(page, text):
    page.evaluate("""text => {
      let node = document.getElementById('recording-caption');
      if (!node) {
        node = document.createElement('div'); node.id = 'recording-caption';
        node.style.cssText = 'position:fixed;bottom:16px;left:22%;right:3%;z-index:9999;background:#152c3bf5;color:white;padding:16px 22px;border-radius:12px;font:500 21px/1.4 Arial;box-shadow:0 6px 30px #0003;pointer-events:none';
        document.body.append(node);
      }
      node.textContent = text;
    }""", text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8765")
    args = parser.parse_args()
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(ROOT / ".browser-cache"))
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        # Read public configuration before choosing truthful narration.
        probe = browser.new_context()
        configured = probe.request.get(args.url + "/api/config").json()["configured"]
        probe.close()
        generation = "An AMD hosted model prepares a summary for human review, using the supplied source facts." if configured else "This baseline assembles a structured draft. The AMD model adapter is present, but this recording does not demonstrate model inference."
        scenes = [
            {"caption": "ClearPath | A shared discharge review workspace", "speech": "ClearPath helps discharge coordinators bring clinical notes, pharmacy review, and billing findings into one visible workflow. This demonstration uses a synthetic patient."},
            {"caption": "01  Prepare a draft from a clinician note and source records", "speech": "We start with a clinician note and a proposed medicine. Patient facts are retrieved through a Model Context Protocol tool. " + generation},
            {"caption": "02  Approval belongs to the exact revision being reviewed", "speech": "The draft awaits doctor review. Checks remain locked until this exact revision is approved. Approval here is simulated for the prototype; it is not discharge authorization."},
            {"caption": "03  Pharmacy and billing checks run concurrently", "speech": "Now the independent pharmacy and billing checks run together. The pharmacy example flags amoxicillin against the documented penicillin allergy. Billing finds two missing gauze units and one missing stapler. The system reports these findings without changing medication orders or charges."},
            {"caption": "A changed note invalidates previous approval and findings", "speech": "If the clinician changes the note, ClearPath creates a new revision. Previous approval, findings, and generated text are cleared. The updated content must be reviewed again."},
            {"caption": "Saved workflow state remains available after a page reload", "speech": "Reloading the page restores the saved workflow. SQLite stores the latest snapshot, while revision checks prevent an old worker result from being attached to changed content."},
            {"caption": "ClearPath | AI helps prepare. People decide.", "speech": "ClearPath demonstrates a reviewable handoff built with Fast API, Python concurrency, typed schemas, and MCP tools. Real clinical integrations and validation are future work. People remain responsible for decisions."},
        ]
        narration(scenes)
        context = browser.new_context(viewport={"width":1600,"height":900}, record_video_dir=str(WORK), record_video_size={"width":1600,"height":900})
        page = context.new_page()
        page.goto(args.url, wait_until="networkidle")
        page.add_style_tag(content="body{zoom:.82}")
        timeline = []
        started = time.monotonic()
        for index, scene in enumerate(scenes):
            scene_start = time.monotonic() - started
            caption(page, scene["caption"])
            if index == 1:
                page.locator("#create-draft").click()
                expect(page.locator("#revision-badge")).to_have_text("Revision 1", timeout=120000)
                if configured:
                    expect(page.locator("#generation-badge")).to_contain_text("AMD")
                page.locator("#draft-content").scroll_into_view_if_needed()
            elif index == 2:
                page.locator("#approve-draft").click()
                expect(page.locator("#run-checks")).to_be_enabled()
            elif index == 3:
                page.locator("#run-checks").click()
                expect(page.locator("#findings")).to_contain_text("Medication conflict detected")
                expect(page.locator("#findings")).to_contain_text("2 item discrepancies")
                page.locator("#findings").scroll_into_view_if_needed()
                page.locator('#recording-caption').evaluate("node => node.hidden = true")
                page.screenshot(path=str(ROOT / "submission" / "screenshots" / ("04-amd-review-findings.png" if configured else "02-review-findings.png")), full_page=True)
                page.locator('#recording-caption').evaluate("node => node.hidden = false")
            elif index == 4:
                page.locator("#review-note").fill("Updated clinician note: confirm follow-up arrangements before completing discharge review.")
                page.locator("#save-note").click()
                expect(page.locator("#revision-badge")).to_have_text("Revision 2")
                expect(page.locator("#run-checks")).to_be_disabled()
            elif index == 5:
                page.reload(wait_until="networkidle")
                page.add_style_tag(content="body{zoom:.82}")
                caption(page, scene["caption"])
                expect(page.locator("#revision-badge")).to_have_text("Revision 2")
            elif index == 6:
                page.locator('[data-view="about"]').click()
                page.evaluate("window.scrollTo(0,0)")
            remaining = scene["duration"] - (time.monotonic() - started - scene_start)
            if remaining > 0:
                page.wait_for_timeout(remaining * 1000)
            timeline.append({**scene, "start": scene_start, "actual_duration": time.monotonic()-started-scene_start})
            print(f"Scene {index+1}/{len(scenes)} recorded", flush=True)
        video = page.video
        context.close()
        video_path = video.path()
        browser.close()

    # Each voice segment starts at its recorded scene boundary. Long model calls
    # remain visible with silence rather than fabricated progress or time claims.
    with wave.open(str(WORK / "0.wav"), "rb") as first:
        params = first.getparams()
    with wave.open(str(WORK / "narration.wav"), "wb") as combined:
        combined.setparams(params)
        for index, scene in enumerate(timeline):
            with wave.open(str(WORK / f"{index}.wav"), "rb") as part:
                combined.writeframes(part.readframes(part.getnframes()))
                padding = max(0, round(scene["actual_duration"] * params.framerate) - part.getnframes())
                combined.writeframes(b"\0" * padding * params.nchannels * params.sampwidth)
    output = ROOT / "submission" / ("ClearPath-demo-AMD.mp4" if configured else "ClearPath-demo-baseline.mp4")
    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", str(video_path), "-i", str(WORK / "narration.wav"), "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(output)]
    subprocess.run(command, check=True, capture_output=True)
    (WORK / "timeline.json").write_text(json.dumps(timeline, indent=2), encoding="utf-8")
    print(f"Created {output.name}: {output.stat().st_size/1024/1024:.1f} MB; synthetic narration; actual browser workflow.")


if __name__ == "__main__":
    main()
