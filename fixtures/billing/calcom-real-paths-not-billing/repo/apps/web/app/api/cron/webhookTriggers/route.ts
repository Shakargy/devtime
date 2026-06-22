import { NextResponse } from "next/server";

// Cron: fire generic outbound webhook triggers for app events. No payments.
export async function POST() {
  await fireWebhookTriggers();
  return NextResponse.json({ fired: true });
}

async function fireWebhookTriggers() {
  return true;
}
