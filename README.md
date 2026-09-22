# AI Video Agent

Turns a text prompt into a short-form MP4: script, narration, visuals, captions, render, and a QA retry loop.

## Setup

1. Install [FFmpeg](https://ffmpeg.org/) and make sure `ffmpeg` / `ffprobe` are on your PATH.
2. Create a virtual environment and install dependencies:

```bash
python -m venv myenv
myenv\Scripts\activate
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and set `GEMINI_API_KEY`.

## Run

```bash
python main.py "Create a cinematic reel about morning exercise"
```

Options:

- `--aspect-ratio` — `9:16` (default), `16:9`, or `1:1`
- `-o` / `--output` — output MP4 path (default: `output/final_video.mp4`)

## Tests

```bash
python tests/test_engine.py
```

## Pipeline

1. Gemini writes a scene script (hook, narration, visuals, motion).
2. Edge-TTS generates speech; scene timing follows measured audio length.
3. Whisper (when available) supplies word timestamps for captions.
4. Images are generated (Pollinations, with a local fallback).
5. FFmpeg renders Ken Burns motion, mixes audio, and burns captions.
6. QA scores the file and retries if the score is below the pass threshold.
