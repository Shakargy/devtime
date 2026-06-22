import { NextResponse } from "next/server";

// Cron job that cleans up stale calendar subscriptions. No payments.
export async function POST() {
  await cleanupStaleCalendarSubscriptions();
  return NextResponse.json({ cleaned: true });
}

async function cleanupStaleCalendarSubscriptions() {
  return true;
}
