import { NextResponse } from "next/server";

// Cron: clean up stale calendar subscriptions. No billing.
export async function POST() {
  await cleanupCalendarSubscriptions();
  return NextResponse.json({ cleaned: true });
}

async function cleanupCalendarSubscriptions() {
  return true;
}
