#!/usr/bin/env python3
"""Render the demo video: scene.html frame by frame, plus music.py's sound.

Needs Google Chrome and: pip install playwright imageio-ffmpeg numpy scipy
  python3 scripts/demo_video/render.py               # full video in out/
  python3 scripts/demo_video/render.py --stills 3,8  # just those seconds, as PNGs
"""
import argparse
import json
import subprocess
from pathlib import Path

import imageio_ffmpeg
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"


def open_scene(p, timeline):
    browser = p.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    page.on("pageerror", lambda e: print("page error:", e))
    page.add_init_script(f"window.TL = {json.dumps(timeline, ensure_ascii=False)};")
    page.goto((HERE / "scene.html").as_uri())
    page.evaluate("window.ready")
    return browser, page


def stills(timeline, seconds):
    folder = OUT / "stills"
    folder.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser, page = open_scene(p, timeline)
        for s in seconds:
            page.evaluate(f"render({s})")
            page.screenshot(path=str(folder / f"t{s:05.2f}.png"))
        browser.close()
    print(folder)


def full(timeline):
    fps, frames = timeline["fps"], round(timeline["duration"] * timeline["fps"])
    audio = OUT / "sound.wav"
    if not audio.exists():
        raise SystemExit("run music.py first")
    target = OUT / "whale_be_friends_demo.mp4"
    ffmpeg = subprocess.Popen(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error",
         "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg", "-i", "-",
         "-i", str(audio),
         # JPEG frames are full-range; players expect video-range bt709. A little grain keeps the sky from banding.
         "-vf", "scale=in_range=pc:out_range=tv:in_color_matrix=bt601:out_color_matrix=bt709,format=yuv420p,noise=alls=2:allf=t",
         "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
         "-c:v", "libx264", "-preset", "slow", "-crf", "21",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(target)],
        stdin=subprocess.PIPE)
    with sync_playwright() as p:
        browser, page = open_scene(p, timeline)
        for i in range(frames):
            page.evaluate(f"render({i / fps})")
            ffmpeg.stdin.write(page.screenshot(type="jpeg", quality=97))
            if i % 90 == 0:
                print(f"frame {i}/{frames}", flush=True)
        browser.close()
    ffmpeg.stdin.close()
    if ffmpeg.wait() != 0:
        raise SystemExit("ffmpeg failed")
    print(target)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stills", help="comma-separated seconds; writes PNGs instead of the video")
    args = ap.parse_args()
    timeline = json.loads((HERE / "timeline.json").read_text(encoding="utf-8"))
    OUT.mkdir(exist_ok=True)
    if args.stills:
        stills(timeline, [float(s) for s in args.stills.split(",")])
    else:
        full(timeline)


if __name__ == "__main__":
    main()
