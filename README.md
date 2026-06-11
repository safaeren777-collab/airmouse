# AirMouse V4 — Pinch-Based Touchless PC Control

> **Status: Completed / Archived.** This project was a four-version experiment exploring how far
> webcam-based hand-gesture and facial-expression control of a computer can be pushed — including
> the honest conclusion we reached. Full write-up:
> **[Project Page (GitHub Pages)](https://safaeren777-collab.github.io/airmouse/)**

A Windows desktop application that turns an ordinary webcam into a touchless input device
capable of clicking, scrolling, window management and shortcut triggering. Built with Python,
PyQt6, MediaPipe and the Win32 API.

## What It Does

| Gesture | Action |
|---|---|
| 🤏 Index pinch — **tap** | Confirm / Enter |
| 🤏 Index pinch — **hold & drag** | Continuous page scroll (joystick-style, proportional speed) |
| 🤏 Middle pinch — **horizontal drag** | **Alt-Tab carousel**: Alt stays held, sweep left/right to pick a window, release to switch |
| 🤏 Middle pinch — **vertical drag** | Task View / Show Desktop |
| 🤏 Ring pinch — **4-way drag** | Back / Forward / Maximize / Close Tab |
| 🤏 Middle / Ring / Pinky — **tap** | New Tab / Copy / Paste |
| 🙂 **Face Mode** (Ctrl+Shift+Space) | Raise eyebrows = Alt-Tab · Open mouth = Play/Pause · Wink = Back/Forward |

Every mapping is customizable from the settings panel; prefixing a shortcut with `app:`
launches an application instead (e.g. `app:spotify:`).

## How Machine Learning Is Used

AirMouse runs **two on-device neural networks** per frame via Google's MediaPipe Tasks API
(GPU delegate requested, automatic CPU fallback):

1. **Hand Landmarker** — a two-stage pipeline: a single-shot palm *detector* CNN localizes
   the hand, then a landmark *regression* CNN predicts **21 3D keypoints** (fingertips,
   joints, wrist). Running in `VIDEO` mode exploits temporal coherence: the expensive
   detector only re-runs when tracking confidence drops, keeping per-frame cost low enough
   for ~30 FPS on CPU.
2. **Face Landmarker** — regresses a 478-point 3D face mesh **plus 52 blendshape
   coefficients** (ARKit-compatible expression weights such as `browInnerUp`, `jawOpen`,
   `eyeBlinkLeft`), each a continuous 0–1 score of how strongly the user performs that
   expression.

**The key design decision: classical geometry and state machines *on top of* the ML, instead
of training an end-to-end gesture classifier.** The raw landmarks feed hand-engineered
features — fingertip-to-thumb distance normalized by hand scale (wrist → middle-finger MCP) —
which makes detection invariant to hand size and distance from the camera. Why this approach
won over a custom classifier:

- **No training data needed** — the geometric definition of a pinch generalizes to any hand.
- **Debuggable** — every trigger can be traced to a number crossing a threshold, not an
  opaque model output.
- **Stable** — per-frame neural predictions are noisy; a hysteresis band (pinch *engages*
  below ratio 0.40 but only *releases* above 0.60) plus a state machine
  (IDLE → PINCHED → TAP / SCROLL / CAROUSEL / SWIPE) converts that noise into clean,
  discrete events. This is what fixed the gesture-flicker problem that plagued V3's
  static-pose classifier.

The blendshape stream is filtered the same way: activation threshold + minimum hold duration
(250 ms — a natural blink lasts ~150 ms, so blinks never trigger) + refractory period +
cross-checks (a wink only counts if the *other* eye is open). An exponential moving average
smooths the pinch midpoint before drag distances are measured.

## Architecture

```
                        ┌─────────────────────────────┐
 Webcam ──► OpenCV ──►  │  GestureEngine (QThread)    │
 1280x720 (16:9 FOV)    │  • MediaPipe HandLandmarker │──► Qt signals ──► main.py
 → downscale to 640px   │  • MediaPipe FaceLandmarker │     (pinch_tap, swipe,
                        │  • Pinch state machine      │      scroll_delta, carousel,
                        │  • Blendshape state machine │      face_triggered, ...)
                        └─────────────────────────────┘              │
                                                                     ▼
        ┌────────────────────┬───────────────────────┬──────────────────────────┐
        │ ActionExecutor     │ OverlayWindow         │ SettingsWindow (PyQt6)   │
        │ • pyautogui hotkeys│ • Click-through HUD   │ • Live camera telemetry  │
        │ • Win32 raw scroll │ • Mode pill + toast   │ • Gesture mapping editor │
        │ • Alt-Tab keyDown/ │   notifications       │ • Sensitivity calibration│
        │   keyUp management │                       │                          │
        └────────────────────┴───────────────────────┴──────────────────────────┘
                 + HotkeyListener (Win32 RegisterHotKey, multiple global hotkeys)
```

**Key design decisions:**

1. **Discrete commands instead of absolute positioning.** Pointing a cursor mid-air is both
   exhausting (gorilla-arm syndrome) and imprecise. V4 is fully event-based: taps, swipes,
   carousel.
2. **Pinch + hysteresis.** A pinch is detected from the thumb–fingertip distance normalized
   by hand size. Engage at 0.40, release at 0.60 — the gap structurally eliminates flicker.
3. **The touchpad metaphor.** The pinch itself is the "touch-down moment": pinch → drag →
   release. Gesture start/end become unambiguous, false triggers drop.
4. **Ambiguity guard.** If the two closest fingertips are both within pinch range (a fist),
   the gesture is rejected.
5. **Safe input-state management.** The Alt-Tab carousel physically holds the Alt key;
   `release_all()` is guaranteed on every exit path — hand lost, mode toggled, app quit.
6. **Full field of view.** Forcing 640x480 (4:3) crops the sides of 16:9 webcam sensors;
   the camera is opened at MJPG 1280x720 and downscaled to 640px for processing
   (same CPU cost, full FOV).

## Installation

```bash
pip install -r requirements.txt
python main.py
```

- **Requirements:** Windows 10/11, Python 3.10+, any webcam.
- The `hand_landmarker.task` and `face_landmarker.task` model files ship with the repo.
- **Ctrl+Space** → toggle hand tracking · **Ctrl+Shift+Space** → toggle face mode.
- Note: the in-app UI text is currently in Turkish.

## What We Learned (Why It Was Archived)

After four versions, the honest conclusion: for an able-bodied user on a laptop, webcam
gestures cannot compete with the keyboard. A keyboard shortcut completes in ~200 ms under
all conditions; the camera-latency + model-inference + lighting-dependency chain can't
consistently beat that bar. The real home of this technology is **accessibility** — the same
space Google's Project Gameface targets — not as an alternative to the keyboard, but as a
keyboard for those who cannot use one. The project is therefore archived not as a failure,
but as an experiment whose **question got answered**. The technical gains (hysteresis-based
gesture state machines, MediaPipe integration, Win32 input simulation, click-through
overlays) carry forward to future projects.

## License

MIT — use it however you like.
