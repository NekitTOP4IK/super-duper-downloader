import { useI18n } from "../i18n/I18nContext";
import { LANGS } from "../i18n/messages";
import { AUTO } from "../themes/runtime";
import { useTheme } from "../themes/ThemeContext";

export function Header({ onOpenThemes }: { onOpenThemes: () => void }) {
  const { t, lang, setLang } = useI18n();
  const { theme, preference } = useTheme();
  const p = theme.palette;

  return (
    <header className="head">
      <a className="brand" href="/" aria-label="super-duper-downloader">
        <span className="brand-prompt">~/</span>
        <span className="brand-full">super-duper-downloader</span>
        <span className="brand-short">sdd</span>
        <span className="cursor" aria-hidden="true" />
      </a>
      <nav className="head-tools">
        <span className="langs" role="group" aria-label={t("lang.switch")}>
          {LANGS.map((code) => (
            <button
              key={code}
              type="button"
              className="link-button"
              aria-pressed={lang === code}
              onClick={() => setLang(code)}
            >
              {code}
            </button>
          ))}
        </span>
        <button type="button" className="theme-button" onClick={onOpenThemes} aria-keyshortcuts="t">
          <span className="dots" aria-hidden="true">
            {[p.accent, p.ok, p.danger].map((color) => (
              <i key={color} style={{ background: color }} />
            ))}
          </span>
          <span className="theme-name">
            {preference === AUTO ? `${t("theme.auto")} · ${theme.name}` : theme.name}
          </span>
          <kbd>t</kbd>
        </button>
      </nav>
    </header>
  );
}
