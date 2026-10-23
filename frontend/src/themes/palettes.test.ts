import { describe, expect, it } from "vitest";
import { contrast, mix } from "./color";
import { DEFAULT_DARK, DEFAULT_LIGHT, THEMES, findTheme } from "./palettes";

describe("color helpers", () => {
  it("computes WCAG contrast", () => {
    expect(contrast("#000000", "#ffffff")).toBeCloseTo(21, 5);
    expect(contrast("#777777", "#777777")).toBe(1);
  });

  it("mixes in sRGB", () => {
    expect(mix("#000000", "#ffffff", 0.5)).toBe("#808080");
    expect(mix("#102030", "#102030", 0.3)).toBe("#102030");
  });
});

describe("themes", () => {
  it("have unique ids and resolvable defaults", () => {
    expect(new Set(THEMES.map((t) => t.id)).size).toBe(THEMES.length);
    expect(findTheme(DEFAULT_DARK)?.scheme).toBe("dark");
    expect(findTheme(DEFAULT_LIGHT)?.scheme).toBe("light");
  });

  it.each(THEMES)("$name uses 6-digit hex colors", ({ palette }) => {
    for (const value of Object.values(palette)) expect(value).toMatch(/^#[0-9a-f]{6}$/i);
  });

  // Body text must read comfortably without the glare of near-white on near-black.
  it.each(THEMES)("$name body text is readable but not harsh", ({ palette: p }) => {
    for (const background of [p.bg, p.surface, p.field]) {
      const ratio = contrast(p.fg, background);
      expect(ratio).toBeGreaterThanOrEqual(7);
      expect(ratio).toBeLessThanOrEqual(15);
    }
  });

  it.each(THEMES)("$name secondary and status text meet WCAG AA", ({ palette: p }) => {
    for (const color of [p.mute, p.link, p.ok, p.danger, p.strong]) {
      expect(contrast(color, p.surface)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(color, p.bg)).toBeGreaterThanOrEqual(4.5);
    }
  });

  it.each(THEMES)("$name buttons keep their label readable", ({ palette: p }) => {
    expect(contrast(p.onAccent, p.accent)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(p.onAccent, p.danger)).toBeGreaterThanOrEqual(4.5);
  });
});
