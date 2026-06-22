import { NextResponse } from "next/server";

// Returns the employment job-title / job-role taxonomy. No queues or workers.
export async function GET() {
  return NextResponse.json([
    { jobTitle: "Engineer", jobRole: "ic" },
    { jobTitle: "Manager", jobRole: "lead" },
  ]);
}
