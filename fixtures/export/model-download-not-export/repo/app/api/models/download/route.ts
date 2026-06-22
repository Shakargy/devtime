import { NextResponse } from "next/server";

// Downloads an ML model artifact (weights). Not user data export.
export async function GET(req: Request) {
  const url = new URL(req.url);
  const model = url.searchParams.get("model");
  return NextResponse.json({ modelArtifactUrl: `https://models.example.com/${model}.bin` });
}
