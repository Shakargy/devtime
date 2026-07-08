import type { Task, TaskHandler } from "./types";

// Minimal internal task runner: tasks are persisted and picked up by a cron-driven
// processor. Modeled on real-world custom taskers (no BullMQ/Celery dependency).
export class InternalTasker {
  private handlers = new Map<string, TaskHandler>();

  register(type: string, handler: TaskHandler): void {
    this.handlers.set(type, handler);
  }

  async create(type: string, payload: string): Promise<string> {
    const task: Task = { type, payload, attempts: 0 };
    return this.enqueue(task);
  }

  private async enqueue(task: Task): Promise<string> {
    // persist task for the processor to pick up
    return `${task.type}:${Date.now()}`;
  }
}
