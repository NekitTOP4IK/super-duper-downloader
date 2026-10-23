import { describe, expect, it } from "vitest";
import { detectLang, translator } from "./I18nContext";
import { MESSAGES } from "./messages";

describe("detectLang", () => {
  it("keeps a saved choice", () => {
    expect(detectLang("en", ["ru-RU"])).toBe("en");
  });

  it("follows the browser for Russian and falls back to English otherwise", () => {
    expect(detectLang(null, ["ru-RU", "en"])).toBe("ru");
    expect(detectLang(null, ["uk-UA", "ru"])).toBe("en");
    expect(detectLang("de", [])).toBe("en");
  });
});

describe("translator", () => {
  it("picks Russian plural forms", () => {
    const t = translator("ru");
    expect([1, 2, 5, 11, 21, 22, 25].map((n) => t("input.links", { n }))).toEqual([
      "1 ссылка",
      "2 ссылки",
      "5 ссылок",
      "11 ссылок",
      "21 ссылка",
      "22 ссылки",
      "25 ссылок",
    ]);
  });

  it("picks English plural forms and fills variables", () => {
    const t = translator("en");
    expect(t("input.links", { n: 1 })).toBe("1 link");
    expect(t("input.links", { n: 3 })).toBe("3 links");
    expect(t("jobs.summary", { done: 2, total: 7 })).toBe("2 of 7");
  });

  it("has the same keys in every language", () => {
    expect(Object.keys(MESSAGES.en).sort()).toEqual(Object.keys(MESSAGES.ru).sort());
  });
});
