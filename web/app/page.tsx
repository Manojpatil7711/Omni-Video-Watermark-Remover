"use client";

import { FormEvent, useRef, useState } from "react";

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState("");
  const [status, setStatus] = useState("");
  const [progress, setProgress] = useState(0);
  const [outputUrl, setOutputUrl] = useState("");
  const [error, setError] = useState("");
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  async function createJob(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setError(""); setOutputUrl(""); setProgress(0); setStatus("Preparing upload…");
    try {
      const sign = await fetch("/api/upload", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ name: file.name, contentType: file.type || "video/mp4" }),
      });
      const signed = await sign.json();
      if (!sign.ok) throw new Error(signed.error ?? "Unable to prepare upload");

      // Supabase signed-upload targets are consumed by the upload-to-signed-url
      // operation. Use POST with the signed token rather than treating the
      // endpoint as a normal authenticated object PUT; this avoids falling back
      // to an anonymous storage.objects INSERT/RLS check.
      const uploaded = await fetch(signed.signedUrl, {
        method: "POST",
        headers: { "content-type": file.type || "video/mp4" },
        body: file,
      });
      if (!uploaded.ok) {
        const detail = await uploaded.text().catch(() => "");
        throw new Error(detail || "Video upload failed");
      }

      const job = await fetch("/api/jobs", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ input_url: signed.publicUrl }),
      });
      const data = await job.json();
      if (!job.ok) throw new Error(data.error ?? "Unable to create processing job");
      setJobId(data.id); setStatus(data.status ?? "queued");
      if (timer.current) clearInterval(timer.current);
      timer.current = setInterval(() => void refresh(data.id), 2000);
    } catch (e) { setError(e instanceof Error ? e.message : "Upload failed"); setStatus(""); }
  }

  async function refresh(id = jobId) {
    if (!id) return;
    const response = await fetch(`/api/jobs/${encodeURIComponent(id)}`, { cache: "no-store" });
    const data = await response.json();
    if (!response.ok) { setError(data.error ?? "Unable to read job"); return; }
    setStatus(data.status ?? "unknown"); setProgress(Number(data.progress ?? 0));
    if (data.output_url) setOutputUrl(data.output_url);
    if (["completed", "failed"].includes(data.status) && timer.current) { clearInterval(timer.current); timer.current = null; }
  }

  return (
    <main style={{ maxWidth: 720, margin: "80px auto", padding: 24, fontFamily: "system-ui" }}>
      <h1>Omni Watermark Remover</h1>
      <p>Upload a video and remove authorized overlays with the configured processing worker.</p>
      <form onSubmit={createJob} style={{ display: "grid", gap: 12 }}>
        <label htmlFor="video">Video file</label>
        <input id="video" type="file" accept="video/*" required onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        <button type="submit" disabled={!file} style={{ padding: 12 }}>Upload &amp; process</button>
      </form>
      {jobId && <section style={{ marginTop: 24 }}><strong>Job:</strong> {jobId}<br /><strong>Status:</strong> {status}<br /><strong>Progress:</strong> {progress}% {outputUrl && <><br /><a href={outputUrl} target="_blank" rel="noreferrer">Open processed video</a></>}<br /><button type="button" onClick={() => refresh()} style={{ marginTop: 12, padding: 10 }}>Refresh</button></section>}
      {error && <p role="alert">{error}</p>}
    </main>
  );
}
