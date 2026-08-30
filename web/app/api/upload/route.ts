import { NextResponse } from "next/server";

export async function POST(request: Request) {
  const supabaseUrl = process.env.SUPABASE_URL;
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  // Support the environment-variable name already used by the Vercel project,
  // while keeping the older INPUT_BUCKET name backward-compatible.
  const bucket = process.env.SUPABASE_INPUT_BUCKET ?? process.env.SUPABASE_STORAGE_BUCKET ?? "videos";
  if (!supabaseUrl || !serviceKey) {
    return NextResponse.json({ error: "Storage is not configured" }, { status: 503 });
  }

  const body = await request.json().catch(() => null);
  const name = typeof body?.name === "string" ? body.name : "";
  const contentType = typeof body?.contentType === "string" ? body.contentType : "video/mp4";
  if (!name || !contentType.startsWith("video/")) {
    return NextResponse.json({ error: "A video filename and video content type are required" }, { status: 400 });
  }

  const safeName = name.replace(/[^a-zA-Z0-9._-]/g, "_").slice(-120);
  const path = `inputs/${crypto.randomUUID()}-${safeName}`;
  const response = await fetch(`${supabaseUrl.replace(/\/$/, "")}/storage/v1/object/upload/sign/${encodeURIComponent(path)}`, {
    method: "POST",
    headers: { apikey: serviceKey, Authorization: `Bearer ${serviceKey}`, "content-type": "application/json" },
    body: JSON.stringify({ bucketId: bucket, upsert: false }),
    cache: "no-store",
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) return NextResponse.json({ error: data?.message ?? "Unable to create upload URL" }, { status: response.status });
  return NextResponse.json({ bucket, path, token: data?.token, contentType });
}
