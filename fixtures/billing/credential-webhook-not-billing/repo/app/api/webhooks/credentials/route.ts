import { NextResponse } from "next/server";

// Receives connector credential-rotation webhooks. No payments.
export async function POST(req: Request) {
  const event = await req.json();
  await rotateCredential(event.connectorId);
  return NextResponse.json({ ok: true });
}

async function rotateCredential(id: string) {
  return id;
}
