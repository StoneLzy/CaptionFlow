# CaptionFlow macOS packaging

This project is the macOS app packaging track copied from Translation Middleware.

## Current packaging architecture

- Tauri v2 owns the macOS window and app bundle.
- React/Vite builds into `frontend/dist` and is loaded by Tauri.
- The local WhisperKit runtime lives under `runtime/whisperkit/` during development.
- The Python/FastAPI backend is packaged by PyInstaller in `--onedir` mode.
- Tauri starts the bundled backend executable from `Contents/Resources/runtime/backend` on a free `127.0.0.1` port and exposes that base URL to the frontend through the `backend_base_url` command.
- The WhisperKit runtime is bundled as a Tauri resource under `Contents/Resources/runtime/whisperkit`.
- Bundled media tools live under `Contents/Resources/runtime/media/bin` with ffmpeg dylibs under `runtime/media/lib` on Apple Silicon.

## Local commands

```bash
npm install
cd frontend && npm install
cd ..
./scripts/setup_media_tools.sh --ensure
npm run tauri:build
```

Tauri requires Rust/Cargo in addition to Xcode Command Line Tools.

For local development, install Rust with rustup and make Cargo available in the shell:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
. "$HOME/.cargo/env"
```

## WhisperKit-only runtime

The packaging copy intentionally keeps only the currently used WhisperKit chain:

- `runtime/whisperkit/bin/argmax-cli`
- `runtime/whisperkit/Models/whisperkit-coreml/openai_whisper-large-v3-v20240930_626MB`

The old MLX, faster-whisper, whisper.cpp, and Swift build checkout assets are not required for the initial macOS app package. `runtime/` is ignored by Git because it contains large local binaries/models; the packaging flow should copy or install these resources explicitly.

## Bundled media tools

`./scripts/setup_media_tools.sh --ensure` prepares:

- `runtime/media/bin/ffmpeg`
- `runtime/media/bin/ffprobe`
- `runtime/media/bin/yt-dlp`

On Apple Silicon, ffmpeg/ffprobe are copied from Homebrew together with their dylibs into `runtime/media/lib`, then patched to load via `@executable_path/../lib`. On Intel macOS, static ffmpeg/ffprobe builds are downloaded from evermeet.cx. yt-dlp is always fetched from the official macOS release binary.

Tauri injects `TM_FFMPEG_EXECUTABLE`, `TM_FFPROBE_EXECUTABLE`, and `TM_YTDLP_EXECUTABLE` when starting the backend runtime.

## Backend runtime

`npm run sidecar:build` builds `backend/app/sidecar.py` with PyInstaller and writes the onedir runtime to:

```text
runtime/backend/captionflow-backend/captionflow-backend
```

The backend runtime is intentionally built without MLX/faster-whisper/torch/scipy modules. The ASR factory lazy-loads legacy ASR adapters so the packaged app only ships the WhisperKit path.

The current PyInstaller mode is `--onedir`, so Python runtime files are already expanded inside the app bundle. This avoids the `--onefile` startup extraction cost.

## App identity

- Product name: `CaptionFlow`
- Bundle identifier: `com.stonelzy.captionflow`
- Local signing: ad-hoc signing identity `-`
- Local entitlement: `com.apple.security.cs.disable-library-validation` for the PyInstaller backend runtime.
- Default data directory: `~/Library/Application Support/CaptionFlow`
- Default logs directory: `~/Library/Logs/CaptionFlow`

Ad-hoc signing makes the local `.app` code-sign valid, but it is not notarized.
`spctl` will still reject it for public distribution until a Developer ID
certificate and Apple notarization credentials are configured.

## Current build output

After a successful build, the deliverables are copied to:

```text
release/CaptionFlow.app
release/CaptionFlow_0.1.0_aarch64.dmg
```

`release/CaptionFlow.app` has been verified to start its backend runtime and return `status: ok` from `/api/health`.

## Next packaging slices

1. Add first-run resource copy/install into `~/Library/Application Support/CaptionFlow/Models` if the model should not stay inside the app bundle.
2. Add Apple Developer ID signing and notarization for distribution outside this machine.
