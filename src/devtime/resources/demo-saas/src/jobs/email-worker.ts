import { Worker } from "bullmq";
import IORedis from "ioredis";

const connection = new IORedis(process.env.REDIS_URL as string);

export const emailWorker = new Worker(
  "emails",
  async (job) => {
    await sendEmail(job.data.to, job.data.template);
  },
  { connection }
);

async function sendEmail(to: string, template: string) {
  return { to, template };
}
