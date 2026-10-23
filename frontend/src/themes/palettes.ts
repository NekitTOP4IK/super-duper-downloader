import { contrast, mix } from "./color";

export type Scheme = "dark" | "light";

export interface Palette {
  bg: string;
  surface: string;
  field: string;
  line: string;
  fg: string;
  strong: string;
  mute: string;
  accent: string;
  link: string;
  ok: string;
  warn: string;
  danger: string;
  onAccent: string;
}

export interface Theme {
  id: string;
  name: string;
  scheme: Scheme;
  source: string;
  glow?: boolean;
  palette: Palette;
}

// Colors come from each scheme's official palette (see `source`). Where a scheme has no shade
// for a role, the value is mixed from its own colors. The phosphor themes are our own, modelled
// on amber and green monochrome monitors. normalize() then nudges lightness until every role
// meets its contrast target, keeping the hue.
const PALETTES: Theme[] = [
  {
    id: "tokyo-night",
    name: "Tokyo Night",
    scheme: "dark",
    source: "https://github.com/folke/tokyonight.nvim",
    palette: {
      bg: "#1a1b26",
      surface: "#1f2335",
      field: "#16161e",
      line: "#292e42",
      fg: "#a9b1d6",
      strong: "#c0caf5",
      mute: "#737aa2",
      accent: "#7aa2f7",
      link: "#7dcfff",
      ok: "#9ece6a",
      warn: "#e0af68",
      danger: "#f7768e",
      onAccent: "#16161e",
    },
  },
  {
    id: "tokyo-storm",
    name: "Tokyo Storm",
    scheme: "dark",
    source: "https://github.com/folke/tokyonight.nvim",
    palette: {
      bg: "#24283b",
      surface: "#1f2335",
      field: "#1b1e2d",
      line: "#3b4261",
      fg: "#a9b1d6",
      strong: "#c0caf5",
      mute: "#737aa2",
      accent: "#7aa2f7",
      link: "#7dcfff",
      ok: "#9ece6a",
      warn: "#e0af68",
      danger: "#f7768e",
      onAccent: "#1b1e2d",
    },
  },
  {
    id: "tokyo-moon",
    name: "Tokyo Moon",
    scheme: "dark",
    source: "https://github.com/folke/tokyonight.nvim",
    palette: {
      bg: "#222436",
      surface: "#1e2030",
      field: "#191b29",
      line: "#2f334d",
      fg: "#c8d3f5",
      strong: mix("#c8d3f5", "#ffffff", 0.3),
      mute: "#828bb8",
      accent: "#82aaff",
      link: "#86e1fc",
      ok: "#c3e88d",
      warn: "#ffc777",
      danger: "#ff757f",
      onAccent: "#191b29",
    },
  },
  {
    id: "catppuccin-mocha",
    name: "Catppuccin Mocha",
    scheme: "dark",
    source: "https://github.com/catppuccin/catppuccin",
    palette: {
      bg: "#1e1e2e",
      surface: "#181825",
      field: "#11111b",
      line: "#313244",
      fg: "#bac2de",
      strong: "#cdd6f4",
      mute: "#9399b2",
      accent: "#89b4fa",
      link: "#89dceb",
      ok: "#a6e3a1",
      warn: "#f9e2af",
      danger: "#f38ba8",
      onAccent: "#11111b",
    },
  },
  {
    id: "catppuccin-macchiato",
    name: "Catppuccin Macchiato",
    scheme: "dark",
    source: "https://github.com/catppuccin/catppuccin",
    palette: {
      bg: "#24273a",
      surface: "#1e2030",
      field: "#181926",
      line: "#363a4f",
      fg: "#b8c0e0",
      strong: "#cad3f5",
      mute: "#939ab7",
      accent: "#8aadf4",
      link: "#91d7e3",
      ok: "#a6da95",
      warn: "#eed49f",
      danger: "#ed8796",
      onAccent: "#181926",
    },
  },
  {
    id: "kanagawa-wave",
    name: "Kanagawa Wave",
    scheme: "dark",
    source: "https://github.com/rebelot/kanagawa.nvim",
    palette: {
      bg: "#1f1f28",
      surface: "#1a1a22",
      field: "#16161d",
      line: "#2a2a37",
      fg: "#dcd7ba",
      strong: mix("#dcd7ba", "#ffffff", 0.3),
      mute: "#938aa9",
      accent: "#7e9cd8",
      link: "#7fb4ca",
      ok: "#98bb6c",
      warn: "#e6c384",
      danger: "#e46876",
      onAccent: "#16161d",
    },
  },
  {
    id: "kanagawa-dragon",
    name: "Kanagawa Dragon",
    scheme: "dark",
    source: "https://github.com/rebelot/kanagawa.nvim",
    palette: {
      bg: "#181616",
      surface: "#1d1c19",
      field: "#12120f",
      line: "#282727",
      fg: "#c5c9c5",
      strong: mix("#c5c9c5", "#ffffff", 0.3),
      mute: "#a6a69c",
      accent: "#8ba4b0",
      link: "#8ea4a2",
      ok: "#87a987",
      warn: "#c4b28a",
      danger: "#c4746e",
      onAccent: "#12120f",
    },
  },
  {
    id: "rose-pine",
    name: "Rosé Pine",
    scheme: "dark",
    source: "https://rosepinetheme.com",
    palette: {
      bg: "#191724",
      surface: "#1f1d2e",
      field: mix("#191724", "#000000", 0.2),
      line: "#26233a",
      fg: mix("#e0def4", "#908caa", 0.15),
      strong: "#e0def4",
      mute: "#908caa",
      accent: "#c4a7e7",
      link: "#9ccfd8",
      ok: "#9ccfd8",
      warn: "#f6c177",
      danger: "#eb6f92",
      onAccent: "#191724",
    },
  },
  {
    id: "rose-pine-moon",
    name: "Rosé Pine Moon",
    scheme: "dark",
    source: "https://rosepinetheme.com",
    palette: {
      bg: "#232136",
      surface: "#2a273f",
      field: mix("#232136", "#000000", 0.2),
      line: "#393552",
      fg: mix("#e0def4", "#908caa", 0.15),
      strong: "#e0def4",
      mute: "#908caa",
      accent: "#c4a7e7",
      link: "#9ccfd8",
      ok: "#9ccfd8",
      warn: "#f6c177",
      danger: "#eb6f92",
      onAccent: "#232136",
    },
  },
  {
    id: "everforest",
    name: "Everforest",
    scheme: "dark",
    source: "https://github.com/sainnhe/everforest",
    palette: {
      bg: "#2d353b",
      surface: "#343f44",
      field: "#232a2e",
      line: "#475258",
      fg: "#d3c6aa",
      strong: mix("#d3c6aa", "#ffffff", 0.3),
      mute: "#9da9a0",
      accent: "#a7c080",
      link: "#7fbbb3",
      ok: "#83c092",
      warn: "#dbbc7f",
      danger: "#e67e80",
      onAccent: "#232a2e",
    },
  },
  {
    id: "gruvbox-material",
    name: "Gruvbox Material",
    scheme: "dark",
    source: "https://github.com/sainnhe/gruvbox-material",
    palette: {
      bg: "#282828",
      surface: "#32302f",
      field: "#1b1b1b",
      line: "#45403d",
      fg: "#d4be98",
      strong: "#ddc7a1",
      mute: "#a89984",
      accent: "#7daea3",
      link: "#89b482",
      ok: "#a9b665",
      warn: "#d8a657",
      danger: "#ea6962",
      onAccent: "#1b1b1b",
    },
  },
  {
    id: "nord",
    name: "Nord",
    scheme: "dark",
    source: "https://www.nordtheme.com",
    palette: {
      bg: "#2e3440",
      surface: "#3b4252",
      field: mix("#2e3440", "#000000", 0.18),
      line: "#434c5e",
      fg: "#d8dee9",
      strong: "#eceff4",
      mute: mix("#d8dee9", "#3b4252", 0.38),
      accent: "#88c0d0",
      link: "#8fbcbb",
      ok: "#a3be8c",
      warn: "#ebcb8b",
      danger: "#bf616a",
      onAccent: "#2e3440",
    },
  },
  {
    id: "carbon",
    name: "Carbon",
    scheme: "dark",
    source: "https://github.com/nyoom-engineering/oxocarbon.nvim",
    palette: {
      bg: "#161616",
      surface: "#262626",
      field: "#131313",
      line: "#393939",
      fg: mix("#161616", "#ffffff", 0.82),
      strong: "#f2f4f8",
      mute: "#a8a8a8",
      accent: "#78a9ff",
      link: "#33b1ff",
      ok: "#42be65",
      warn: "#3ddbd9",
      danger: "#ee5396",
      onAccent: "#161616",
    },
  },
  {
    id: "dracula",
    name: "Dracula",
    scheme: "dark",
    source: "https://draculatheme.com",
    palette: {
      bg: "#282a36",
      surface: mix("#282a36", "#44475a", 0.35),
      field: mix("#282a36", "#000000", 0.2),
      line: "#44475a",
      fg: mix("#f8f8f2", "#282a36", 0.12),
      strong: "#f8f8f2",
      mute: mix("#6272a4", "#f8f8f2", 0.3),
      accent: "#bd93f9",
      link: "#8be9fd",
      ok: "#50fa7b",
      warn: "#f1fa8c",
      danger: "#ff5555",
      onAccent: "#282a36",
    },
  },
  {
    id: "flexoki-dark",
    name: "Flexoki Dark",
    scheme: "dark",
    source: "https://stephango.com/flexoki",
    palette: {
      bg: "#100f0f",
      surface: "#1c1b1a",
      field: "#100f0f",
      line: "#282726",
      fg: "#cecdc3",
      strong: "#e6e4d9",
      mute: "#878580",
      accent: "#4385be",
      link: "#3aa99f",
      ok: "#879a39",
      warn: "#d0a215",
      danger: "#d14d41",
      onAccent: "#100f0f",
    },
  },
  {
    id: "phosphor-amber",
    name: "Phosphor Amber",
    scheme: "dark",
    source: "https://en.wikipedia.org/wiki/Monochrome_monitor",
    glow: true,
    palette: {
      bg: "#110d07",
      surface: "#17120a",
      field: "#0c0905",
      line: "#3a2c15",
      fg: "#e8a948",
      strong: "#ffc56b",
      mute: "#a87a3a",
      accent: "#ffb000",
      link: "#ffc56b",
      ok: "#e8c85a",
      warn: "#ffd88a",
      danger: "#ff7350",
      onAccent: "#110d07",
    },
  },
  {
    id: "phosphor-green",
    name: "Phosphor Green",
    scheme: "dark",
    source: "https://en.wikipedia.org/wiki/Monochrome_monitor",
    glow: true,
    palette: {
      bg: "#08100a",
      surface: "#0c170e",
      field: "#050b06",
      line: "#1c3321",
      fg: "#6fd47e",
      strong: "#a3f0ad",
      mute: "#4e9a5a",
      accent: "#52e868",
      link: "#a3f0ad",
      ok: "#a3f0ad",
      warn: "#d9e36a",
      danger: "#ff7a6b",
      onAccent: "#08100a",
    },
  },
  {
    id: "tokyo-day",
    name: "Tokyo Day",
    scheme: "light",
    source: "https://github.com/folke/tokyonight.nvim",
    palette: {
      bg: "#e1e2e7",
      surface: mix("#e1e2e7", "#ffffff", 0.45),
      field: "#ffffff",
      line: "#c4c8da",
      fg: "#3760bf",
      strong: "#3760bf",
      mute: "#68709a",
      accent: "#2e7de9",
      link: "#007197",
      ok: "#587539",
      warn: "#8c6c3e",
      danger: "#c64343",
      onAccent: "#ffffff",
    },
  },
  {
    id: "catppuccin-latte",
    name: "Catppuccin Latte",
    scheme: "light",
    source: "https://github.com/catppuccin/catppuccin",
    palette: {
      bg: "#eff1f5",
      surface: "#e6e9ef",
      field: "#ffffff",
      line: "#ccd0da",
      fg: "#5c5f77",
      strong: "#4c4f69",
      mute: "#6c6f85",
      accent: "#1e66f5",
      link: "#1e66f5",
      ok: "#40a02b",
      warn: "#df8e1d",
      danger: "#d20f39",
      onAccent: "#eff1f5",
    },
  },
  {
    id: "rose-pine-dawn",
    name: "Rosé Pine Dawn",
    scheme: "light",
    source: "https://rosepinetheme.com",
    palette: {
      bg: "#faf4ed",
      surface: "#fffaf3",
      field: "#fffaf3",
      line: "#f2e9e1",
      fg: mix("#464261", "#797593", 0.15),
      strong: "#464261",
      mute: "#797593",
      accent: "#286983",
      link: "#286983",
      ok: "#56949f",
      warn: "#ea9d34",
      danger: "#b4637a",
      onAccent: "#faf4ed",
    },
  },
  {
    id: "kanagawa-lotus",
    name: "Kanagawa Lotus",
    scheme: "light",
    source: "https://github.com/rebelot/kanagawa.nvim",
    palette: {
      bg: "#f2ecbc",
      surface: "#e5ddb0",
      field: mix("#f2ecbc", "#ffffff", 0.5),
      line: "#dcd5ac",
      fg: "#545464",
      strong: "#43436c",
      mute: "#716e61",
      accent: "#4d699b",
      link: "#4e8ca2",
      ok: "#6f894e",
      warn: "#cc6d00",
      danger: "#c84053",
      onAccent: "#f2ecbc",
    },
  },
  {
    id: "everforest-light",
    name: "Everforest Light",
    scheme: "light",
    source: "https://github.com/sainnhe/everforest",
    palette: {
      bg: "#fdf6e3",
      surface: "#f4f0d9",
      field: mix("#fdf6e3", "#ffffff", 0.5),
      line: "#e6e2cc",
      fg: "#5c6a72",
      strong: "#5c6a72",
      mute: "#829181",
      accent: "#3a94c5",
      link: "#35a77c",
      ok: "#8da101",
      warn: "#dfa000",
      danger: "#f85552",
      onAccent: "#fdf6e3",
    },
  },
  {
    id: "flexoki-light",
    name: "Flexoki Light",
    scheme: "light",
    source: "https://stephango.com/flexoki",
    palette: {
      bg: "#fffcf0",
      surface: "#f2f0e5",
      field: "#fffcf0",
      line: "#e6e4d9",
      fg: "#403e3c",
      strong: "#100f0f",
      mute: "#6f6e69",
      accent: "#205ea6",
      link: "#24837b",
      ok: "#66800b",
      warn: "#ad8301",
      danger: "#af3029",
      onAccent: "#fffcf0",
    },
  },
];

