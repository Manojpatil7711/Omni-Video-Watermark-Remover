# GPU Worker

This directory documents the production worker boundary used by the Vercel API.

Flow: upload/job request -> GPU worker -> SAM-2 mask propagation -> optional ProPainter/LaMa inpainting -> FFmpeg output.

The worker must expose an authenticated job API and should keep large video payloads off Vercel. Configure object storage URLs rather than sending large binaries through the Vercel request path.

## Contract

`POST /v1/jobs` accepts a JSON job containing `input_url`, `output_url` (or storage destination), `mode`, and optional backend settings. It returns a job id.

`GET /v1/jobs/{id}` returns `queued`, `running`, `completed`, or `failed` plus progress and output metadata.

Do not hard-code credentials in this repository. Use deployment secrets/environment variables.
