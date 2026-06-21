import { Queue } from "bullmq";
import IORedis from "ioredis";

const connection = new IORedis(process.env.REDIS_URL as string);

export const emailQueue = new Queue("emails", { connection });
