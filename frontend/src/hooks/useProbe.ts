import { useEffect, useState } from "react";
import { ApiError, type MediaInfo, api } from "../api/client";

const DEBOUNCE_MS = 450;
const cache = new Map<string, MediaInfo | ApiError>();

export type ProbeState =
  | { status: "idle" }
  | { status: "loading"; url: string }
  | { status: "ready"; url: string; info: MediaInfo }
  | { status: "error"; url: string; error: ApiError };

function settled(url: string, result: MediaInfo | ApiError): ProbeState {
  return result instanceof ApiError
    ? { status: "error", url, error: result }
    : { status: "ready", url, info: result };
}

export function useProbe(url: string | null): ProbeState {
  const [state, setState] = useState<ProbeState>({ status: "idle" });

  useEffect(() => {
    if (!url) {
      setState({ status: "idle" });
      return;
    }
    const cached = cache.get(url);
    if (cached) {
      setState(settled(url, cached));
      return;
    }
    setState({ status: "loading", url });
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const info = await api.probe(url, controller.signal);
        cache.set(url, info);
        setState(settled(url, info));
      } catch (error) {
        if (controller.signal.aborted) return;
        const failure = error instanceof ApiError ? error : new ApiError(0, "UNKNOWN", String(error));
        // Busy, unreachable or rate-limited servers are worth asking again; a failed extraction is not.
        if (!["BUSY", "OFFLINE", "PROBE_TIMEOUT", "RATE_LIMITED"].includes(failure.code)) cache.set(url, failure);
        setState(settled(url, failure));
      }
    }, DEBOUNCE_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [url]);

  return state;
}
