import { NextResponse } from "next/server";

export async function GET(req: Request) {
  if (!isAdmin(req)) {
    return NextResponse.json({ error: "forbidden" }, { status: 403 });
  }
  return NextResponse.json(await listUsers());
}

function isAdmin(req: Request) {
  return req.headers.get("x-role") === "admin";
}

async function listUsers() {
  return [];
}
