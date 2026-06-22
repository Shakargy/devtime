import { NextResponse } from "next/server";

// Receives connector sync webhooks (GitHub/Fireflies/Recall style). No payments.
export async function POST(req: Request) {
  const event = await req.json();
  await syncConnector(event.connector);
  return NextResponse.json({ ok: true });
}

async function syncConnector(name: string) {
  return name;
}
