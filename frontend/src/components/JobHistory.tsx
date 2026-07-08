import { useEffect, useRef, useState } from "react";

import type { JobSummary } from "../types";
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
      <div className="panel-heading">
        <h2>{t.historyTitle}</h2>
        <span>{t.historyCount(jobs.length)}</span>
      </div>
      {loading ? <p>{t.loadingJobs}</p> : null}
      {loadError ? (
        <p className="form-error" role="alert">
          {loadError}
        </p>
      ) : null}
      {!loading && !loadError && jobs.length === 0 ? <p>{t.noJobs}</p> : null}
      {jobs.length > 0 ? <p className="history-hint">{t.historyExpandHint}</p> : null}
      {jobs.map((job) => {
        const isExpanded = expandedJobId === job.id;
        return (
          <button
            className={`job-row${selectedJobId === job.id ? " selected" : ""}${isExpanded ? " expanded" : ""}`}
            key={job.id}
            ref={selectedJobId === job.id ? selectedRowRef : undefined}
            type="button"
            aria-current={selectedJobId === job.id ? "true" : undefined}
            aria-expanded={isExpanded}
            onClick={() => handleRowClick(job.id)}
          >
            <span
              className={`job-row-title${isExpanded ? " expanded" : ""}`}
              title={isExpanded ? undefined : job.filename}
            >
              {job.filename}
            </span>
            <span className="job-row-meta">
              <span>{t.jobStatusLabels[job.status]}</span>
              {jobPercent(job) != null ? <span>{jobPercent(job)}%</span> : null}
            </span>
            {jobPercent(job) != null ? (
              <span className="mini-progress" aria-hidden="true">
                <span style={{ width: `${jobPercent(job)}%` }} />
              </span>
            ) : null}
          </button>
        );
      })}
    </aside>
  );
}
