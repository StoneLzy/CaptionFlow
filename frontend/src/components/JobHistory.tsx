import { useEffect, useRef, useState } from "react";
import {
  Ban,
  CheckCircle2,
  ChevronRight,
  CircleDashed,
  Clock3,
  FileVideo2,
  Folder,
  History,
  Inbox,
  LoaderCircle,
  TriangleAlert,
  XCircle,
  type LucideIcon,
} from "lucide-react";

import type { JobStatus, JobSummary } from "../types";
import type { Translations } from "../i18n";

interface Props {
  jobs: JobSummary[];
  selectedJobId: string | null;
  onSelectJob: (jobId: string) => void;
  t: Translations;
  loading?: boolean;
  loadError?: string | null;
}

function jobPercent(job: JobSummary): number | null {
  if (job.status === "completed") {
    return 100;
  }
  if (job.progress.length === 0) {
    return null;
  }
  const totalPercent = job.progress.reduce((sum, stage) => {
    if (typeof stage.percent === "number") {
      return sum + stage.percent;
    }
    if (stage.status === "completed" || stage.status === "skipped") {
      return sum + 100;
    }
    return sum;
  }, 0);
  return Math.round(totalPercent / job.progress.length);
}

const JOB_STATUS_ICONS: Record<JobStatus, LucideIcon> = {
  created: Clock3,
  running: LoaderCircle,
  completed: CheckCircle2,
  failed: XCircle,
  cancelled: Ban,
};

export function JobHistory({ jobs, selectedJobId, onSelectJob, t, loading, loadError }: Props) {
  const selectedRowRef = useRef<HTMLButtonElement>(null);
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);

  useEffect(() => {
    selectedRowRef.current?.scrollIntoView?.({ block: "nearest", behavior: "smooth" });
  }, [selectedJobId]);

  useEffect(() => {
    if (selectedJobId) {
      setExpandedJobId(selectedJobId);
    }
  }, [selectedJobId]);

  function handleRowClick(jobId: string) {
    if (selectedJobId === jobId) {
      setExpandedJobId((current) => (current === jobId ? null : jobId));
      return;
    }
    onSelectJob(jobId);
    setExpandedJobId(jobId);
  }

  return (
    <aside className="history">
      <div className="panel-heading history-heading">
        <div className="history-heading-copy">
          <span className="history-heading-icon" aria-hidden="true">
            <History size={18} strokeWidth={2} />
          </span>
          <h2>{t.historyTitle}</h2>
        </div>
        <span className="history-count">{t.historyCount(jobs.length)}</span>
      </div>
      {loading ? (
        <p className="history-state history-loading">
          <LoaderCircle className="history-state-icon is-spinning" size={17} aria-hidden="true" />
          <span>{t.loadingJobs}</span>
        </p>
      ) : null}
      {loadError ? (
        <p className="form-error history-state history-error" role="alert">
          <TriangleAlert className="history-state-icon" size={17} aria-hidden="true" />
          <span>{loadError}</span>
        </p>
      ) : null}
      {!loading && !loadError && jobs.length === 0 ? (
        <div className="history-empty">
          <span className="history-empty-icon" aria-hidden="true">
            <Inbox size={24} strokeWidth={1.8} />
          </span>
          <p>{t.noJobs}</p>
        </div>
      ) : null}
      {jobs.length > 0 ? <p className="history-hint">{t.historyExpandHint}</p> : null}
      <div className="history-list" role="list">
        {jobs.map((job) => {
          const isExpanded = expandedJobId === job.id;
          const percent = jobPercent(job);
          const StatusIcon = JOB_STATUS_ICONS[job.status] ?? CircleDashed;
          return (
            <div className="history-list-item" role="listitem" key={job.id}>
              <button
                className={`job-row status-${job.status}${selectedJobId === job.id ? " selected" : ""}${isExpanded ? " expanded" : ""}`}
                ref={selectedJobId === job.id ? selectedRowRef : undefined}
                type="button"
                aria-current={selectedJobId === job.id ? "true" : undefined}
                aria-expanded={isExpanded}
                onClick={() => handleRowClick(job.id)}
              >
                <span className="job-row-summary">
                  <span className={`job-row-icon status-${job.status}`} aria-hidden="true">
                    <FileVideo2 size={17} strokeWidth={1.9} />
                  </span>
                  <span className="job-row-copy">
                    <span
                      className={`job-row-title${isExpanded ? " expanded" : ""}`}
                      title={isExpanded ? undefined : job.filename}
                    >
                      {job.filename}
                    </span>
                    <span className="job-row-meta">
                      <span className={`job-status-badge status-${job.status}`}>
                        <StatusIcon
                          className={job.status === "running" ? "is-spinning" : undefined}
                          size={12}
                          strokeWidth={2.2}
                          aria-hidden="true"
                        />
                        <span>{t.jobStatusLabels[job.status]}</span>
                      </span>
                      {percent != null ? <span className="job-row-percent">{percent}%</span> : null}
                    </span>
                  </span>
                  <ChevronRight
                    className={`job-row-chevron${isExpanded ? " expanded" : ""}`}
                    size={15}
                    strokeWidth={2.2}
                    aria-hidden="true"
                  />
                </span>
                {isExpanded && job.output_directory ? (
                  <span className="job-row-path" title={job.output_directory}>
                    <Folder size={13} strokeWidth={2} aria-hidden="true" />
                    <span>{t.outputDirectoryLabel}: {job.output_directory}</span>
                  </span>
                ) : null}
                {percent != null ? (
                  <span className="mini-progress" aria-hidden="true">
                    <span style={{ width: `${percent}%` }} />
                  </span>
                ) : null}
              </button>
            </div>
          );
        })}
      </div>
    </aside>
  );
}
