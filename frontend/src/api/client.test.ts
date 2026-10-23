import { afterEach, describe, expect, it, vi } from "vitest";
import { type ApiError, api } from "./client";

function respond(status: number, body: string, type = "text/plain") {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(body, { status, headers: { "Content-Type": type } }));
}

async function failure(): Promise<ApiError> {
  return api.limits().then(
    () => {
      throw new Error("expected a failure");
    },
    (error: ApiError) => error,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("api errors", () => {
  it("keeps the code the API sends", async () => {
    respond(503, JSON.stringify({ detail: { code: "BUSY", message: "busy" } }), "application/json");
    expect((await failure()).code).toBe("BUSY");
  });

  it.each([502, 503, 504])("treats a bare %i from the proxy as an unreachable server", async (status) => {
    respond(status, "");
    expect((await failure()).code).toBe("OFFLINE");
  });

  it("treats a failed request as an unreachable server", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
    expect((await failure()).code).toBe("OFFLINE");
  });

  it("reports other unexpected answers as unknown", async () => {
    respond(500, "Internal Server Error");
    expect((await failure()).code).toBe("UNKNOWN");
  });
});
