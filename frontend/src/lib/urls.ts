const URL_RE = /https?:\/\/[^\s<>"']+/gi;
const TRAILING = /[.,;:!?)\]}>]+$/;

// Mirrors backend/app/core/urls.py so the counter matches what the server will accept.
export function extractUrls(text: string): string[] {
  const found = new Set<string>();
  for (const match of text.matchAll(URL_RE)) {
    const url = match[0].replace(TRAILING, "");
    try {
      if (new URL(url).host) found.add(url);
    } catch {
      // Not a parseable URL; the server would skip it too.
    }
  }
  return [...found];
}

export function siteOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function shortUrl(url: string): string {
  try {
    const { hostname, pathname } = new URL(url);
    return `${hostname.replace(/^www\./, "")}${pathname === "/" ? "" : pathname}`;
  } catch {
    return url;
  }
}
