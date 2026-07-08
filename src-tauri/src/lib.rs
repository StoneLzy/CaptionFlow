use std::{
    io::{BufRead, BufReader, Read},
    net::TcpListener,
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::Mutex,
};

use tauri::{path::BaseDirectory, Manager, RunEvent, State};

const BACKEND_HOST: &str = "127.0.0.1";
const WHISPERKIT_MODEL: &str = "large-v3-v20240930_626MB";

#[derive(Default)]
struct BackendState {
    base_url: Mutex<Option<String>>,
    child: Mutex<Option<Child>>,
}

#[tauri::command]
fn backend_base_url(state: State<'_, BackendState>) -> Result<String, String> {
    state
        .base_url
        .lock()
        .map_err(|_| "backend state is poisoned".to_string())?
        .clone()
        .ok_or_else(|| "backend has not started yet".to_string())
}

fn reserve_local_port() -> Result<u16, String> {
    let listener = TcpListener::bind((BACKEND_HOST, 0))
        .map_err(|error| format!("failed to reserve backend port: {error}"))?;
    let port = listener
        .local_addr()
        .map_err(|error| format!("failed to read backend port: {error}"))?
        .port();
    drop(listener);
    Ok(port)
}

fn resource_path(app: &tauri::App, resource: &str) -> Result<PathBuf, String> {
    app.path()
        .resolve(resource, BaseDirectory::Resource)
        .map_err(|error| format!("failed to resolve resource {resource}: {error}"))
}

fn augmented_path() -> String {
    const EXTRA_PATHS: &[&str] = &[
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/opt/homebrew/sbin",
        "/usr/local/sbin",
    ];
    let existing = std::env::var("PATH").unwrap_or_default();
    if existing.is_empty() {
        EXTRA_PATHS.join(":")
    } else {
        format!("{}:{}", EXTRA_PATHS.join(":"), existing)
    }
}

fn resolve_executable(name: &str) -> Option<PathBuf> {
    for directory in augmented_path().split(':').filter(|part| !part.is_empty()) {
        let candidate = PathBuf::from(directory).join(name);
        if candidate.is_file() {
            return Some(candidate);
        }
    }
    None
}

fn optional_resource_executable(app: &tauri::App, resource: &str) -> Option<PathBuf> {
    resource_path(app, resource)
        .ok()
        .filter(|path| path.is_file())
}

fn configure_media_tool_env(app: &tauri::App, command: &mut Command) {
    command.env("PATH", augmented_path());

    if let Some(ffmpeg) = optional_resource_executable(app, "runtime/media/bin/ffmpeg") {
        command.env("TM_FFMPEG_EXECUTABLE", ffmpeg.as_os_str());
    }
    if let Some(ffprobe) = optional_resource_executable(app, "runtime/media/bin/ffprobe") {
        command.env("TM_FFPROBE_EXECUTABLE", ffprobe.as_os_str());
    }
    if let Some(ytdlp) = optional_resource_executable(app, "runtime/media/bin/yt-dlp") {
        command.env("TM_YTDLP_EXECUTABLE", ytdlp.as_os_str());
    } else if let Some(ytdlp) = resolve_executable("yt-dlp") {
        command.env("TM_YTDLP_EXECUTABLE", ytdlp.as_os_str());
    }
}

#[cfg(unix)]
fn child_process_ids(pid: u32) -> Vec<u32> {
    let output = std::process::Command::new("pgrep")
        .args(["-P", &pid.to_string()])
        .output();

    output
        .ok()
        .filter(|output| output.status.success())
        .map(|output| {
            String::from_utf8_lossy(&output.stdout)
                .lines()
                .filter_map(|line| line.trim().parse::<u32>().ok())
                .collect()
        })
        .unwrap_or_default()
}

#[cfg(unix)]
fn terminate_descendants(pid: u32) {
    for child_pid in child_process_ids(pid) {
        terminate_descendants(child_pid);
        let _ = std::process::Command::new("kill")
            .args(["-TERM", &child_pid.to_string()])
            .status();
    }
}

#[cfg(not(unix))]
fn terminate_descendants(_pid: u32) {}

fn pipe_backend_output(label: &'static str, stream: impl Read + Send + 'static) {
    std::thread::spawn(move || {
        let reader = BufReader::new(stream);
        for line in reader.lines().map_while(Result::ok) {
            eprintln!("[captionflow-backend:{label}] {line}");
        }
    });
}

fn start_backend(app: &mut tauri::App) -> Result<(), String> {
    let port = reserve_local_port()?;
    let base_url = format!("http://{BACKEND_HOST}:{port}");
    let backend_executable = resource_path(
        app,
        "runtime/backend/captionflow-backend/captionflow-backend",
    )?;
    let backend_dir = backend_executable
        .parent()
        .ok_or_else(|| "backend executable has no parent directory".to_string())?;
    let whisperkit_executable = resource_path(app, "runtime/whisperkit/bin/argmax-cli")?;
    let whisperkit_model_path = resource_path(
        app,
        &format!("runtime/whisperkit/Models/whisperkit-coreml/openai_whisper-{WHISPERKIT_MODEL}"),
    )?;

    let port_arg = port.to_string();
    let mut command = Command::new(&backend_executable);
    command
        .current_dir(backend_dir)
        .args([
            "--host",
            BACKEND_HOST,
            "--port",
            port_arg.as_str(),
            "--log-level",
            "warning",
        ])
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .env("TM_ASR_BACKEND", "whisperkit_server")
        .env(
            "TM_WHISPERKIT_EXECUTABLE_PATH",
            whisperkit_executable.as_os_str(),
        )
        .env("TM_WHISPERKIT_CLI_WORKDIR", "")
        .env("TM_WHISPERKIT_MODEL", WHISPERKIT_MODEL)
        .env(
            "TM_WHISPERKIT_MODEL_PATH",
            whisperkit_model_path.as_os_str(),
        );

    configure_media_tool_env(app, &mut command);

    let mut child = command
        .spawn()
        .map_err(|error| format!("failed to spawn backend runtime: {error}"))?;

    if let Some(stdout) = child.stdout.take() {
        pipe_backend_output("stdout", stdout);
    }
    if let Some(stderr) = child.stderr.take() {
        pipe_backend_output("stderr", stderr);
    }

    let state = app.state::<BackendState>();
    *state
        .base_url
        .lock()
        .map_err(|_| "backend state is poisoned".to_string())? = Some(base_url);
    *state
        .child
        .lock()
        .map_err(|_| "backend state is poisoned".to_string())? = Some(child);

    Ok(())
}

fn stop_backend(app: &tauri::AppHandle) {
    if let Some(state) = app.try_state::<BackendState>() {
        if let Ok(mut child) = state.child.lock() {
            if let Some(mut child) = child.take() {
                terminate_descendants(child.id());
                let _ = child.kill();
            }
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .manage(BackendState::default())
        .invoke_handler(tauri::generate_handler![backend_base_url])
        .setup(|app| {
            start_backend(app).map_err(|error| Box::<dyn std::error::Error>::from(error))?;
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building CaptionFlow")
        .run(|app, event| {
            if matches!(event, RunEvent::ExitRequested { .. } | RunEvent::Exit) {
                stop_backend(app);
            }
        });
}
