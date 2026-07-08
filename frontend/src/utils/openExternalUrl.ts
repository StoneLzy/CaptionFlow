export async function openExternalUrl(url: string): Promise<void> {
  const windowWithTauri = window as Window & { __TAURI_INTERNALS__?: unknown };
  if (windowWithTauri.__TAURI_INTERNALS__) {
    const { openUrl } = await import("@tauri-apps/plugin-opener");
    await openUrl(url);
    return;
  }
  window.open(url, "_blank", "noopener,noreferrer");
}
