# ARON AI Video Studio V1 — FREE ONLY

Local mobile-friendly image-to-video app.

## Features
- Prompt
- Reference image
- Locked 9:16 workflow
- 2/3/4 second generation
- Generate
- Live status
- Preview
- Download MP4
- Hard spending lock = PHP 0

## Free-only architecture
This build uses a public Hugging Face ZeroGPU Space only.
It DOES NOT contain fal, Replicate, paid Inference Provider, or paid fallback code.

Anonymous mode uses anonymous/shared ZeroGPU access.
HF Free Account mode checks remaining included ZeroGPU quota before generation.
If quota cannot be verified or falls below the safety buffer, generation is refused.

## Setup
1. Install Python 3.11+.
2. Recommended: `winget install --id Gyan.FFmpeg -e`
3. Double-click `SETUP_AND_RUN.bat`.
4. Open http://127.0.0.1:5188

Later: `RUN_ARON_STUDIO.bat`

## Default free engine
r3gm/wan2-2-fp8da-aoti-preview

It is a community ZeroGPU Space. Community Spaces may queue, pause, change, or disappear.
The Space ID is editable under Advanced so V1 can switch to another free ZeroGPU engine.

## Important
Free GPU access is quota/queue based, not unlimited.
When free capacity is unavailable, this app STOPS. It never switches to paid compute.
