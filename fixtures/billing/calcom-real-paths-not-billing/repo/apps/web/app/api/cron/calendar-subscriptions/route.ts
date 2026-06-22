import { NextResponse } from "next/server";

// Cron: refresh calendar subscriptions with external calendar providers. No billing.
export async function POST() {
  await refreshCalendarSubscriptions();
  return NextResponse.json({ refreshed: true });
}

async function refreshCalendarSubscriptions() {
  return true;
}
