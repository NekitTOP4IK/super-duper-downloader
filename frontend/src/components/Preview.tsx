import { type ReactNode, useState } from "react";
import type { MediaInfo } from "../api/client";
import { useI18n } from "../i18n/I18nContext";
import { formatDuration } from "../lib/format";
import { siteOf } from "../lib/urls";

interface Props {
  info: MediaInfo;
  maxItems: number;
  children: ReactNode;
}

export function Preview({ info, maxItems, children }: Props) {
  const { t } = useI18n();
  const [thumbFailed, setThumbFailed] = useState(false);
  const meta = [
    info.uploader,
    info.duration ? formatDuration(info.duration) : null,
    siteOf(info.url),
  ].filter(Boolean);
  const count = info.count ?? info.entries.length;

  return (
    <div className="preview">
      {info.thumbnail && !thumbFailed ? (
        <img
          className="thumb"
          src={info.thumbnail}
          alt=""
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={() => setThumbFailed(true)}
        />
      ) : (
        <div className="thumb thumb-empty" aria-hidden="true">
          {info.kind === "playlist" ? "≡" : "▶"}
        </div>
      )}
      <div className="preview-body">
        <div className="preview-title">{info.title ?? siteOf(info.url)}</div>
        <div className="mute">{meta.join(" · ")}</div>
        {info.kind === "playlist" ? (
          <div className="mute">
            {t("input.playlist", { n: count })}
            {count > maxItems ? ` · ${t("input.playlistLimit", { max: maxItems })}` : ""}
          </div>
        ) : null}
        <div className="row">{children}</div>
      </div>
    </div>
  );
}
