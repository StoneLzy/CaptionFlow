export async function selectDirectory(currentValue = ""): Promise<string | null> {
  const windowWithTauri = window as Window & { __TAURI_INTERNALS__?: unknown };
  if (!windowWithTauri.__TAURI_INTERNALS__) {
    return window.prompt("Output directory", currentValue) || null;
  }

  const { open } = await import("@tauri-apps/plugin-dialog");
  const selected = await open({
    directory: true,
    multiple: false,
    defaultPath: currentValue || undefined,
  });
  return typeof selected === "string" ? selected : null;
}
