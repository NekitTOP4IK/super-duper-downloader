import { type ClipboardEvent, type KeyboardEvent, useEffect, useRef, useState } from "react";
import { ApiError, type Limits, PRESETS, type Preset } from "../api/client";
import { useProbe } from "../hooks/useProbe";
import { useI18n } from "../i18n/I18nContext";
import { extractUrls } from "../lib/urls";
import { errorText } from "./errors";
import { Presets } from "./Presets";
import { Preview } from "./Preview";
import { Spinner } from "./Spinner";

const MAX_FILE_BYTES = 1_000_000;
const RETRIABLE = new Set(["BUSY", "OFFLINE", "PROBE_TIMEOUT", "RATE_LIMITED", "NETWORK", "UNKNOWN"]);

interface Props {
  limits: Limits;
  onSubmit: (urls: string[], preset: Preset) => Promise<void>;
}

export function InputPanel({ limits, onSubmit }: Props) {
  const { t } = useI18n();
  const maxLinks = limits.max_batch_urls;
  const [bulk, setBulk] = useState(false);
  const [single, setSingle] = useState("");
  const [bulkText, setBulkText] = useState("");
  const [preset, setPreset] = useState<Preset>("best");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const areaRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const shownBulk = useRef(bulk);

  const singleUrl = extractUrls(single)[0] ?? null;
  const probe = useProbe(bulk ? null : singleUrl);
  const bulkUrls = extractUrls(bulkText);

  const offered =
    probe.status === "ready" && probe.info.kind === "single" && probe.info.presets.length
      ? probe.info.presets
      : PRESETS;
  const chosen = offered.includes(preset) ? preset : (offered[0] as Preset);

  useEffect(() => {
    // No autofocus on load: it would swallow the "t" shortcut, and paste works page-wide anyway.
    if (shownBulk.current !== bulk) (bulk ? areaRef : inputRef).current?.focus();
    shownBulk.current = bulk;
  }, [bulk]);

  useEffect(() => setError(null), [single, bulkText, bulk]);

  async function submit(urls: string[]) {
    if (busy) return;
    if (!urls.length) {
      setError(t("error.NO_URLS"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await onSubmit(urls.slice(0, maxLinks), chosen);
      if (bulk) setBulkText("");
      else setSingle("");
    } catch (failure) {
      setError(errorText(t, failure instanceof ApiError ? failure.code : "UNKNOWN"));
    } finally {
      setBusy(false);
    }
  }

  async function loadFile(file: File) {
    if (file.size > MAX_FILE_BYTES) {
      setError(t("input.fileTooBig"));
      return;
    }
    const text = await file.text();
    setBulkText((previous) => (previous.trim() ? `${previous.trimEnd()}\n${text}` : text));
    setBulk(true);
  }

  useEffect(() => {
    const hasFiles = (event: DragEvent) => event.dataTransfer?.types.includes("Files") ?? false;
    const over = (event: DragEvent) => {
      if (!hasFiles(event)) return;
      event.preventDefault();
      setDragging(true);
    };
    const leave = (event: DragEvent) => {
      if (!event.relatedTarget) setDragging(false);
    };
    const drop = (event: DragEvent) => {
      if (!hasFiles(event)) return;
      event.preventDefault();
      setDragging(false);
      const file = event.dataTransfer?.files[0];
      if (file) void loadFile(file);
    };
    window.addEventListener("dragover", over);
    window.addEventListener("dragleave", leave);
    window.addEventListener("drop", drop);
    return () => {
      window.removeEventListener("dragover", over);
      window.removeEventListener("dragleave", leave);
      window.removeEventListener("drop", drop);
    };
  });

  useEffect(() => {
    const paste = (event: globalThis.ClipboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest("input, textarea, [contenteditable]")) return;
      const text = event.clipboardData?.getData("text") ?? "";
      const urls = extractUrls(text);
      if (!urls.length) return;
      event.preventDefault();
      if (urls.length > 1 || bulk) {
        setBulkText((previous) => (previous.trim() ? `${previous.trimEnd()}
${text}` : text));
        setBulk(true);
        areaRef.current?.focus();
      } else {
        setSingle(urls[0] as string);
        inputRef.current?.focus();
      }
    };
    window.addEventListener("paste", paste);
    return () => window.removeEventListener("paste", paste);
  }, [bulk]);

  function onSinglePaste(event: ClipboardEvent<HTMLInputElement>) {
    const text = event.clipboardData.getData("text");
    if (extractUrls(text).length < 2) return;
    event.preventDefault();
    setBulkText((previous) => (previous.trim() ? `${previous.trimEnd()}\n${text}` : text));
    setBulk(true);
  }

  function onSingleKey(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      void submit(singleUrl ? [singleUrl] : []);
    }
  }

  function onBulkKey(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      void submit(bulkUrls);
    }
  }

  const goButton = (label: string, urls: string[]) => (
    <button type="button" className="btn go" disabled={busy} onClick={() => void submit(urls)}>
      {busy ? <Spinner /> : null}
      {label}
    </button>
  );

  return (
    <section className={bulk ? "panel bulk" : "panel"} aria-label={t("input.hint")}>
      <div className="panel-top">
        <span>{bulk ? t("input.hintBulk", { max: maxLinks }) : t("input.hint")}</span>
        <button
          type="button"
          role="switch"
          aria-checked={bulk}
          className="toggle"
          onClick={() => setBulk((value) => !value)}
        >
          <b>{bulk ? "[x]" : "[ ]"}</b> {t("input.bulk")}
        </button>
      </div>

      <div className="field">
        {bulk ? (
          <textarea
            ref={areaRef}
            value={bulkText}
            rows={6}
            spellCheck={false}
            placeholder={t("input.placeholderBulk")}
            aria-label={t("input.hintBulk", { max: maxLinks })}
            onChange={(event) => setBulkText(event.target.value)}
            onKeyDown={onBulkKey}
          />
        ) : (
          <input
            ref={inputRef}
            type="text"
            inputMode="url"
            autoComplete="off"
            spellCheck={false}
            value={single}
            placeholder={t("input.placeholder")}
            aria-label={t("input.hint")}
            onChange={(event) => setSingle(event.target.value)}
            onKeyDown={onSingleKey}
            onPaste={onSinglePaste}
          />
        )}
        <button
          type="button"
          className="btn file"
          title={t("input.txtTitle")}
          aria-label={t("input.txtTitle")}
          onClick={() => fileRef.current?.click()}
        >
          {t("input.txt")}
        </button>
        <input
          ref={fileRef}
          type="file"
          accept=".txt,text/plain"
          hidden
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void loadFile(file);
            event.target.value = "";
          }}
        />
      </div>

      {error ? (
        <p className="notice" role="alert">
          ✕ {error}
        </p>
      ) : null}

      {bulk ? (
        <div className="row">
          <span className="mute counter" aria-live="polite">
            {bulkUrls.length ? t("input.links", { n: bulkUrls.length }) : t("input.noLinks")}
            {bulkUrls.length > maxLinks ? ` · ${t("input.truncated", { max: maxLinks })}` : ""}
          </span>
          <span className="mute keys">{t("input.keysBulk")}</span>
        </div>
      ) : null}

      {bulk ? (
        <div className="row">
          <span className="mute">{t("input.forAll")}</span>
          <Presets options={PRESETS} value={chosen} onChange={setPreset} label={t("input.forAll")} />
          {goButton(
            t("input.downloadN", { n: Math.min(bulkUrls.length, maxLinks) }),
            bulkUrls,
          )}
        </div>
      ) : null}

      {!bulk && probe.status === "idle" ? (
        <div className="row hint-row">
          <span className="mute">{t("input.sites")}</span>
          <span className="mute keys">{t("input.keysSingle")}</span>
        </div>
      ) : null}

      {!bulk && probe.status === "loading" ? (
        <div className="row">
          <span className="mute probing">
            <Spinner /> {t("input.probing")}
          </span>
          {goButton(t("input.download"), [probe.url])}
        </div>
      ) : null}

      {!bulk && probe.status === "error" ? (
        <div className="row">
          <span className="notice inline">✕ {errorText(t, probe.error.code)}</span>
          {RETRIABLE.has(probe.error.code) ? goButton(t("input.download"), [probe.url]) : null}
        </div>
      ) : null}

      {!bulk && probe.status === "ready" ? (
        <Preview info={probe.info} maxItems={limits.max_playlist_items}>
          <Presets options={offered} value={chosen} onChange={setPreset} sizes={probe.info.sizes} />
          {goButton(t("input.download"), [probe.url])}
        </Preview>
      ) : null}

      {dragging ? (
        <div className="drop" aria-hidden="true">
          <span>{t("input.drop")}</span>
        </div>
      ) : null}
    </section>
  );
}
