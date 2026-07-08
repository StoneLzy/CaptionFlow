import { render, screen } from "@testing-library/react";
import { ProgressTimeline } from "../components/ProgressTimeline";
import { t } from "../i18n";

test("renders localized batch detail, count, and progress bar from processed/total", () => {
  const { container } = render(
    <ProgressTimeline
      t={t.zh}
      stages={[
        {
          name: "translation",
          status: "running",
          detail: "Batch 2 of 5",
          processed: 80,
          total: 200,
        },
      ]}
    />,
  );

  expect(screen.getByText("翻译")).toBeInTheDocument();
  expect(screen.getByText("翻译批次 2/5")).toBeInTheDocument();
  expect(screen.getByText("80 / 200 条字幕")).toBeInTheDocument();
  expect(screen.getByText("40%")).toBeInTheDocument();
  expect(container.querySelector(".stage-progress span")).toHaveStyle({ width: "40%" });
});

test("renders explicit stage percent on the right", () => {
  render(
    <ProgressTimeline
      t={t.zh}
      stages={[
        {
          name: "transcription",
          status: "running",
          detail: "Transcribing audio",
          percent: 42,
        },
      ]}
    />,
  );

  expect(screen.getByText("进行中")).toBeInTheDocument();
  expect(screen.getByText("42%")).toBeInTheDocument();
});

test("prefers explicit percent over processed/total fallback", () => {
  render(
    <ProgressTimeline
      t={t.en}
      stages={[
        {
          name: "translation",
          status: "running",
          detail: "Batch 1 of 2",
          percent: 10,
          processed: 40,
          total: 200,
        },
      ]}
    />,
  );

  expect(screen.getByText("10%")).toBeInTheDocument();
  expect(screen.getByText("Translation batch 1/2")).toBeInTheDocument();
});
