import { NextResponse } from "next/server";

export async function POST(request: Request) {
  const supabaseUrl = process.env.SUPABASE_URL;
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  const bucket = process.env.SUPABASE_INPUT_BUCKET ?? process.env.SUPABASE_STORAGE_BUCKET ?? "manox-media";
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
  const base = supabaseUrl.replace(/\/$/, "");
  const encodedPath = path.split("/").map(encodeURIComponent).join("/");
  const signResponse = await fetch(`${base}/storage/v1/object/upload/sign/${encodeURIComponent(bucket)}/${encodedPath}`, {
    method: "POST",
    headers: { apikey: serviceKey, Authorization: `Bearer ${serviceKey}`, "content-type": "application/json" },
    body: JSON.stringify({ upsert: false }),
    cache: "no-store",
  });
  const data = await signResponse.json().catch(() => null);
  if (!signResponse.ok || typeof data?.url !== "string" || typeof data?.token !== "string") {
    return NextResponse.json({ error: data?.message ?? "Unable to create upload URL" }, { status: signResponse.status || 502 });
  }

  // The signed token must be part of the browser upload URL. Without it,
  // Storage evaluates the PUT as an anonymous object INSERT and storage.objects
  // RLS correctly rejects it.
  const returnedUrl = data.url.startsWith("http") ? data.url : `${base}${data.url}`;
  const signed = new URL(returnedUrl);
  if (!signed.searchParams.has("token")) signed.searchParams.set("token", data.token);
  const signedUrl = signed.toString();
  const publicUrl = `${base}/storage/v1/object/public/${encodeURIComponent(bucket)}/${encodedPath}`;
  return NextResponse.json({ bucket, path, token: data.token, signedUrl, publicUrl, contentType });
}
