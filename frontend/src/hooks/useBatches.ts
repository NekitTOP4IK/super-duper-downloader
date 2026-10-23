import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { ApiError, type Batch, type BatchState, type Job, api } from "../api/client";
import { read, write } from "../themes/runtime";

const STORAGE_KEY = "sdd.batches";
const TERMINAL = new Set(["done", "failed", "expanded"]);
const RETRY_MS = 5000;

export interface BatchView {
  batch: Batch;
  jobs: Job[];
}

type Action =
  | { type: "snapshot"; state: BatchState }
  | { type: "job"; job: Job }
  | { type: "remove"; id: string };

function upsert(jobs: Job[], job: Job): Job[] {
  const index = jobs.findIndex((item) => item.id === job.id);
  if (index === -1) return [...jobs, job];
  const next = jobs.slice();
  next[index] = job;
  return next;
}

export function reducer(views: BatchView[], action: Action): BatchView[] {
  switch (action.type) {
    case "snapshot": {
      const view = { batch: action.state.batch, jobs: action.state.jobs };
      const exists = views.some((item) => item.batch.id === view.batch.id);
      return exists
        ? views.map((item) => (item.batch.id === view.batch.id ? view : item))
        : [view, ...views];
    }
    case "job":
      return views.map((item) =>
        item.batch.id === action.job.batch_id
          ? { ...item, jobs: upsert(item.jobs, action.job) }
          : item,
      );
    case "remove":
      return views.filter((item) => item.batch.id !== action.id);
  }
}

export function isFinished(view: BatchView): boolean {
  return view.jobs.length > 0 && view.jobs.every((job) => TERMINAL.has(job.status));
}

export function countFiles(view: BatchView): { done: number; total: number } {
  const real = view.jobs.filter((job) => job.status !== "expanded");
  return { done: real.filter((job) => job.status === "done").length, total: real.length };
}

interface Saved {
  id: string;
  expires_at: string;
}

function loadSaved(): Saved[] {
  try {
    const saved = JSON.parse(read(STORAGE_KEY) ?? "[]") as Saved[];
    return saved.filter((item) => Date.parse(item.expires_at) > Date.now());
  } catch {
    return [];
  }
}

export function useBatches() {
  const [views, dispatch] = useReducer(reducer, []);
  const [restored, setRestored] = useState(false);
  const sources = useRef(new Map<string, EventSource>());
  const removed = useRef(new Set<string>());

  const refresh = useCallback(async (id: string): Promise<void> => {
    if (removed.current.has(id)) return;
    try {
      const state = await api.batch(id);
      if (!removed.current.has(id)) dispatch({ type: "snapshot", state });
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        dispatch({ type: "remove", id });
      } else {
        setTimeout(() => void refresh(id), RETRY_MS);
      }
    }
  }, []);

  useEffect(() => {
    const saved = loadSaved().reverse();
    void Promise.allSettled(saved.map(({ id }) => refresh(id))).then(() => setRestored(true));
  }, [refresh]);

  useEffect(() => {
    // Writing before the saved list is restored would wipe it on a slow first load.
    if (!restored) return;
    write(
      STORAGE_KEY,
      JSON.stringify(views.map(({ batch }) => ({ id: batch.id, expires_at: batch.expires_at }))),
    );
  }, [views, restored]);

  useEffect(() => {
    const live = new Set(views.filter((view) => !isFinished(view)).map((view) => view.batch.id));
    for (const [id, source] of sources.current) {
      if (!live.has(id)) {
        source.close();
        sources.current.delete(id);
      }
    }
    for (const id of live) {
      if (sources.current.has(id)) continue;
      const source = new EventSource(api.eventsUrl(id));
      source.addEventListener("snapshot", (event) => {
        dispatch({ type: "snapshot", state: JSON.parse((event as MessageEvent).data) });
      });
      source.addEventListener("job", (event) => {
        dispatch({ type: "job", job: JSON.parse((event as MessageEvent).data) });
      });
      source.onerror = () => {
        // The browser retries on its own unless the server answered with an error status.
        if (source.readyState !== EventSource.CLOSED) return;
        sources.current.delete(id);
        void refresh(id);
      };
      sources.current.set(id, source);
    }
  }, [views, refresh]);

  useEffect(() => {
    const open = sources.current;
    return () => {
      for (const source of open.values()) source.close();
      open.clear();
    };
  }, []);

  const add = useCallback((id: string) => refresh(id), [refresh]);
  const remove = useCallback((id: string) => {
    removed.current.add(id);
    dispatch({ type: "remove", id });
  }, []);

  return { views, add, remove };
}
