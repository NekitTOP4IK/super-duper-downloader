import { useI18n } from "../i18n/I18nContext";

const REPO = "https://github.com/NekitTOP4IK/super-duper-downloader";

export function Footer() {
  const { t } = useI18n();
  return (
    <footer className="foot">
      <a href={REPO} target="_blank" rel="noreferrer">
        {t("footer.source")}
      </a>
      <span aria-hidden="true">·</span>
      <a href={`${REPO}/blob/main/LICENSE`} target="_blank" rel="noreferrer">
        {t("footer.license")}
      </a>
      <span aria-hidden="true">·</span>
      <span>{t("footer.engines")}</span>
    </footer>
  );
}
