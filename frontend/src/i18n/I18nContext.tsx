import { type ReactNode, createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { read, write } from "../themes/runtime";
import { LANGS, type Lang, MESSAGES, type MessageKey } from "./messages";

const LANG_KEY = "sdd.lang";

type Vars = Record<string, string | number>;
export type Translate = (key: MessageKey, vars?: Vars) => string;

interface I18nState {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: Translate;
}

const I18nContext = createContext<I18nState | null>(null);

export function detectLang(saved: string | null, preferred: readonly string[]): Lang {
  if (saved && (LANGS as string[]).includes(saved)) return saved as Lang;
  const first = preferred.map((tag) => tag.toLowerCase().split("-")[0]).find(Boolean);
  return first === "ru" ? "ru" : "en";
}

export function translator(lang: Lang): Translate {
  const rules = new Intl.PluralRules(lang);
  return (key, vars = {}) => {
    const entry = MESSAGES[lang][key];
    const template =
      typeof entry === "string"
        ? entry
        : (entry[rules.select(Number(vars.n ?? 0)) as keyof typeof entry] ?? entry.other);
    return template.replace(/\{(\w+)\}/g, (match, name: string) =>
      name in vars ? String(vars[name]) : match,
    );
  };
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() =>
    detectLang(read(LANG_KEY), typeof navigator === "undefined" ? [] : navigator.languages),
  );

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    write(LANG_KEY, next);
  }, []);

  const value = useMemo(() => ({ lang, setLang, t: translator(lang) }), [lang, setLang]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nState {
  const state = useContext(I18nContext);
  if (!state) throw new Error("useI18n must be used inside I18nProvider");
  return state;
}
