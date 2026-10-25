import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DEFAULT_LIMITS, type Limits } from "../api/client";
import { I18nProvider } from "../i18n/I18nContext";
import { InputPanel } from "./InputPanel";

function setup(onSubmit = vi.fn().mockResolvedValue(undefined), limits: Limits = DEFAULT_LIMITS) {
  localStorage.setItem("sdd.lang", "en");
  render(
    <I18nProvider>
      <InputPanel limits={limits} onSubmit={onSubmit} />
    </I18nProvider>,
  );
  return { onSubmit, user: userEvent.setup() };
}

function mockProbe(body: object, status = 200) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }),
  );
}

afterEach(() => vi.restoreAllMocks());

describe("InputPanel", () => {
  it("probes a pasted link and offers only the presets the media has", async () => {
    mockProbe({
      kind: "single",
      url: "https://youtu.be/a",
      title: "Me at the zoo",
      thumbnail: null,
      duration: 19,
      uploader: "jawed",
      presets: ["best", "audio"],
      count: null,
      entries: [],
    });
    const { onSubmit, user } = setup();
    await user.type(screen.getByRole("textbox"), "https://youtu.be/a");

    expect(await screen.findByText("Me at the zoo")).toBeInTheDocument();
    expect(screen.getByText("jawed · 0:19 · youtu.be")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "720" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "audio" }));
    await user.click(screen.getByRole("button", { name: "download" }));
    expect(onSubmit).toHaveBeenCalledWith(["https://youtu.be/a"], "audio");
    await waitFor(() => expect(screen.getByRole("textbox")).toHaveValue(""));
  });

  it("shows the approximate size of each quality it knows", async () => {
    mockProbe({
      kind: "single",
      url: "https://youtu.be/b",
      title: "Mob Rap",
      thumbnail: null,
      duration: 267,
      uploader: null,
      presets: ["best", "720", "audio"],
      sizes: { best: 305043934, "720": 90595025 },
      count: null,
      entries: [],
    });
    const { user } = setup();
    await user.type(screen.getByRole("textbox"), "https://youtu.be/b");

    expect(await screen.findByRole("button", { name: "best ~291 MB" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "720 ~86.4 MB" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "audio" })).toBeInTheDocument();
  });

  it("says how many files a post with several videos holds", async () => {
    mockProbe({
      kind: "single",
      url: "https://www.instagram.com/p/a/",
      title: "Post",
      thumbnail: null,
      duration: null,
      uploader: null,
      presets: ["best", "audio"],
      count: 3,
      entries: [],
    });
    const { user } = setup();
    await user.type(screen.getByRole("textbox"), "https://www.instagram.com/p/a/");
    expect(await screen.findByText("3 files")).toBeInTheDocument();
  });

  it("shows why a link cannot be downloaded", async () => {
    mockProbe({ detail: { code: "PRIVATE", message: "login" } }, 422);
    const { user } = setup();
    await user.type(screen.getByRole("textbox"), "https://site.example/p/1");
    expect(await screen.findByText(/private content or login required/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "download" })).not.toBeInTheDocument();
  });

  it("switches to bulk mode when several links are pasted", async () => {
    const { onSubmit, user } = setup();
    const input = screen.getByRole("textbox");
    fireEvent.paste(input, {
      clipboardData: { getData: () => "https://a.example/1\nhttps://b.example/2 https://a.example/1" },
    });

    const area = await screen.findByRole("textbox");
    expect(area.tagName).toBe("TEXTAREA");
    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "true");
    expect(screen.getByText("2 links")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "1080" }));
    await user.click(screen.getByRole("button", { name: "download 2" }));
    expect(onSubmit).toHaveBeenCalledWith(["https://a.example/1", "https://b.example/2"], "1080");
  });

  it("offers a GIF of every link in bulk mode", async () => {
    const { onSubmit, user } = setup();
    fireEvent.paste(screen.getByRole("textbox"), {
      clipboardData: { getData: () => "https://x.com/a/status/1\nhttps://x.com/b/status/2" },
    });

    await user.click(await screen.findByRole("button", { name: "gif" }));
    await user.click(screen.getByRole("button", { name: "download 2" }));
    expect(onSubmit).toHaveBeenCalledWith(
      ["https://x.com/a/status/1", "https://x.com/b/status/2"],
      "gif",
    );
  });

  it("loads links from a .txt file into bulk mode", async () => {
    const { user } = setup();
    const file = new File(["https://a.example/1\nhttps://b.example/2\nhttps://c.example/3\n"], "links.txt", {
      type: "text/plain",
    });
    const picker = document.querySelector('input[type="file"]') as HTMLInputElement;
    await act(async () => {
      await user.upload(picker, file);
    });
    expect(await screen.findByText("3 links")).toBeInTheDocument();
    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "true");
  });

  it("takes no more links than the server allows", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const { user } = setup(onSubmit, { ...DEFAULT_LIMITS, max_batch_urls: 3 });
    await user.click(screen.getByRole("switch"));
    const text = Array.from({ length: 5 }, (_, i) => `https://x.example/${i}`).join("\n");
    fireEvent.change(screen.getByRole("textbox"), { target: { value: text } });
    expect(screen.getByText(/5 links · only the first 3 will be taken/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "download 3" }));
    expect(onSubmit.mock.calls[0]?.[0]).toHaveLength(3);
  });

  it("reports server errors from submitting", async () => {
    const { ApiError } = await import("../api/client");
    const { user } = setup(vi.fn().mockRejectedValue(new ApiError(503, "BUSY", "busy")));
    await user.click(screen.getByRole("switch"));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "https://a.example/1" } });
    await user.click(screen.getByRole("button", { name: "download 1" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("the server is busy");
  });
});
