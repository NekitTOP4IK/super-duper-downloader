import { DEFAULT_DARK, DEFAULT_LIGHT, type Palette, type Theme, findTheme } from "./palettes";

export interface Font {
  id: string;
  name: string;
  stack: string;
}

export const FONTS: Font[] = [
  { id: "jetbrains-mono", name: "JetBrains Mono", stack: '"JetBrains Mono", monospace' },
  { id: "ibm-plex-mono", name: "IBM Plex Mono", stack: '"IBM Plex Mono", monospace' },
  { id: "geist-mono", name: "Geist Mono", stack: '"Geist Mono", monospace' },
  { id: "fira-code", name: "Fira Code", stack: '"Fira Code", monospace' },
];

export const AUTO = "auto";
export const THEME_KEY = "sdd.theme";
export const FONT_KEY = "sdd.font";
// Read by public/boot.js before the bundle loads, so the first paint already has the right colors.
export const BOOT_KEY = "sdd.boot";

const VARS: Record<keyof Palette, string> = {
  bg: "--bg",
  surface: "--surface",
  field: "--field",
  line: "--line",
  fg: "--fg",
  strong: "--strong",
  mute: "--mute",
  accent: "--accent",
  link: "--link",
  ok: "--ok",
  warn: "--warn",
  danger: "--danger",
  onAccent: "--on-accent",
};

export function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function write(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // Private mode or blocked storage: the choice just won't survive a reload.
  }
}

export function systemPrefersLight(): boolean {
  return typeof matchMedia === "function" && matchMedia("(prefers-color-scheme: light)").matches;
}

export function resolveTheme(preference: string, prefersLight: boolean): Theme {
  const fallback = prefersLight ? DEFAULT_LIGHT : DEFAULT_DARK;
  const id = preference === AUTO ? fallback : preference;
  return findTheme(id) ?? (findTheme(fallback) as Theme);
}

export function resolveFont(id: string | null): Font {
  return FONTS.find((font) => font.id === id) ?? (FONTS[0] as Font);
}

export function themeVars(theme: Theme, font: Font): Record<string, string> {
  const vars: Record<string, string> = { "--font": font.stack };
  for (const [role, name] of Object.entries(VARS)) vars[name] = theme.palette[role as keyof Palette];
  return vars;
}

export function applyTheme(theme: Theme, font: Font, { persist }: { persist: boolean }): void {
  const root = document.documentElement;
  const vars = themeVars(theme, font);
  for (const [name, value] of Object.entries(vars)) root.style.setProperty(name, value);
  root.dataset.scheme = theme.scheme;
  root.dataset.glow = theme.glow ? "on" : "off";
  root.style.colorScheme = theme.scheme;
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", theme.palette.bg);
  if (persist) {
    write(BOOT_KEY, JSON.stringify({ vars, scheme: theme.scheme, glow: Boolean(theme.glow) }));
  }
}
