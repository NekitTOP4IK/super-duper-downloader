import { type CSSProperties, type KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { useI18n } from "../i18n/I18nContext";
import { DEFAULT_DARK, DEFAULT_LIGHT, type Theme, THEMES, findTheme } from "../themes/palettes";
import { AUTO, FONTS } from "../themes/runtime";
import { useTheme } from "../themes/ThemeContext";

type Direction = "ArrowUp" | "ArrowDown" | "ArrowLeft" | "ArrowRight";

function cardVars(theme: Theme): CSSProperties {
  const p = theme.palette;
  return {
    "--c-bg": p.bg,
    "--c-surface": p.surface,
    "--c-field": p.field,
    "--c-line": p.line,
    "--c-fg": p.fg,
    "--c-strong": p.strong,
    "--c-mute": p.mute,
    "--c-accent": p.accent,
    "--c-ok": p.ok,
    "--c-danger": p.danger,
  } as CSSProperties;
}

// Picks the nearest card in the pressed direction, so arrows behave the same across the
// dark and light grids whatever the column count is at the current width.
function neighbour(cards: HTMLElement[], from: HTMLElement, direction: Direction): HTMLElement | null {
  const a = from.getBoundingClientRect();
  let best: HTMLElement | null = null;
  let bestScore = Infinity;
  for (const card of cards) {
    if (card === from) continue;
    const b = card.getBoundingClientRect();
    const dx = b.left - a.left;
    const dy = b.top - a.top;
    const [main, cross] =
      direction === "ArrowDown" ? [dy, dx] : direction === "ArrowUp" ? [-dy, dx] : direction === "ArrowRight" ? [dx, dy] : [-dx, dy];
    if (main <= 4) continue;
    const score = main + Math.abs(cross) * 3;
    if (score < bestScore) {
      bestScore = score;
      best = card;
    }
  }
  return best;
}

function MiniWindow({ theme }: { theme: Theme }) {
  return (
    <span className="tc-window" aria-hidden="true">
      <span className="tc-line">
        <span className="tc-prompt">~</span> sdd
      </span>
      <span className="tc-panel">
        <span className="tc-field">https://…</span>
        <span className="tc-go" />
      </span>
      <span className="tc-panel tc-bulk">
        <span className="tc-field" />
      </span>
      <span className="tc-status">
        <span className="tc-ok">✓</span>
        <span className="tc-bar" />
      </span>
      {theme.glow ? <span className="tc-glow" /> : null}
    </span>
  );
}

interface Props {
  onClose: () => void;
}

export function ThemePicker({ onClose }: Props) {
  const { t } = useI18n();
  const { preference, font, setPreference, setFont, preview } = useTheme();
  const [query, setQuery] = useState("");
  const dialogRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return THEMES.filter((theme) => !needle || `${theme.name} ${theme.id} ${theme.scheme}`.toLowerCase().includes(needle));
  }, [query]);
  const dark = visible.filter((theme) => theme.scheme === "dark");
  const light = visible.filter((theme) => theme.scheme === "light");

  const cards = () => Array.from(dialogRef.current?.querySelectorAll<HTMLElement>(".theme-card") ?? []);

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    const selected = cards().find((card) => card.dataset.id === preference);
    (selected ?? searchRef.current)?.focus();
    selected?.scrollIntoView({ block: "nearest" });
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = overflow;
      preview(null);
      opener?.focus();
    };
    // Runs once per opening: focus, scroll lock and restoring the previous state on close.
  }, []);

  function choose(id: string) {
    setPreference(id);
    onClose();
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key === "Tab") {
      const focusable = Array.from(
        dialogRef.current?.querySelectorAll<HTMLElement>("button, input, [href]") ?? [],
      ).filter((element) => !element.hasAttribute("disabled"));
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
      return;
    }
    if (!["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(event.key)) return;
    const all = cards();
    const current = document.activeElement as HTMLElement;
    if (current === searchRef.current) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        all[0]?.focus();
      }
      return;
    }
    if (!all.includes(current)) return;
    event.preventDefault();
    const next = neighbour(all, current, event.key as Direction);
    if (next) next.focus();
    else if (event.key === "ArrowUp") searchRef.current?.focus();
  }

  const card = (theme: Theme) => (
    <button
      key={theme.id}
      type="button"
      role="option"
      aria-selected={preference === theme.id}
      className="theme-card"
      data-id={theme.id}
      style={cardVars(theme)}
      onClick={() => choose(theme.id)}
      onFocus={() => preview(theme.id)}
      onMouseEnter={() => preview(theme.id)}
    >
      <MiniWindow theme={theme} />
      <span className="tc-name">{theme.name}</span>
    </button>
  );

  const autoDark = findTheme(DEFAULT_DARK) as Theme;
  const autoLight = findTheme(DEFAULT_LIGHT) as Theme;

  return (
    <div className="picker-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div
        ref={dialogRef}
        className="picker"
        role="dialog"
        aria-modal="true"
        aria-labelledby="picker-title"
        onKeyDown={onKeyDown}
        onMouseLeave={() => preview(null)}
      >
        <div className="picker-head">
          <h2 id="picker-title">
            <span className="mute">~/</span>
            {t("theme.title")}
          </h2>
          <input
            ref={searchRef}
            type="search"
            value={query}
            placeholder={t("theme.filter")}
            aria-label={t("theme.filter")}
            onChange={(event) => setQuery(event.target.value)}
          />
          <button type="button" className="icon" aria-label={t("theme.close")} onClick={onClose}>
            ×
          </button>
        </div>

        <div className="picker-body" role="listbox" aria-labelledby="picker-title">
          {!query ? (
            <button
              type="button"
              role="option"
              aria-selected={preference === AUTO}
              className="theme-card auto"
              data-id={AUTO}
              style={cardVars(autoDark)}
              onClick={() => choose(AUTO)}
              onFocus={() => preview(null)}
              onMouseEnter={() => preview(null)}
            >
              <span className="auto-split" aria-hidden="true">
                <span style={cardVars(autoDark)}>
                  <MiniWindow theme={autoDark} />
                </span>
                <span style={cardVars(autoLight)}>
                  <MiniWindow theme={autoLight} />
                </span>
              </span>
              <span className="tc-name">
                {t("theme.auto")} <span className="tc-sub">· {t("theme.autoHint")}</span>
              </span>
            </button>
          ) : null}

          {dark.length ? <h3>{t("theme.dark")}</h3> : null}
          {dark.length ? <div className="theme-grid">{dark.map(card)}</div> : null}
          {light.length ? <h3>{t("theme.light")}</h3> : null}
          {light.length ? <div className="theme-grid">{light.map(card)}</div> : null}
          {!visible.length ? <p className="mute">{t("theme.none")}</p> : null}
        </div>

        <div className="picker-foot">
          <span className="mute">{t("theme.font")}:</span>
          <span className="fonts" role="group" aria-label={t("theme.font")}>
            {FONTS.map((item) => (
              <button
                key={item.id}
                type="button"
                className="chip"
                aria-pressed={font.id === item.id}
                style={{ fontFamily: item.stack }}
                onClick={() => setFont(item.id)}
              >
                {item.name}
              </button>
            ))}
          </span>
          <span className="mute keys">{t("theme.keys")}</span>
        </div>
      </div>
    </div>
  );
}
