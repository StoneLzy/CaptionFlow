import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { App } from "../App";
import type { JobSummary } from "../types";

function settingsPayload(
  asrBackend = "mlx_whisper",
  onboardingCompleted = true,
) {
  return {
    onboarding_completed: onboardingCompleted,
    data_dir: "/tmp/app/Data",
    models_dir: "/tmp/app/Models",
    logs_dir: "/tmp/app/Logs",
    asr_backend: asrBackend,
    mlx_whisper_model: "mlx-community/whisper-large-v3-mlx",
    mlx_whisper_model_dir: "",
    mlx_whisper_word_timestamps: true,
    whisperkit_executable_path: "/tmp/runtime/argmax-cli",
    whisperkit_executable_ready: true,
    whisperkit_cli_workdir: "/tmp/argmax-oss-swift",
    whisperkit_model: "large-v3-v20240930_626MB",
    whisperkit_model_path: "/tmp/Models/whisperkit",
    whisperkit_model_ready: true,
    whisperkit_host: "127.0.0.1",
    whisperkit_startup_timeout_seconds: 120,
    whisperkit_request_timeout_seconds: 1800,
    asr_max_subtitle_chars: 42,
    asr_max_subtitle_duration_ms: 6000,
    asr_min_subtitle_duration_ms: 800,
    asr_max_word_gap_ms: 800,
    faster_whisper_model: "large-v3-turbo",
    faster_whisper_device: "cpu",
    faster_whisper_compute_type: "int8",
    faster_whisper_vad_filter: true,
    faster_whisper_min_silence_duration_ms: 500,
    faster_whisper_word_timestamps: true,
    faster_whisper_beam_size: 3,
    faster_whisper_cpu_threads: 4,
    whisper_executable_path: "/tmp/whisper",
    whisper_model_path: "/tmp/ggml-large-v3.bin",
    whisper_timestamp_precision: "standard",
    whisper_dtw_preset: "large.v3",
    provider_base_url: "https://api.openai.com/v1",
    provider_model: "gpt-4.1-mini",
    provider_api_key_configured: true,
    provider_api_key_storage: "keychain",
    provider_timeout_seconds: 120,
    translation_batch_size: 40,
    ytdlp_executable: "yt-dlp",
    ytdlp_cookies_configured: false,
  };
}

function jobPayload(status: JobSummary["status"]): JobSummary {
  return {
    id: "job-1",
    filename: "sample.mp4",
    status,
    created_at: "2026-05-30T00:00:00Z",
    updated_at: "2026-05-30T00:00:01Z",
    progress: [
      { name: "upload", status: "completed", detail: "", percent: 100 },
      {
        name: "transcription",
        status: "running",
        detail: "Transcribing audio",
        percent: 42,
        processed: 2,
        total: 5,
      },
      { name: "merge", status: "pending", detail: "" },
      { name: "translation", status: "pending", detail: "" },
      { name: "export", status: "pending", detail: "" },
    ],
    outputs: {},
  };
}

function completedTranscriptOnlyJob(): JobSummary {
  return {
    ...jobPayload("completed"),
    progress: [
      { name: "upload", status: "completed", detail: "", percent: 100 },
      {
        name: "transcription",
        status: "completed",
        detail: "Transcription complete",
        percent: 100,
      },
      { name: "merge", status: "skipped", detail: "Merge disabled" },
      { name: "translation", status: "skipped", detail: "Translation disabled" },
      { name: "export", status: "completed", detail: "", percent: 100 },
    ],
  };
}

