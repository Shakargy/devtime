export type Task = { type: string; payload: string; attempts: number };
export type TaskHandler = (payload: string) => Promise<void>;
