import { describe, expect, it } from "vitest";
import { formatBytes, formatDuration, formatSpeed } from "./format";
import { extractUrls, siteOf } from "./urls";

describe("format", () => {
  it.each([
    [0, "0 B"],
    [1023, "1023 B"],
    [533_504, "521 KB"],
    [52_429, "51.2 KB"],
    [2_202_009, "2.1 MB"],
    [150 * 1024 * 1024, "150 MB"],
  ])("formatBytes(%i) = %s", (bytes, expected) => {
    expect(formatBytes(bytes)).toBe(expected);
  });

  it.each([
    [19, "0:19"],
    [605, "10:05"],
    [3725, "1:02:05"],
    [-3, "0:00"],
  ])("formatDuration(%i) = %s", (seconds, expected) => {
    expect(formatDuration(seconds)).toBe(expected);
  });

  it("formats speed", () => {
    expect(formatSpeed(2_202_009)).toBe("2.1 MB/s");
  });
});

describe("urls", () => {
  it("extracts unique links like the backend", () => {
    const text = `see https://youtu.be/abc, and (https://x.com/a/status/1).
      again https://youtu.be/abc
      ftp://nope.example and https://
      "https://site.example/path?q=1"`;
    expect(extractUrls(text)).toEqual([
      "https://youtu.be/abc",
      "https://x.com/a/status/1",
      "https://site.example/path?q=1",
    ]);
  });

  it("shows a short site name", () => {
    expect(siteOf("https://www.youtube.com/watch?v=1")).toBe("youtube.com");
    expect(siteOf("not a url")).toBe("not a url");
  });
});
