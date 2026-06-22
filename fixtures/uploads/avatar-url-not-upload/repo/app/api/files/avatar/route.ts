import { NextResponse } from "next/server";

// Returns a user's avatar URL. Read-only; no upload, no multipart, no storage write.
export async function GET(req: Request) {
  const url = new URL(req.url);
  const userId = url.searchParams.get("userId");
  return NextResponse.json({ avatarUrl: `https://cdn.example.com/${userId}.png` });
}
