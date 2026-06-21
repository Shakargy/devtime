import { NextResponse } from "next/server";

export async function POST(req: Request) {
  const form = await req.formData();
  const file = form.get("file");
  await store(file);
  return NextResponse.json({ ok: true });
}

async function store(file: unknown) {
  return file;
}
