# CaptionFlow macOS packaging

This project is the macOS app packaging track copied from Translation Middleware.

## Current packaging architecture

- Tauri v2 owns the macOS window and app bundle.
- React/Vite builds into `frontend/dist` and is loaded by Tauri.
- The local WhisperKit runtime lives under `runtime/whisperkit/` during development.
- The Python/FastAPI backend is packaged by PyInstaller as a Tauri sidecar.
- Tauri starts the backend sidecar on a free `127.0.0.1` port and exposes that base URL to the frontend through the `backend_base_url` command.
- The WhisperKit runtime is bundled as a Tauri resource under `Contents/Resources/runtime/whisperkit`.

## Local commands

```bash
npm install
cd frontend && npm install
cd ..
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

## Backend sidecar

`npm run sidecar:build` builds `backend/app/sidecar.py` with PyInstaller and writes the Tauri sidecar binary to:

```text
src-tauri/binaries/captionflow-backend-aarch64-apple-darwin
```

The sidecar binary is intentionally built without MLX/faster-whisper/torch/scipy modules. The ASR factory lazy-loads legacy ASR adapters so the packaged app only ships the WhisperKit path.

The current PyInstaller mode is `--onefile`, so the first backend startup may take several seconds while Python runtime files are extracted. If startup latency becomes annoying, switch to an onedir sidecar/resource layout in a later slice.

## App identity

- Product name: `CaptionFlow`
- Bundle identifier: `com.stonelzy.captionflow`
- Local signing: ad-hoc signing identity `-`
- Local entitlement: `com.apple.security.cs.disable-library-validation` for the PyInstaller backend sidecar.
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

`release/CaptionFlow.app` has been verified to start its backend sidecar and return `status: ok` from `/api/health`.

## Next packaging slices

1. Replace PyInstaller `--onefile` with an onedir sidecar if startup latency matters.
2. Add first-run resource copy/install into `~/Library/Application Support/CaptionFlow/Models` if the model should not stay inside the app bundle.
3. Add Apple Developer ID signing and notarization for distribution outside this machine.
