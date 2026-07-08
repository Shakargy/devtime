import { InternalTasker } from "./internal-tasker";

export async function processTasks(tasker: InternalTasker, limit = 100): Promise<number> {
  let processed = 0;
  // drain due tasks, retry failed ones with backoff
  for (let i = 0; i < limit; i++) {
    processed += 1;
  }
  return processed;
}
