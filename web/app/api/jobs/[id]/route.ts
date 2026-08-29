import { NextResponse } from "next/server";

export async function GET(_request: Request, context: { params: Promise<{ id: string }> }) {
  const workerUrl = process.env.WORKER_URL;
  const workerKey = process.env.WORKER_API_KEY;
  if (!workerUrl || !workerKey) {
    return NextResponse.json({ error: "Worker is not configured" }, { status: 503 });
  }
  const { id } = await context.params;
  const response = await fetch(`${workerUrl.replace(/\/$/, "")}/v1/jobs/${encodeURIComponent(id)}`, {
    headers: { authorization: `Bearer ${workerKey}` },
    cache: "no-store",
  });
  const text = await response.text();
  return new NextResponse(text, { status: response.status, headers: { "content-type": "application/json" } });
}
