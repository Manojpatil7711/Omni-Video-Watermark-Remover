"use client";

import { FormEvent, useState } from "react";

export default function Home() {
  const [inputUrl, setInputUrl] = useState("");
  const [jobId, setJobId] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  async function createJob(event: FormEvent) {
    event.preventDefault();
    setError("");
    setStatus("Submitting…");
    const response = await fetch("/api/jobs", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ input_url: inputUrl }),
    });
    const data = await response.json();
    if (!response.ok) {
      setError(data.error ?? "Unable to create job");
      setStatus("");
      return;
    }
    setJobId(data.job_id);
    setStatus(data.status ?? "queued");
  }

  async function refresh() {
    if (!jobId) return;
    const response = await fetch(`/api/jobs/${jobId}`, { cache: "no-store" });
    const data = await response.json();
    if (!response.ok) {
      setError(data.error ?? "Unable to read job");
      return;
    }
    setStatus(data.status ?? "unknown");
  }

  return (
    <main style={{ maxWidth: 720, margin: "80px auto", padding: 24, fontFamily: "system-ui" }}>
      <h1>Omni Watermark Remover</h1>
      <p>Remove authorized video overlays with the configured processing worker.</p>
      <form onSubmit={createJob} style={{ display: "grid", gap: 12 }}>
        <label htmlFor="input-url">Input video URL</label>
        <input id="input-url" value={inputUrl} onChange={(e) => setInputUrl(e.target.value)} required type="url" placeholder="https://…/video.mp4" style={{ padding: 12 }} />
        <button type="submit" style={{ padding: 12 }}>Start processing</button>
      </form>
      {jobId && <section style={{ marginTop: 24 }}><strong>Job:</strong> {jobId}<br /><strong>Status:</strong> {status}<br /><button onClick={refresh} style={{ marginTop: 12, padding: 10 }}>Refresh status</button></section>}
      {error && <p role="alert">{error}</p>}
    </main>
  );
}
