import { NextResponse } from "next/server";

// Calendar provider change-feed callback (Google/Office365). No payments.
export async function POST(req: Request) {
  const { provider } = await req.json();
  await handleCalendarCallback(provider);
  return NextResponse.json({ ok: true });
}

async function handleCalendarCallback(provider: string) {
  return provider;
}
