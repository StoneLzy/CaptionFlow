import { useCallback, useEffect, useState } from "react";
import {
  cancelJob,
  deleteJob,
  fetchHealth,
  fetchJobs,
  fetchSettings,
  jobLogUrl,
  openJobFolder,
  outputDownloadUrl,
  renameJob,
  runJob,
  translateJob,
} from "./api/client";
import type { AppSettings } from "./api/client";
import { JobHistory } from "./components/JobHistory";
import { JobWorkbench } from "./components/JobWorkbench";
import { AboutDialog } from "./components/AboutDialog";
import { ProgressTimeline } from "./components/ProgressTimeline";
import { SettingsDialog } from "./components/SettingsDialog";
import { OUTPUT_LABELS } from "./formDefaults";
import { readStoredLanguage, storeLanguage, t, type UiLanguage } from "./i18n";
import type { JobSummary } from "./types";

function formatTimestamp(value: string, language: UiLanguage): string {
  try {
    return new Intl.DateTimeFormat(language === "zh" ? "zh-CN" : "en-US", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function outputLabel(key: string, language: UiLanguage): string {
  const labels = OUTPUT_LABELS[key];
  if (labels) {
    return language === "zh" ? labels.zh : labels.en;
  }
  return key.replaceAll("_", " ");
}

function isDownloadableOutput(key: string): boolean {
  return key !== "download_title" && key !== "ytdlp_log";
}

export function App() {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [language, setLanguage] = useState<UiLanguage>(() => readStoredLanguage());
  const [jobsLoading, setJobsLoading] = useState(true);
  const [jobsLoadError, setJobsLoadError] = useState<string | null>(null);
  const [backendDegraded, setBackendDegraded] = useState(false);
  const [folderError, setFolderError] = useState<string | null>(null);
  const [retryError, setRetryError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);
  const [rerunning, setRerunning] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [activeLog, setActiveLog] = useState<string | null>(null);
  const [isRenaming, setIsRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState("");
  const [renameError, setRenameError] = useState<string | null>(null);
  const [renaming, setRenaming] = useState(false);
  const [aboutOpen, setAboutOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsRevision, setSettingsRevision] = useState(0);
  const labels = t[language];

  const refreshJobs = useCallback(async () => {
    try {
      const nextJobs = await fetchJobs();
      setJobs(nextJobs);
      setJobsLoadError(null);
      return nextJobs;
    } catch (error) {
      setJobsLoadError(error instanceof Error ? error.message : labels.jobsLoadError);
      return null;
    } finally {
      setJobsLoading(false);
    }
  }, [labels.jobsLoadError]);

  useEffect(() => {
    void refreshJobs();
    fetchHealth()
      .then((health) => setBackendDegraded(health.status !== "ok"))
      .catch(() => setBackendDegraded(true));
    fetchSettings()
      .then((settings) => {
        if (!settings.onboarding_completed) {
          setSettingsOpen(true);
        }
      })
      .catch(() => undefined);
  }, [refreshJobs]);

  useEffect(() => {
    const hasActiveJob = jobs.some((job) => !["completed", "failed", "cancelled"].includes(job.status));
    if (!hasActiveJob) {
      return;
    }

    const timer = window.setInterval(() => {
      void refreshJobs();
    }, 2000);

    return () => window.clearInterval(timer);
  }, [jobs, refreshJobs]);

  useEffect(() => {
    if (jobs.length === 0) {
      setSelectedJobId(null);
      return;
    }
    if (selectedJobId && jobs.some((job) => job.id === selectedJobId)) {
      return;
    }
    const activeJob = jobs.find((job) => !["completed", "failed", "cancelled"].includes(job.status));
    setSelectedJobId((activeJob ?? jobs[0]).id);
  }, [jobs, selectedJobId]);

  const selectedJob = jobs.find((job) => job.id === selectedJobId) ?? null;

  useEffect(() => {
    setIsRenaming(false);
    setRenameValue(selectedJob?.filename ?? "");
    setRenameError(null);
  }, [selectedJobId, selectedJob?.filename]);

  function handleJobStarted(job: JobSummary) {
    setSelectedJobId(job.id);
    setActiveLog(null);
    setFolderError(null);
    setRetryError(null);
    setActionError(null);
    setJobs((current) => [job, ...current.filter((item) => item.id !== job.id)]);
    void refreshJobs();
  }

  function handleLanguageChange(nextLanguage: UiLanguage) {
    setLanguage(nextLanguage);
    storeLanguage(nextLanguage);
  }

  function handleSettingsSaved(_settings: AppSettings) {
    setSettingsRevision((current) => current + 1);
    setSettingsOpen(false);
    fetchHealth()
      .then((health) => setBackendDegraded(health.status !== "ok"))
      .catch(() => setBackendDegraded(true));
  }

  async function handleOpenOutputFolder(jobId: string) {
    setFolderError(null);
    try {
      await openJobFolder(jobId);
    } catch (error) {
      setFolderError(error instanceof Error ? error.message : labels.openOutputFolderError);
    }
  }

  function canRetryTranslation(job: JobSummary) {
    if (!["completed", "failed", "cancelled"].includes(job.status)) {
      return false;
    }
    return Boolean(
      job.outputs.translation_srt ||
        job.outputs.transcript_srt ||
        job.outputs.merged_srt,
    );
  }

  async function handleRetryTranslation(jobId: string) {
    setRetryError(null);
    setRetrying(true);
    try {
      const started = await translateJob(jobId);
      handleJobStarted(started);
    } catch (error) {
      setRetryError(error instanceof Error ? error.message : labels.retryTranslationError);
    } finally {
      setRetrying(false);
    }
  }

  async function handleRerunJob(jobId: string) {
    setActionError(null);
    setRerunning(true);
    try {
      const started = await runJob(jobId);
      handleJobStarted(started);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : labels.rerunJobError);
    } finally {
      setRerunning(false);
    }
  }

  async function handleCancelJob(jobId: string) {
    setActionError(null);
    setCancelling(true);
    try {
      await cancelJob(jobId);
      await refreshJobs();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : labels.cancelJobError);
    } finally {
      setCancelling(false);
    }
  }

  async function handleDeleteJob(jobId: string) {
    setActionError(null);
    setDeleting(true);
    try {
      await deleteJob(jobId);
      const nextJobs = await refreshJobs();
      if (selectedJobId === jobId) {
        setSelectedJobId(nextJobs?.[0]?.id ?? null);
      }
      setActiveLog(null);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : labels.deleteJobError);
    } finally {
      setDeleting(false);
    }
  }

  async function handleRenameJob(jobId: string) {
    const nextName = renameValue.trim();
    if (!nextName) {
      setRenameError(labels.renameJobError);
      return;
    }
    setRenameError(null);
    setRenaming(true);
    try {
      const updated = await renameJob(jobId, nextName);
      setJobs((current) =>
        current.map((job) => (job.id === updated.id ? { ...job, filename: updated.filename } : job)),
      );
      setIsRenaming(false);
    } catch (error) {
      setRenameError(error instanceof Error ? error.message : labels.renameJobError);
    } finally {
      setRenaming(false);
    }
  }

  async function handleViewLog(jobId: string, logName: "ytdlp" | "whisperkit") {
    setActionError(null);
    try {
      const response = await fetch(jobLogUrl(jobId, logName));
      if (!response.ok) {
        throw new Error(labels.noLogAvailable);
      }
      setActiveLog(await response.text());
    } catch (error) {
      setActionError(error instanceof Error ? error.message : labels.noLogAvailable);
      setActiveLog(null);
    }
  }

  const outputEntries = selectedJob
    ? Object.entries(selectedJob.outputs).filter(([key]) => key !== "download_title")
    : [];

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <h1>{labels.appTitle}</h1>
          <p>{labels.appSubtitle}</p>
          {backendDegraded ? (
            <p className="topbar-warning" role="alert">
              {labels.backendDegraded}
            </p>
          ) : null}
        </div>
        <div className="topbar-actions">
          <button className="about-trigger" type="button" onClick={() => setSettingsOpen(true)}>
            {labels.settings}
          </button>
          <button className="about-trigger" type="button" onClick={() => setAboutOpen(true)}>
            {labels.about}
          </button>
          <div className="language-toggle" aria-label="Language">
            <button
              className={language === "zh" ? "active" : ""}
              type="button"
              onClick={() => handleLanguageChange("zh")}
            >
              {labels.languageZh}
            </button>
            <button
              className={language === "en" ? "active" : ""}
              type="button"
              onClick={() => handleLanguageChange("en")}
            >
              {labels.languageEn}
            </button>
          </div>
        </div>
      </header>
      <AboutDialog open={aboutOpen} onClose={() => setAboutOpen(false)} t={labels} />
      <SettingsDialog
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onSaved={handleSettingsSaved}
        t={labels}
      />
      <div className="layout">
        <JobHistory
          jobs={jobs}
          selectedJobId={selectedJobId}
          onSelectJob={setSelectedJobId}
          t={labels}
          loading={jobsLoading}
          loadError={jobsLoadError}
        />
        <div className="main-panel">
          <JobWorkbench
            key={settingsRevision}
            onJobStarted={handleJobStarted}
            t={labels}
          />
        </div>
        <aside className="progress-panel">
          {selectedJob ? (
            <section className="job-detail">
              <p className="panel-eyebrow">{labels.selectedJob}</p>
              {isRenaming ? (
                <div className="job-title-edit">
                  <input
                    aria-label={labels.renameJobPlaceholder}
                    type="text"
                    value={renameValue}
                    onChange={(event) => setRenameValue(event.target.value)}
                    placeholder={labels.renameJobPlaceholder}
                  />
                  <div className="job-title-edit-actions">
                    <button
                      className="secondary-button"
                      type="button"
                      disabled={renaming}
                      onClick={() => void handleRenameJob(selectedJob.id)}
                    >
                      {renaming ? labels.saveRename : labels.saveRename}
                    </button>
                    <button
                      className="secondary-button"
                      type="button"
                      disabled={renaming}
                      onClick={() => {
                        setIsRenaming(false);
                        setRenameValue(selectedJob.filename);
                        setRenameError(null);
                      }}
                    >
                      {labels.cancelRename}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="job-title-row">
                  <h2 className="job-title-full">{selectedJob.filename}</h2>
                  <button
                    className="secondary-button job-rename-button"
                    type="button"
                    onClick={() => {
                      setRenameValue(selectedJob.filename);
                      setIsRenaming(true);
                      setRenameError(null);
                    }}
                  >
                    {labels.renameJob}
                  </button>
                </div>
              )}
              {renameError ? (
                <p className="form-error" role="alert">
                  {renameError}
                </p>
              ) : null}
              <p className="job-status">
                {labels.status}: {labels.jobStatusLabels[selectedJob.status]}
              </p>
              <p className="job-meta">
                {labels.createdAt}: {formatTimestamp(selectedJob.created_at, language)}
              </p>
              <div className="job-actions">
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => void handleOpenOutputFolder(selectedJob.id)}
                >
                  {labels.openOutputFolder}
                </button>
                {selectedJob.status === "running" ? (
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={cancelling}
                    onClick={() => void handleCancelJob(selectedJob.id)}
                  >
                    {cancelling ? labels.cancelJob : labels.cancelJob}
                  </button>
                ) : null}
                {["failed", "completed", "cancelled"].includes(selectedJob.status) ? (
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={rerunning}
                    onClick={() => void handleRerunJob(selectedJob.id)}
                  >
                    {rerunning ? labels.starting : labels.rerunJob}
                  </button>
                ) : null}
                {canRetryTranslation(selectedJob) ? (
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={retrying || selectedJob.status === "running"}
                    onClick={() => void handleRetryTranslation(selectedJob.id)}
                  >
                    {retrying ? labels.retryingTranslation : labels.retryTranslation}
                  </button>
                ) : null}
                {selectedJob.status !== "running" ? (
                  <button
                    className="danger-button"
                    type="button"
                    disabled={deleting}
                    onClick={() => void handleDeleteJob(selectedJob.id)}
                  >
                    {deleting ? labels.deleteJob : labels.deleteJob}
                  </button>
                ) : null}
              </div>
              {canRetryTranslation(selectedJob) ? (
                <p className="job-hint">{labels.retryTranslationHint}</p>
              ) : null}
              {folderError ? (
                <p className="form-error" role="alert">
                  {folderError}
                </p>
              ) : null}
              {retryError ? (
                <p className="form-error" role="alert">
                  {retryError}
                </p>
              ) : null}
              {actionError ? (
                <p className="form-error" role="alert">
                  {actionError}
                </p>
              ) : null}
              {selectedJob.error_summary ? (
                <p className="form-error" role="alert">
                  {selectedJob.error_summary}
                </p>
              ) : null}
              {outputEntries.length > 0 ? (
                <div className="outputs-panel">
                  <h3>{labels.outputsTitle}</h3>
                  <ul className="outputs-list">
                    {outputEntries.map(([key, path]) => (
                      <li key={key}>
                        <span>{outputLabel(key, language)}</span>
                        {isDownloadableOutput(key) ? (
                          <a
                            href={outputDownloadUrl(selectedJob.id, key)}
                            download
                          >
                            {labels.downloadOutput}
                          </a>
                        ) : (
                          <span className="output-path">{path.split("/").pop()}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              <div className="log-actions">
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => void handleViewLog(selectedJob.id, "ytdlp")}
                >
                  {labels.viewLog}: yt-dlp
                </button>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => void handleViewLog(selectedJob.id, "whisperkit")}
                >
                  {labels.viewLog}: WhisperKit
                </button>
              </div>
              {activeLog ? (
                <pre className="job-log" role="region" aria-label="Job log">
                  {activeLog}
                </pre>
              ) : null}
              <ProgressTimeline stages={selectedJob.progress} t={labels} />
            </section>
          ) : (
            <section className="job-detail empty-progress">
              <p className="panel-eyebrow">{labels.progress}</p>
              <h2>{labels.noSelection}</h2>
            </section>
          )}
        </aside>
      </div>
    </main>
  );
}
