import { type ReactNode, createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { type Theme, findTheme } from "./palettes";
import {
  AUTO,
  FONT_KEY,
  type Font,
  THEME_KEY,
  applyTheme,
  read,
  resolveFont,
  resolveTheme,
  systemPrefersLight,
  write,
} from "./runtime";

interface ThemeState {
  preference: string;
  theme: Theme;
  font: Font;
  setPreference: (id: string) => void;
  setFont: (id: string) => void;
  preview: (id: string | null) => void;
}

const ThemeContext = createContext<ThemeState | null>(null);

function usePrefersLight(): boolean {
  const [light, setLight] = useState(systemPrefersLight);
  useEffect(() => {
    if (typeof matchMedia !== "function") return;
    const query = matchMedia("(prefers-color-scheme: light)");
    const update = () => setLight(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return light;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const prefersLight = usePrefersLight();
  const [preference, setPreferenceState] = useState(() => read(THEME_KEY) ?? AUTO);
  const [fontId, setFontId] = useState(() => read(FONT_KEY));
  const [previewId, setPreviewId] = useState<string | null>(null);

  const theme = resolveTheme(preference, prefersLight);
  const font = resolveFont(fontId);
  const shown = (previewId && findTheme(previewId)) || theme;

  useEffect(() => {
    applyTheme(shown, font, { persist: shown === theme });
  }, [shown, theme, font]);

  const setPreference = useCallback((id: string) => {
    setPreferenceState(id);
    setPreviewId(null);
    write(THEME_KEY, id);
  }, []);

  const setFont = useCallback((id: string) => {
    setFontId(id);
    write(FONT_KEY, id);
  }, []);

  const value = useMemo(
    () => ({ preference, theme, font, setPreference, setFont, preview: setPreviewId }),
    [preference, theme, font, setPreference, setFont],
  );
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeState {
  const state = useContext(ThemeContext);
  if (!state) throw new Error("useTheme must be used inside ThemeProvider");
  return state;
}
