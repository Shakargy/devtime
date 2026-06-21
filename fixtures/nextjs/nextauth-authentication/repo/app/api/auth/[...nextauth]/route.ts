import NextAuth from "next-auth";

const handler = NextAuth({ providers: [] });

export async function GET(req: Request) {
  return handler(req);
}

export async function POST(req: Request) {
  return handler(req);
}
