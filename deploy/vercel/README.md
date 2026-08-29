# Vercel integration

This deployment layer is intended for the web control plane only. Large video payloads should be uploaded directly to object storage; Vercel should create and poll processing jobs rather than proxying video bytes.

Required environment variables:

- `GPU_WORKER_URL` — HTTPS base URL of the deployed GPU worker.
- `GPU_WORKER_API_KEY` — server-side worker API key.
- `STORAGE_UPLOAD_URL` — optional signed-upload endpoint supplied by the storage layer.

Recommended flow:

1. Browser requests a signed upload target.
2. Browser uploads the video directly to storage.
3. Browser submits the resulting `input_url` to the Vercel job API.
4. Vercel calls `POST /v1/jobs` on the GPU worker.
5. Browser polls the Vercel status endpoint until the worker returns a result URL.

Do not expose `GPU_WORKER_API_KEY` to browser code.
