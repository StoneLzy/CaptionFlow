import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Captions,
  CheckCircle2,
  CircleHelp,
  Download,
  FileText,
  FolderOpen,
  Languages,
  Pencil,
  Plus,
  RefreshCw,
  ScrollText,
  Settings2,
  ShieldCheck,
  Sparkles,
  Square,
  Trash2,
} from "lucide-react";
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

function jobPercent(job: JobSummary): number {
  if (job.status === "completed") {
    return 100;
  }
  if (job.progress.length === 0) {
    return 0;
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
  const [workspaceMode, setWorkspaceMode] = useState<"create" | "detail">("create");
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
      setWorkspaceMode("create");
      return;
    }
    if (selectedJobId && jobs.some((job) => job.id === selectedJobId)) {
      return;
    }
    const activeJob = jobs.find((job) => !["completed", "failed", "cancelled"].includes(job.status));
    setSelectedJobId((activeJob ?? jobs[0]).id);
    setWorkspaceMode("detail");
  }, [jobs, selectedJobId]);

  const selectedJob = jobs.find((job) => job.id === selectedJobId) ?? null;

  useEffect(() => {
    setIsRenaming(false);
    setRenameValue(selectedJob?.filename ?? "");
    setRenameError(null);
  }, [selectedJobId, selectedJob?.filename]);

  function clearJobFeedback() {
    setActiveLog(null);
    setFolderError(null);
    setRetryError(null);
    setActionError(null);
  }

  function handleJobCreated(job: JobSummary) {
    setSelectedJobId(job.id);
    clearJobFeedback();
    setJobs((current) => [job, ...current.filter((item) => item.id !== job.id)]);
  }

  function handleJobStarted(job: JobSummary) {
    setSelectedJobId(job.id);
    setWorkspaceMode("detail");
    clearJobFeedback();
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
    const confirmed = window.confirm(
      language === "zh"
        ? "确定删除这个任务吗？任务目录及其中产物将被永久删除。"
        : "Delete this job? Its job directory and generated files will be permanently removed.",
    );
    if (!confirmed) {
      return;
    }
    setActionError(null);
    setDeleting(true);
    try {
      await deleteJob(jobId);
      const nextJobs = await refreshJobs();
      if (selectedJobId === jobId) {
        setSelectedJobId(nextJobs?.[0]?.id ?? null);
        setWorkspaceMode(nextJobs?.length ? "detail" : "create");
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
  const overallPercent = selectedJob ? jobPercent(selectedJob) : 0;
  const activeStage = selectedJob?.progress.find((stage) => stage.status === "running") ?? null;

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand-block">
          <div className="brand-mark" aria-hidden="true">
            <Captions size={25} strokeWidth={2.2} />
          </div>
          <div className="brand-wordmark">
            <h1>{labels.appTitle}</h1>
            <p>{labels.appSubtitle}</p>
          </div>
        </div>
        <div className="topbar-actions">
          <div
            className={`health-pill${backendDegraded ? " degraded" : ""}`}
            role={backendDegraded ? "alert" : undefined}
            title={backendDegraded ? labels.backendDegraded : undefined}
          >
            {backendDegraded ? (
              <AlertTriangle size={14} aria-hidden="true" />
            ) : (
              <CheckCircle2 size={14} aria-hidden="true" />
            )}
            <span>
              {backendDegraded
                ? language === "zh" ? "服务需要检查" : "Service needs attention"
                : language === "zh" ? "本地引擎已连接" : "Local engine ready"}
            </span>
          </div>
          <button className="topbar-button" type="button" onClick={() => setSettingsOpen(true)}>
            <Settings2 size={16} aria-hidden="true" />
            <span>{labels.settings}</span>
          </button>
          <button className="topbar-button icon-only" type="button" aria-label={labels.about} onClick={() => setAboutOpen(true)}>
            <CircleHelp size={17} aria-hidden="true" />
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
        <div className="sidebar-shell">
          <button
            className={`new-job-nav${workspaceMode === "create" ? " active" : ""}`}
            type="button"
            aria-current={workspaceMode === "create" ? "page" : undefined}
            onClick={() => {
              setWorkspaceMode("create");
              setActiveLog(null);
            }}
          >
            <span className="new-job-nav-icon" aria-hidden="true">
              <Plus size={19} />
            </span>
            <span className="new-job-nav-copy">
              <strong>{labels.newJob}</strong>
              <small>{language === "zh" ? "开始一条新的字幕工作流" : "Start a new subtitle flow"}</small>
            </span>
          </button>
          <JobHistory
            jobs={jobs}
            selectedJobId={workspaceMode === "detail" ? selectedJobId : null}
            onSelectJob={(jobId) => {
              setSelectedJobId(jobId);
              setWorkspaceMode("detail");
              clearJobFeedback();
            }}
            t={labels}
            loading={jobsLoading}
            loadError={jobsLoadError}
          />
          <div className="sidebar-trust-note">
            <ShieldCheck size={16} aria-hidden="true" />
            <span>{language === "zh" ? "文件与任务数据保留在本机" : "Files and job data stay on this Mac"}</span>
          </div>
        </div>

        <section className="workspace">
          {workspaceMode === "create" || !selectedJob ? (
            <JobWorkbench
              key={settingsRevision}
              onJobCreated={handleJobCreated}
              onJobStarted={handleJobStarted}
              t={labels}
            />
          ) : (
            <div className="job-workspace">
              <header className="job-hero">
                <div className="job-hero-topline">
                  <p className="panel-eyebrow">
                    <Activity size={14} aria-hidden="true" />
                    {labels.selectedJob}
                  </p>
                  <span className={`job-status-pill status-${selectedJob.status}`}>
                    <span aria-hidden="true" />
                    {labels.jobStatusLabels[selectedJob.status]}
                  </span>
                </div>
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
                      className="primary-button compact"
                      type="button"
                      disabled={renaming}
                      onClick={() => void handleRenameJob(selectedJob.id)}
                    >
                      {renaming ? labels.saveRename : labels.saveRename}
                    </button>
                    <button
                      className="ghost-button compact"
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
                    className="icon-button job-rename-button"
                    type="button"
                    aria-label={labels.renameJob}
                    onClick={() => {
                      setRenameValue(selectedJob.filename);
                      setIsRenaming(true);
                      setRenameError(null);
                    }}
                  >
                    <Pencil size={16} aria-hidden="true" />
                  </button>
                </div>
              )}
              {renameError ? (
                <p className="form-error" role="alert">
                  {renameError}
                </p>
              ) : null}
                <div className="job-hero-meta">
                  <span>{labels.createdAt}: {formatTimestamp(selectedJob.created_at, language)}</span>
                  {activeStage ? (
                    <span>{language === "zh" ? "当前阶段" : "Current stage"}: {labels.stageLabels[activeStage.name]}</span>
                  ) : null}
                </div>
                <div className="overall-progress-block">
                  <div className="overall-progress-copy">
                    <span>{language === "zh" ? "整体进度" : "Overall progress"}</span>
                    <strong>{overallPercent}%</strong>
                  </div>
                  <div className="overall-progress-track" aria-hidden="true">
                    <span style={{ width: `${overallPercent}%` }} />
                  </div>
                </div>
              </header>

              <div className="job-detail-grid">
                <div className="job-detail-main">
                  <section className="detail-card progress-card">
                    <header className="detail-card-heading">
                      <span className="detail-card-icon"><Activity size={17} aria-hidden="true" /></span>
                      <div>
                        <p className="panel-eyebrow">{language === "zh" ? "PROCESS" : "PROCESS"}</p>
                        <h3>{labels.progress}</h3>
                      </div>
                    </header>
                    <ProgressTimeline stages={selectedJob.progress} t={labels} />
                  </section>
                  {activeLog ? (
                    <section className="detail-card log-card">
                      <header className="detail-card-heading">
                        <span className="detail-card-icon"><ScrollText size={17} aria-hidden="true" /></span>
                        <div>
                          <p className="panel-eyebrow">LOG</p>
                          <h3>{language === "zh" ? "运行日志" : "Runtime log"}</h3>
                        </div>
                      </header>
                      <pre className="job-log" role="region" aria-label="Job log">
                        {activeLog}
                      </pre>
                    </section>
                  ) : null}
                </div>

                <aside className="job-detail-aside">
                  <section className="detail-card action-card">
                    <header className="detail-card-heading compact-heading">
                      <span className="detail-card-icon"><Sparkles size={17} aria-hidden="true" /></span>
                      <h3>{language === "zh" ? "任务操作" : "Job actions"}</h3>
                    </header>
                    <button
                      className="primary-button wide"
                      type="button"
                      onClick={() => void handleOpenOutputFolder(selectedJob.id)}
                    >
                      <FolderOpen size={17} aria-hidden="true" />
                      {labels.openOutputFolder}
                    </button>
                    <div className="job-actions">
                      {selectedJob.status === "running" ? (
                        <button
                          className="secondary-button"
                          type="button"
                          disabled={cancelling}
                          onClick={() => void handleCancelJob(selectedJob.id)}
                        >
                          <Square size={14} aria-hidden="true" />
                          {labels.cancelJob}
                        </button>
                      ) : null}
                      {selectedJob.status === "created" ? (
                        <button
                          className="secondary-button"
                          type="button"
                          disabled={rerunning}
                          onClick={() => void handleRerunJob(selectedJob.id)}
                        >
                          <RefreshCw size={15} aria-hidden="true" />
                          {rerunning ? labels.starting : labels.startJob}
                        </button>
                      ) : null}
                      {["failed", "completed", "cancelled"].includes(selectedJob.status) ? (
                        <button
                          className="secondary-button"
                          type="button"
                          disabled={rerunning}
                          onClick={() => void handleRerunJob(selectedJob.id)}
                        >
                          <RefreshCw size={15} aria-hidden="true" />
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
                          <Languages size={15} aria-hidden="true" />
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
                          <Trash2 size={15} aria-hidden="true" />
                          {labels.deleteJob}
                        </button>
                      ) : null}
                    </div>
                    {canRetryTranslation(selectedJob) ? (
                      <p className="job-hint">{labels.retryTranslationHint}</p>
                    ) : null}
                    {[folderError, retryError, actionError, selectedJob.error_summary]
                      .filter(Boolean)
                      .map((message) => (
                        <p className="form-error" role="alert" key={message}>{message}</p>
                      ))}
                  </section>

                  <section className="detail-card outputs-panel">
                    <header className="detail-card-heading compact-heading">
                      <span className="detail-card-icon"><FileText size={17} aria-hidden="true" /></span>
                      <h3>{labels.outputsTitle}</h3>
                      {outputEntries.length ? <span className="card-count">{outputEntries.length}</span> : null}
                    </header>
                    {outputEntries.length > 0 ? (
                      <ul className="outputs-list">
                        {outputEntries.map(([key, path]) => (
                          <li key={key}>
                            <span className="output-file-icon"><FileText size={15} aria-hidden="true" /></span>
                            <span className="output-file-copy">
                              <strong>{outputLabel(key, language)}</strong>
                              <small>{path.split("/").pop()}</small>
                            </span>
                            {isDownloadableOutput(key) ? (
                              <a
                                href={outputDownloadUrl(selectedJob.id, key)}
                                download
                                aria-label={`${labels.downloadOutput}: ${outputLabel(key, language)}`}
                              >
                                <Download size={15} aria-hidden="true" />
                              </a>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="empty-card-copy">{language === "zh" ? "任务完成后，产物会显示在这里。" : "Outputs will appear here when the job is ready."}</p>
                    )}
                  </section>

                  <section className="detail-card logs-panel">
                    <header className="detail-card-heading compact-heading">
                      <span className="detail-card-icon"><ScrollText size={17} aria-hidden="true" /></span>
                      <h3>{language === "zh" ? "诊断日志" : "Diagnostic logs"}</h3>
                    </header>
                    <div className="log-actions">
                      <button className="ghost-button" type="button" onClick={() => void handleViewLog(selectedJob.id, "ytdlp")}>
                        {labels.viewLog}: yt-dlp
                      </button>
                      <button className="ghost-button" type="button" onClick={() => void handleViewLog(selectedJob.id, "whisperkit")}>
                        {labels.viewLog}: WhisperKit
                      </button>
                    </div>
                  </section>
                </aside>
              </div>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