function stubFetch({
  jobs = [],
  asrBackend = "mlx_whisper",
  onboardingCompleted = true,
}: {
  jobs?: JobSummary[][];
  asrBackend?: string;
  onboardingCompleted?: boolean;
} = {}) {
  let jobCall = 0;
  const fetchMock = vi.fn().mockImplementation((input: RequestInfo) => {
    const url = typeof input === "string" ? input : input.url;
    if (url === "/api/settings") {
      return Promise.resolve({
        ok: true,
        json: async () => settingsPayload(asrBackend, onboardingCompleted),
      });
    }
    if (url === "/api/health") {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          status: "ok",
          checks: {
            ffmpeg: true,
            ffprobe: true,
            ytdlp: true,
            asr: { backend: asrBackend, ready: true },
            translation_provider: true,
          },
        }),
      });
    }
    if (url === "/api/jobs") {
      const payload = jobs[Math.min(jobCall, Math.max(jobs.length - 1, 0))] ?? [];
      jobCall += 1;
      return Promise.resolve({
        ok: true,
        json: async () => payload,
      });
    }
    return Promise.resolve({
      ok: true,
      json: async () => [],
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

beforeEach(() => {
  const storage = new Map<string, string>();
  const localStorageStub = {
    getItem: vi.fn((key: string) => storage.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => storage.set(key, value)),
    removeItem: vi.fn((key: string) => storage.delete(key)),
    clear: vi.fn(() => storage.clear()),
  };
  Object.defineProperty(window, "localStorage", {
    value: localStorageStub,
    configurable: true,
  });
  vi.stubGlobal("localStorage", localStorageStub);
  stubFetch();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

test("defaults to Chinese workbench labels", async () => {
  render(<App />);

  expect(await screen.findByText("暂无任务。")).toBeInTheDocument();
  expect(screen.getByLabelText("视频或 SRT 文件")).toBeInTheDocument();
  expect(screen.getByLabelText("源语言")).toHaveValue("auto");
  expect(screen.getByLabelText("目标语言")).toHaveValue("zh-Hans");
  expect(screen.getByText("处理流程")).toBeInTheDocument();
  expect(screen.getByText("转写")).toBeInTheDocument();
  expect(screen.getByText("字幕合并")).toBeInTheDocument();
  expect(screen.getByText("翻译")).toBeInTheDocument();
  expect(screen.getByLabelText("Provider Base URL")).toBeInTheDocument();
  expect(screen.getByLabelText("术语表")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "开始任务" })).toBeDisabled();
});

test("switches the interface to English and persists the choice", async () => {
  const user = userEvent.setup();
  render(<App />);

  await user.click(await screen.findByRole("button", { name: "EN" }));

  expect(screen.getByText("No jobs yet.")).toBeInTheDocument();
  expect(screen.getByLabelText("Video or SRT file")).toBeInTheDocument();
  expect(localStorage.getItem("tm_ui_language")).toBe("en");
});

test("polls while a job is created or running", async () => {
  vi.useFakeTimers();
  const fetchMock = stubFetch({
    jobs: [[jobPayload("created")], [jobPayload("running")], [jobPayload("completed")]],
  });

  render(<App />);
  await act(async () => {
    await Promise.resolve();
  });
  expect(screen.getAllByText("sample.mp4").length).toBeGreaterThan(0);

  await act(async () => {
    await vi.advanceTimersByTimeAsync(2000);
  });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(2000);
  });

  const jobListCalls = fetchMock.mock.calls.filter(([input]) => input === "/api/jobs");
  expect(jobListCalls).toHaveLength(3);
});

test("shows completed transcript-only jobs as 100 percent", async () => {
  stubFetch({ jobs: [[completedTranscriptOnlyJob()]] });

  render(<App />);

  expect(await screen.findByText("sample.mp4")).toBeInTheDocument();
  expect(screen.getAllByText("100%").length).toBeGreaterThan(0);
  expect(screen.getAllByText("已跳过")).toHaveLength(2);
});

test("opens the selected job output folder", async () => {
  const fetchMock = stubFetch({ jobs: [[completedTranscriptOnlyJob()]] });
  const user = userEvent.setup();

  render(<App />);

  await user.click(await screen.findByRole("button", { name: "打开输出文件夹" }));

  expect(fetchMock).toHaveBeenCalledWith("/api/jobs/job-1/open-folder", {
    method: "POST",
  });
});

test("shows whisperkit server model when configured", async () => {
  stubFetch({ asrBackend: "whisperkit_server" });
  const user = userEvent.setup();
  render(<App />);

  const input = await screen.findByLabelText("视频或 SRT 文件");
  const file = new File(["video"], "sample.mp4", { type: "video/mp4" });
  await user.upload(input, file);

  expect(
    await screen.findByText("WhisperKit: large-v3-v20240930_626MB"),
  ).toBeInTheDocument();
  expect(screen.queryByLabelText("时间戳精度")).not.toBeInTheDocument();
});

test("opens settings automatically on first launch", async () => {
  stubFetch({ onboardingCompleted: false, asrBackend: "whisperkit_server" });

  render(<App />);

  expect(await screen.findByRole("dialog")).toBeInTheDocument();
  expect(screen.getByText("首次启动")).toBeInTheDocument();
  expect(screen.getByText("WhisperKit 运行时")).toBeInTheDocument();
  expect(screen.getByText("已就绪")).toBeInTheDocument();
});

test("saves application settings through the settings API", async () => {
  const fetchMock = stubFetch({ asrBackend: "whisperkit_server" });
  const user = userEvent.setup();
  render(<App />);

  await user.click(await screen.findByRole("button", { name: "设置" }));
  const dialog = await screen.findByRole("dialog");
  await user.clear(
    within(dialog).getByLabelText("Provider 模型"),
  );
  await user.type(
    within(dialog).getByLabelText("Provider 模型"),
    "new-model",
  );
  await user.click(
    within(dialog).getByRole("button", { name: "保存并继续" }),
  );

  expect(fetchMock).toHaveBeenCalledWith(
    "/api/settings",
    expect.objectContaining({
      method: "PATCH",
      body: expect.stringContaining('"provider_model":"new-model"'),
    }),
  );
});
