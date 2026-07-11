import {
  CheckCircle2,
  Circle,
  CircleMinus,
  Download,
  FileOutput,
  GitMerge,
  Languages,
  LoaderCircle,
  Mic2,
  PanelsTopLeft,
  UploadCloud,
  XCircle,
  type LucideIcon,
} from "lucide-react";

import type { StageName, StageProgress, StageStatus } from "../types";
import type { Translations } from "../i18n";

interface Props {
  stages: StageProgress[];
  t: Translations;
}

const BATCH_DETAIL_PATTERN = /^Batch (\d+) of (\d+)$/;

const STAGE_ICONS: Record<StageName, LucideIcon> = {
  upload: UploadCloud,
  download: Download,
  track_mux: GitMerge,
  transcription: Mic2,
  merge: PanelsTopLeft,
  translation: Languages,
  export: FileOutput,
};

const STAGE_STATUS_ICONS: Record<StageStatus, LucideIcon> = {
  pending: Circle,
  running: LoaderCircle,
  completed: CheckCircle2,
  failed: XCircle,
  skipped: CircleMinus,
};

function visiblePercent(stage: StageProgress): number | null {
  if (typeof stage.percent === "number") {
    return stage.percent;
  }
  if (
    stage.status === "running" &&
    typeof stage.processed === "number" &&
    typeof stage.total === "number" &&
    stage.total > 0
  ) {
    return Math.min(100, Math.max(0, Math.round((stage.processed / stage.total) * 100)));
  }
  if (stage.status === "completed" || stage.status === "skipped") {
    return 100;
  }
  return null;
}

function stageDetail(stage: StageProgress, t: Translations): string {
  if (!stage.detail) {
    return "";
  }
  const batchMatch = stage.detail.match(BATCH_DETAIL_PATTERN);
  if (batchMatch) {
    return t.translationBatchDetail(Number(batchMatch[1]), Number(batchMatch[2]));
  }
  return stage.detail;
}

export function ProgressTimeline({ stages, t }: Props) {
  return (
    <div className="timeline" aria-label="Job progress">
      {stages.map((stage) => {
        const percent = visiblePercent(stage);
        const detail = stageDetail(stage, t);
        const StageIcon = STAGE_ICONS[stage.name];
        const StatusIcon = STAGE_STATUS_ICONS[stage.status];
        return (
          <section
            className={`timeline-stage status-${stage.status}`}
            key={stage.name}
            data-stage={stage.name}
          >
            <div className={`timeline-stage-marker status-${stage.status}`} aria-hidden="true">
              <StageIcon size={17} strokeWidth={2} />
            </div>
            <div className="timeline-stage-content">
              <div className="stage-header">
                <div className="stage-title">{t.stageLabels[stage.name]}</div>
                <div className={`stage-status status-${stage.status}`}>
                  <StatusIcon
                    className={stage.status === "running" ? "is-spinning" : undefined}
                    size={13}
                    strokeWidth={2.2}
                    aria-hidden="true"
                  />
                  <span>{t.stageStatusLabels[stage.status]}</span>
                  {percent != null ? <strong>{percent}%</strong> : null}
                </div>
              </div>
              {percent != null ? (
                <div className="stage-progress" aria-hidden="true">
                  <span style={{ width: `${percent}%` }} />
                </div>
              ) : null}
              {detail || (stage.processed != null && stage.total != null) ? (
                <div className="stage-supporting-copy">
                  {detail ? <p className="stage-detail">{detail}</p> : null}
                  {stage.processed != null && stage.total != null ? (
                    <span className="stage-count">
                      {t.stageCount(stage.processed, stage.total)}
                    </span>
                  ) : null}
                </div>
              ) : null}
            </div>
          </section>
        );
      })}
    </div>
  );
}
