import type { StageProgress } from "../types";
import type { Translations } from "../i18n";

interface Props {
  stages: StageProgress[];
  t: Translations;
}

const BATCH_DETAIL_PATTERN = /^Batch (\d+) of (\d+)$/;

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
        return (
          <section className={`timeline-stage status-${stage.status}`} key={stage.name}>
            <div className="stage-header">
              <div className="stage-title">{t.stageLabels[stage.name]}</div>
              <div className="stage-status">
                <span>{t.stageStatusLabels[stage.status]}</span>
                {percent != null ? <strong>{percent}%</strong> : null}
              </div>
            </div>
            {percent != null ? (
              <div className="stage-progress" aria-hidden="true">
                <span style={{ width: `${percent}%` }} />
              </div>
            ) : null}
            {detail ? <p>{detail}</p> : null}
            {stage.processed != null && stage.total != null ? (
              <span className="stage-count">
                {t.stageCount(stage.processed, stage.total)}
              </span>
            ) : null}
          </section>
        );
      })}
    </div>
  );
}
