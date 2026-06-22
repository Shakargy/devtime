import jwt from "jsonwebtoken";

// Signs a single-use invitation token for inviting a new teammate by email.
export function createInvitationToken(email: string): string {
  return jwt.sign({ invite: email }, process.env.INVITE_SECRET as string, {
    expiresIn: "7d",
  });
}

export function verifyInvitation(token: string) {
  return jwt.verify(token, process.env.INVITE_SECRET as string);
}
