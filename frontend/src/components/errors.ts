import type { Translate } from "../i18n/I18nContext";
import { MESSAGES, type MessageKey } from "../i18n/messages";

export function errorText(t: Translate, code: string): string {
  const key = `error.${code}`;
  return key in MESSAGES.ru ? t(key as MessageKey) : t("error.UNKNOWN");
}
