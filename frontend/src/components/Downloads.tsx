import { type Job, api } from "../api/client";
import { type BatchView, countFiles, isFinished } from "../hooks/useBatches";
import { useNow } from "../hooks/useNow";
import { useI18n } from "../i18n/I18nContext";
import { formatBytes, formatDuration, formatSpeed } from "../lib/format";
import { shortUrl } from "../lib/urls";
import { errorText } from "./errors";
import { Spinner } from "./Spinner";

interface Props {
  views: BatchView[];
  onRemove: (id: string) => void;
}

export function Downloads({ views, onRemove }: Props) {
  const { t } = useI18n();
  const now = useNow(views.length > 0);
  if (!views.length) return null;
  const totals = views.map(countFiles).reduce(
    (sum, item) => ({ done: sum.done + item.done, total: sum.total + item.total }),
    { done: 0, total: 0 },
  );

  return (
    <section className="jobs" aria-labelledby="jobs-title">
      <div className="jobs-head">
        <h2 id="jobs-title">{t("jobs.title")}</h2>
        <span className="mute" aria-live="polite">
          {t("jobs.summary", totals)}
        </span>
      </div>
      {views.map((view) => (
        <BatchBlock key={view.batch.id} view={view} now={now} onRemove={onRemove} />
      ))}
    </section>
  );
}

function BatchBlock({ view, now, onRemove }: { view: BatchView; now: number; onRemove: (id: string) => void }) {
  const { t } = useI18n();
  const { done, total } = countFiles(view);
  const left = (Date.parse(view.batch.expires_at) - now) / 1000;
  const expired = left <= 0;
  const roots = view.jobs.filter((job) => !job.parent_id);
  const children = (id: string) => view.jobs.filter((job) => job.parent_id === id);
  const created = new Date(view.batch.created_at).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className={isFinished(view) ? "batch" : "batch live"}>
      <div className="batch-head">
        <span className="mute batch-info">
          {created} · {view.batch.preset} · {t("jobs.summary", { done, total })}
        </span>
        <span className="batch-actions">
          {done > 0 && total > 1 && !expired ? (
            <a className="btn btn-small ghost" href={api.zipUrl(view.batch.id)} download>
              {t("jobs.zip")}
            </a>
          ) : null}
          <span className="mute">
            {expired ? t("jobs.expired") : t("jobs.expires", { time: formatDuration(left) })}
          </span>
        </span>
        <button
          type="button"
          className="icon batch-remove"
          title={t("jobs.remove")}
          aria-label={t("jobs.remove")}
          onClick={() => onRemove(view.batch.id)}
        >
          ×
        </button>
      </div>
      <ul className="job-list">
        {roots.map((job) => (
          <JobItem key={job.id} job={job} expired={expired} nested={children(job.id)} />
        ))}
      </ul>
    </div>
  );
}

function JobItem({ job, expired, nested }: { job: Job; expired: boolean; nested: Job[] }) {
  return (
    <li>
      <JobRow job={job} expired={expired} childCount={nested.length} />
      {nested.length ? (
        <ul className="job-list nested">
          {nested.map((child) => (
            <li key={child.id}>
              <JobRow job={child} expired={expired} childCount={0} />
            </li>
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function JobRow({ job, expired, childCount }: { job: Job; expired: boolean; childCount: number }) {
  const { t } = useI18n();
  const name = job.title ?? job.files[0]?.name ?? shortUrl(job.url);
  const size = job.files.reduce((sum, file) => sum + file.size, 0);
  const canSave = job.status === "done" && !expired;

  return (
    <div className={`job ${job.status}`}>
      <span className="job-name" title={job.url}>
        {name}
      </span>
      <span className="job-status">
        <Status job={job} childCount={childCount} size={size} />
      </span>
      <span className="job-action">
        {canSave && job.files.length === 1 ? (
          <a href={api.fileUrl(job.id, 0)} download>
            {t("jobs.save")}
          </a>
        ) : null}
        {canSave && job.files.length > 1 ? <span className="mute">{t("jobs.files", { n: job.files.length })}</span> : null}
      </span>
      {canSave && job.files.length > 1 ? (
        <ul className="file-list">
          {job.files.map((file, index) => (
            <li key={file.name}>
              <a href={api.fileUrl(job.id, index)} download>
                {file.name}
              </a>
              <span className="mute"> · {formatBytes(file.size)}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function Status({ job, childCount, size }: { job: Job; childCount: number; size: number }) {
  const { t } = useI18n();
  const progress = job.progress;
  switch (job.status) {
    case "queued":
      return <span className="mute">{t("jobs.queued")}</span>;
    case "processing":
      return (
        <span className="mute">
          <Spinner /> {t("jobs.processing")}
        </span>
      );
    case "expanded":
      return <span className="mute">{t("jobs.expanded", { n: childCount })}</span>;
    case "done":
      return (
        <span className="ok">
          {t("jobs.done")} · {formatBytes(size)}
        </span>
      );
    case "failed":
      return (
        <span className="danger" title={job.error?.message}>
          ✕ {errorText(t, job.error?.code ?? "UNKNOWN")}
        </span>
      );
    case "downloading": {
      if (!progress) {
        return (
          <span className="mute">
            <Spinner /> {t("jobs.starting")}
          </span>
        );
      }
      const parts = [
        progress.percent != null ? `${Math.floor(progress.percent)}%` : progress.downloaded ? formatBytes(progress.downloaded) : null,
        progress.speed ? formatSpeed(progress.speed) : null,
        progress.eta != null ? formatDuration(progress.eta) : null,
      ].filter(Boolean);
      return (
        <span className="progress">
          <span className="progress-meta">{parts.join(" · ")}</span>
          <span
            className={progress.percent == null ? "bar indeterminate" : "bar"}
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={progress.percent ?? undefined}
          >
            <i style={{ width: `${progress.percent ?? 100}%` }} />
          </span>
        </span>
      );
    }
  }
}
