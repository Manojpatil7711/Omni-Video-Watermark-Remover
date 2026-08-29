import { NextResponse } from "next/server";

export async function POST(request: Request) {
  const workerUrl = process.env.WORKER_URL;
  const workerKey = process.env.WORKER_API_KEY;
  if (!workerUrl || !workerKey) {
    return NextResponse.json({ error: "Worker is not configured" }, { status: 503 });
  }

  const body = await request.json();
  if (typeof body.input_url !== "string" || !body.input_url) {
    return NextResponse.json({ error: "input_url is required" }, { status: 400 });
  }

  const response = await fetch(`${workerUrl.replace(/\/$/, "")}/v1/jobs`, {
    method: "POST",
    headers: { "content-type": "application/json", authorization: `Bearer ${workerKey}` },
    body: JSON.stringify({ input_url: body.input_url }),
    cache: "no-store",
  });
  const text = await response.text();
  return new NextResponse(text, { status: response.status, headers: { "content-type": "application/json" } });
}
