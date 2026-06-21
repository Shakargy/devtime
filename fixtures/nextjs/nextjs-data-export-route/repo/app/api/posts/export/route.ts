import { NextResponse } from "next/server";

export async function GET() {
  const rows = await loadPosts();
  const csv = rows.map((r) => `${r.id},${r.title}`).join("\n");
  return new NextResponse(csv, { headers: { "Content-Type": "text/csv" } });
}

async function loadPosts() {
  return [{ id: "p_1", title: "hello" }];
}
