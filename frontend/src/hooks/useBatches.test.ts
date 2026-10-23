import { describe, expect, it } from "vitest";
import type { Batch, Job, JobStatus } from "../api/client";
import { type BatchView, countFiles, isFinished, reducer } from "./useBatches";

const batch = (id: string): Batch => ({
  id,
  preset: "best",
  created_at: "2026-01-01T00:00:00Z",
  expires_at: "2026-01-01T02:00:00Z",
});

const job = (id: string, status: JobStatus, batchId = "b1"): Job => ({
  id,
  batch_id: batchId,
  url: `https://example.com/${id}`,
  status,
  parent_id: null,
  title: null,
  engine: null,
  progress: null,
  files: [],
  error: null,
  expires_at: "2026-01-01T02:00:00Z",
});

const view = (id: string, jobs: Job[]): BatchView => ({ batch: batch(id), jobs });

describe("batches reducer", () => {
  it("puts new batches first and replaces known ones", () => {
    let views = reducer([], { type: "snapshot", state: view("b1", [job("j1", "queued")]) });
    views = reducer(views, { type: "snapshot", state: view("b2", []) });
    expect(views.map((item) => item.batch.id)).toEqual(["b2", "b1"]);

    views = reducer(views, { type: "snapshot", state: view("b1", [job("j1", "done")]) });
    expect(views.map((item) => item.batch.id)).toEqual(["b2", "b1"]);
    expect(views[1]?.jobs[0]?.status).toBe("done");
  });

  it("updates a job in place and appends jobs it has not seen", () => {
    let views = [view("b1", [job("j1", "queued"), job("j2", "queued")])];
    views = reducer(views, { type: "job", job: job("j1", "downloading") });
    views = reducer(views, { type: "job", job: job("j3", "queued") });
    expect(views[0]?.jobs.map((item) => [item.id, item.status])).toEqual([
      ["j1", "downloading"],
      ["j2", "queued"],
      ["j3", "queued"],
    ]);
  });

  it("ignores jobs of other batches and removes batches", () => {
    const start = [view("b1", [job("j1", "queued")])];
    expect(reducer(start, { type: "job", job: job("x", "done", "b9") })).toEqual(start);
    expect(reducer(start, { type: "remove", id: "b1" })).toEqual([]);
  });
});

describe("batch progress", () => {
  it("is finished only when every job reached a final state", () => {
    expect(isFinished(view("b1", []))).toBe(false);
    expect(isFinished(view("b1", [job("a", "done"), job("b", "processing")]))).toBe(false);
    expect(isFinished(view("b1", [job("a", "done"), job("b", "failed"), job("c", "expanded")]))).toBe(true);
  });

  it("does not count expanded playlists as files", () => {
    const jobs = [job("p", "expanded"), job("a", "done"), job("b", "failed"), job("c", "queued")];
    expect(countFiles(view("b1", jobs))).toEqual({ done: 1, total: 3 });
  });
});
