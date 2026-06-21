import express from "express";

// Uses Stripe somewhere, but there is no webhook handler in this repo.
const app = express();

app.get("/health", (req, res) => res.json({ ok: true }));

export default app;
