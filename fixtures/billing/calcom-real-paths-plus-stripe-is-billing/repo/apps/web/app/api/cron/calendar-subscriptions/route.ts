import { NextResponse } from "next/server";

// Generic calendar subscription cron. No billing.
export async function POST() {
  return NextResponse.json({ refreshed: true });
}
