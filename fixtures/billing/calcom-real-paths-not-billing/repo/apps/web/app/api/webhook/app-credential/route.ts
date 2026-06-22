import { NextResponse } from "next/server";

// Receives app credential webhooks (connector credential sync). No payments.
export async function POST(req: Request) {
  const event = await req.json();
  await syncAppCredential(event.appId);
  return NextResponse.json({ ok: true });
}

async function syncAppCredential(appId: string) {
  return appId;
}
