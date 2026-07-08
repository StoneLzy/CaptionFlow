use std::{
    net::TcpListener,
    path::PathBuf,
    sync::Mutex,
};

use tauri::{path::BaseDirectory, Manager, RunEvent, State};
use tauri_plugin_shell::{
    process::{CommandChild, CommandEvent},
    ShellExt,
};

const BACKEND_HOST: &str = "127.0.0.1";
const WHISPERKIT_MODEL: &str = "large-v3-v20240930_626MB";

#[derive(Default)]
struct BackendState {
    base_url: Mutex<Option<String>>,
    child: Mutex<Option<CommandChild>>,
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

fn start_backend(app: &mut tauri::App) -> Result<(), String> {
    let port = reserve_local_port()?;
    let base_url = format!("http://{BACKEND_HOST}:{port}");
    let whisperkit_executable = resource_path(app, "runtime/whisperkit/bin/argmax-cli")?;
    let whisperkit_model_path = resource_path(
        app,
        &format!("runtime/whisperkit/Models/whisperkit-coreml/openai_whisper-{WHISPERKIT_MODEL}"),
    )?;

    let app_handle = app.handle().clone();
    let (mut rx, child) = app
        .shell()
        .sidecar("captionflow-backend")
        .map_err(|error| format!("failed to prepare backend sidecar: {error}"))?
        .args([
            "--host".to_string(),
            BACKEND_HOST.to_string(),
            "--port".to_string(),
            port.to_string(),
            "--log-level".to_string(),
            "warning".to_string(),
        ])
        .env("TM_ASR_BACKEND", "whisperkit_server")
        .env("TM_WHISPERKIT_EXECUTABLE_PATH", whisperkit_executable.as_os_str())
        .env("TM_WHISPERKIT_CLI_WORKDIR", "")
        .env("TM_WHISPERKIT_MODEL", WHISPERKIT_MODEL)
        .env("TM_WHISPERKIT_MODEL_PATH", whisperkit_model_path.as_os_str())
        .spawn()
        .map_err(|error| format!("failed to spawn backend sidecar: {error}"))?;

    let state = app.state::<BackendState>();
    *state
        .base_url
        .lock()
        .map_err(|_| "backend state is poisoned".to_string())? = Some(base_url);
    *state
        .child
        .lock()
        .map_err(|_| "backend state is poisoned".to_string())? = Some(child);

    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stderr(bytes) => {
                    eprintln!("[captionflow-backend] {}", String::from_utf8_lossy(&bytes));
                }
                CommandEvent::Stdout(bytes) => {
                    println!("[captionflow-backend] {}", String::from_utf8_lossy(&bytes));
                }
                CommandEvent::Terminated(payload) => {
                    eprintln!("[captionflow-backend] terminated: {:?}", payload.code);
                    if let Some(state) = app_handle.try_state::<BackendState>() {
                        if let Ok(mut child) = state.child.lock() {
                            child.take();
                        }
                    }
                    break;
                }
                CommandEvent::Error(error) => {
                    eprintln!("[captionflow-backend] error: {error}");
                }
                _ => {}
            }
        }
    });

    Ok(())
}

fn stop_backend(app: &tauri::AppHandle) {
    if let Some(state) = app.try_state::<BackendState>() {
        if let Ok(mut child) = state.child.lock() {
            if let Some(child) = child.take() {
                let _ = child.kill();
            }
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .manage(BackendState::default())
        .invoke_handler(tauri::generate_handler![backend_base_url])
        .setup(|app| {
            start_backend(app).map_err(|error| Box::<dyn std::error::Error>::from(error))?;
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building CaptionFlow")
        .run(|app, event| {
            if let RunEvent::ExitRequested { .. } = event {
                stop_backend(app);
            }
        });
}
