#!/usr/bin/env python3
"""Make the video's sound from nothing: quiet piano, the lake, and small cues.

Everything is synthesised here, so there is no one's music to credit. Cue times
come from timeline.json. Needs numpy and scipy. Writes out/sound.wav.
"""
import json
import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

HERE = Path(__file__).resolve().parent
SR = 44100
TL = json.loads((HERE / "timeline.json").read_text(encoding="utf-8"))
DUR = TL["duration"] + 0.2
N = int(DUR * SR)
rng = np.random.default_rng(1105)
BEAT = 60 / 66
BAR = BEAT * 4


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def add(buf, sig, t, gain=1.0, pan=0.0):
    """Mix a mono sound into the stereo buffer at time t."""
    start = int(t * SR)
    if start >= N or start < 0:
        return
    sig = sig[: N - start]
    left, right = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    buf[start : start + len(sig), 0] += sig * gain * left
    buf[start : start + len(sig), 1] += sig * gain * right


def band(x, lo, hi):
    return sosfilt(butter(2, [lo, hi], "band", fs=SR, output="sos"), x)


def felt_piano(midi, length=3.2, vel=0.7):
    t = np.arange(int(length * SR)) / SR
    f = hz(midi)
    sig = np.zeros_like(t)
    for n in range(1, 8):
        partial = f * n * np.sqrt(1 + 0.00035 * n * n)
        if partial > 7000:
            break
        decay = 0.9 + 0.75 * n + f / 900
        sig += np.exp(-t * decay) * np.sin(2 * np.pi * partial * t) / n**1.7
        sig += 0.4 * np.exp(-t * decay) * np.sin(2 * np.pi * partial * 1.0015 * t) / n**1.7
    sig *= np.minimum(t / 0.010, 1)  # felt: a soft start
    return sig * vel * 0.26


def music_box(midi, length=2.2, vel=0.5):
    t = np.arange(int(length * SR)) / SR
    f = hz(midi)
    sig = np.exp(-t * 2.3) * np.sin(2 * np.pi * f * t)
    sig += 0.22 * np.exp(-t * 6.5) * np.sin(2 * np.pi * f * 3.0 * t)
    sig += 0.09 * np.exp(-t * 14) * np.sin(2 * np.pi * f * 5.4 * t)
    return sig * np.minimum(t / 0.003, 1) * vel * 0.2


def pad(notes, length):
    t = np.arange(int(length * SR)) / SR
    env = np.minimum(t / 1.3, 1) * np.minimum((length - t) / 1.3, 1)
    sig = sum(np.sin(2 * np.pi * hz(m) * t + i) + 0.5 * np.sin(2 * np.pi * hz(m) * 1.003 * t)
              for i, m in enumerate(notes))
    return sig * env * 0.016


# (root, chord tones) per half bar, F major. Bar 9 lands on the title.
CHORDS = [
    [(41, [60, 64, 67, 69]), (41, [60, 65, 67, 69])],  # F
    [(40, [59, 62, 67, 72]), (45, [60, 64, 67, 71])],  # C/E  Am7
    [(38, [60, 62, 65, 69]), (38, [60, 64, 65, 69])],  # Dm9
    [(46, [58, 62, 65, 69]), (46, [58, 62, 65, 67])],  # Bbmaj7
    [(45, [60, 64, 65, 69]), (45, [60, 65, 67, 69])],  # F/A
    [(43, [58, 62, 65, 69]), (48, [58, 60, 65, 67])],  # Gm7  C7sus
    [(45, [60, 64, 67, 71]), (38, [60, 62, 65, 69])],  # Am7  Dm7
    [(46, [58, 62, 65, 69]), (48, [58, 60, 65, 67])],  # Bbmaj7 C7sus
    [(41, [60, 65, 67, 69]), (41, [60, 65, 67, 72])],  # F add9, rings out
]
# (bar, beat, midi, velocity): small and sparse, the chat should stay in front
MELODY = [
    (0, 2, 72, .55), (0, 3, 74, .5),
    (1, 0, 77, .6), (1, 2.5, 76, .45),
    (3, 0, 74, .5), (3, 1.5, 72, .42), (3, 3, 69, .42),
    (4, 0, 72, .58), (4, 1, 77, .55), (4, 2.5, 76, .5), (4, 3.5, 72, .42),
    (5, 0, 74, .55), (5, 2.5, 72, .45),
    (6, 0, 76, .55), (6, 1.5, 74, .45), (6, 2.5, 72, .5),
    (7, 0, 74, .5), (7, 2, 72, .45),
    (8, 0, 77, .62), (8, 1, 79, .45), (8, 2, 84, .42),
]