const BODY_MIN = 7;
const GLARE_MAX = 15;
const TEXT_MIN = 4.5;

function minContrast(color: string, backgrounds: string[]): number {
  return Math.min(...backgrounds.map((background) => contrast(color, background)));
}

function shift(color: string, toward: string, accept: (candidate: string) => boolean): string {
  for (let step = 0; step <= 50; step++) {
    const candidate = mix(color, toward, step / 50);
    if (accept(candidate)) return candidate;
  }
  return toward;
}

function normalize(theme: Theme): Theme {
  const p = { ...theme.palette };
  const away = theme.scheme === "dark" ? "#ffffff" : "#000000";
  const grounds = [p.bg, p.surface, p.field];
  const readable = (min: number) => (c: string) => minContrast(c, grounds) >= min;

  p.fg = shift(p.fg, away, readable(BODY_MIN));
  p.fg = shift(p.fg, p.bg, (c) => Math.max(...grounds.map((g) => contrast(c, g))) <= GLARE_MAX);
  p.strong = shift(p.strong, away, readable(BODY_MIN));
  p.strong = shift(p.strong, p.bg, (c) => Math.max(...grounds.map((g) => contrast(c, g))) <= GLARE_MAX + 2);
  for (const role of ["mute", "link", "ok", "warn", "danger"] as const) {
    p[role] = shift(p[role], away, readable(TEXT_MIN));
  }
  const onBest = [p.onAccent, p.bg, p.field, p.strong].sort(
    (a, b) => Math.min(contrast(b, p.accent), contrast(b, p.danger)) - Math.min(contrast(a, p.accent), contrast(a, p.danger)),
  )[0] as string;
  p.onAccent = onBest;
  const labelAway = contrast(onBest, "#000000") > contrast(onBest, "#ffffff") ? "#000000" : "#ffffff";
  p.accent = shift(p.accent, labelAway, (c) => contrast(onBest, c) >= TEXT_MIN);
  p.danger = shift(p.danger, labelAway, (c) => contrast(onBest, c) >= TEXT_MIN && readable(TEXT_MIN)(c));
  return { ...theme, palette: p };
}

export const THEMES: Theme[] = PALETTES.map(normalize);

export const DEFAULT_DARK = "tokyo-night";
export const DEFAULT_LIGHT = "tokyo-day";

export function findTheme(id: string): Theme | undefined {
  return THEMES.find((theme) => theme.id === id);
}
