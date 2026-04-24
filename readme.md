# AutoEditsMusicVideos2010s

Super Deluxe Python Tkinter GUI for building longer 2010s nostalgia auto-edited music videos with FFmpeg.

## Features
- Multiple video files and multiple video folders.
- Optional recursive folder scan for big archives.
- Multiple audio/music/SFX sources.
- Random one-song or shuffled combine-all music modes.
- Random SFX mix modes: Off, Random one, Random concat bed.
- Long generation controls: min/max clip duration, clip count, resolution, FPS, CRF, seed.
- Transition modes: Cut/Fade with timing and transition FX presets (Fade/Glitch/Warp/RGB Split).
- Dance controls + beat-aware behavior (TBPM tag when available, BPM fallback otherwise).
- Remix modes: Original, Nightcore, Slow Jam, Hyper Dance.
- Instant VFX toggle, draft mode, intro/outro pools, speed ramp, loop/reverse/stutter chances.
- Trailer/Teaser builder, branding logo overlay.
- Remix style presets: Chaos, Beat, Meme, YouTube Poop, TikTok, AMV.
- Save/load JSON presets.

## Requirements
- Python 3.8+
- FFmpeg + FFprobe available in PATH, or select both in the GUI

## Run
```bash
python autoedit_gui.py
```

## Normal GUI alias
```bash
python autoedit_gui_normal.py
```

## Small GUI alias
```bash
python autoedit_gui_small.py
```

## Windows 8.1 tutorials
- `tutorial setup python windows 8.1 autoeditsmusicvideofor2000s.md`
- `tutorial python windows 8.1 autoeditsmusicvideofor2000s.md`

## Tip for very long videos
Raise **Total clips** (for example 200+) and widen **min/max clip seconds**.