def score():
    dry = np.zeros((N, 2))
    for bar, halves in enumerate(CHORDS):
        for half, (root, tones) in enumerate(halves):
            t0 = bar * BAR + half * BAR / 2
            last_bar = bar == len(CHORDS) - 1
            add(dry, pad([root + 12, *tones[:3]], BAR / 2 + 1.3), t0)
            if half == 0 or root != halves[0][0]:
                add(dry, felt_piano(root, 4.0, 0.46), t0)
            if last_bar and half == 1:
                continue
            for k, (beat, idx) in enumerate([(0.5, 0), (1.0, 2), (1.5, 1)]):
                jitter = rng.normal(0, 0.012)
                add(dry, felt_piano(tones[idx], 3.0, 0.5 - 0.05 * k + rng.normal(0, 0.03)),
                    t0 + beat * BEAT + jitter, pan=(idx - 1.5) * 0.22)
    for bar, beat, midi, vel in MELODY:
        add(dry, music_box(midi, vel=vel), bar * BAR + beat * BEAT + rng.normal(0, 0.01), pan=0.18)
    ir_t = np.arange(int(2.2 * SR)) / SR
    wet = np.zeros_like(dry)
    for ch in range(2):
        ir = rng.normal(0, 1, len(ir_t)) * np.exp(-ir_t * 2.6)
        wet[:, ch] = fftconvolve(dry[:, ch], ir, mode="full")[:N]
    wet = wet / (np.abs(wet).max() + 1e-9) * np.abs(dry).max()
    mix = dry + 0.32 * wet
    # a touch of warmth: roll off the top like an old upright
    return sosfilt(butter(2, [55, 5200], "band", fs=SR, output="sos"), mix, axis=0)


def chirp(lo, hi, length, vel):
    t = np.arange(int(length * SR)) / SR
    freq = np.linspace(lo, hi, len(t))
    return np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.sin(np.pi * t / length) ** 2 * vel


def ambience():
    t = np.arange(N) / SR
    out = np.zeros((N, 2))
    g = TL["grade"]
    # the lake: slow swells of filtered noise, always there
    swell = 0.62 + 0.38 * np.sin(2 * np.pi * t / 6.1) * np.sin(2 * np.pi * t / 3.7 + 1)
    for ch in range(2):
        out[:, ch] += band(rng.normal(0, 1, N), 180, 1100) * swell * 0.11
    # morning birds, gone by the time the sun is low
    for when, pan in [(1.1, -.6), (1.42, -.6), (3.3, .5), (3.55, .5), (3.8, .5), (15.8, -.4), (16.1, -.4), (17.4, .6)]:
        add(out, chirp(3000, 4200, .11, .06), when, pan=pan)
        add(out, chirp(4300, 3300, .09, .04), when + .12, pan=pan)
    # crickets come with the night
    level = np.clip((t - g["night_start"]) / 2.2, 0, 1)
    pulse = (np.sin(2 * np.pi * 17 * t) > 0.2) * (np.sin(2 * np.pi * 1.25 * t) > -0.2)
    pulse = sosfilt(butter(2, 180, "low", fs=SR, output="sos"), pulse.astype(float))
    cricket = np.sin(2 * np.pi * 4300 * t) * pulse * level * 0.024
    out[:, 0] += cricket
    out[:, 1] += 0.6 * np.roll(cricket, 900)
    return out


def bloop(lo, hi, vel):
    """A water drop: her messages sound like something from a fish tank."""
    length = 0.14
    t = np.arange(int(length * SR)) / SR
    freq = lo + (hi - lo) * (t / length) ** 1.6
    return np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * 26) * np.minimum(t / 0.004, 1) * vel


def tick(vel):
    length = 0.06
    t = np.arange(int(length * SR)) / SR
    return np.sin(2 * np.pi * 1250 * t) * np.exp(-t * 85) * vel


def cues():
    out = np.zeros((N, 2))
    # the phone buzzes on the sill
    t = np.arange(int(.2 * SR)) / SR
    buzz = np.sin(2 * np.pi * 165 * t) * np.sin(np.pi * t / .2) * 0.07
    add(out, buzz, TL["phone"]["in"] + .05)
    add(out, buzz, TL["phone"]["in"] + .3)
    for m in TL["messages"]:
        if m["who"] == "her":
            add(out, bloop(560, 1180, .17), m["t"], pan=-.25)
        else:
            add(out, tick(.12), m["t"], pan=.25)
    for f in TL["floaters"]["items"]:
        add(out, bloop(380, 760, .11), f["t"], pan=-.15)
    # a pen on paper while the diary writes itself
    for line in TL["diary"]["lines"]:
        n = int((line["t1"] - line["t0"]) * SR)
        t = np.arange(n) / SR
        strokes = 0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 7.3 * t + 3 * np.sin(2 * np.pi * 1.9 * t)))
        strokes = sosfilt(butter(2, 40, "low", fs=SR, output="sos"), strokes)
        add(out, band(rng.normal(0, 1, n), 2600, 7000) * strokes * .05, line["t0"])
    return out


def main():
    music = score()
    sound = 0.92 * music + ambience() + cues()
    t = np.arange(N) / SR
    fade = np.minimum(t / 1.0, 1) * np.clip((TL["duration"] - t) / 1.9, 0, 1) ** 1.5
    sound *= fade[:, None]
    sound = np.tanh(sound / np.abs(sound).max() * 1.1) * 0.5  # gentle ceiling, never clips
    pcm = (sound * 32767).astype(np.int16)
    out = HERE / "out" / "sound.wav"
    out.parent.mkdir(exist_ok=True)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(out, f"peak {np.abs(sound).max():.2f}")


if __name__ == "__main__":
    main()
