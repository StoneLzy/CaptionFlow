import { FormEvent, useEffect, useRef, useState } from "react";

import {
  fetchSettings,
  testProviderSettings,
  updateSettings,
  type AppSettings,
} from "../api/client";
import type { Translations } from "../i18n";

interface Props {
  open: boolean;
  onClose: () => void;
  onSaved: (settings: AppSettings) => void;
  t: Translations;
}

export function SettingsDialog({ open, onClose, onSaved, t }: Props) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [providerBaseUrl, setProviderBaseUrl] = useState("");
  const [providerModel, setProviderModel] = useState("");
  const [providerApiKey, setProviderApiKey] = useState("");
  const [whisperKitExecutablePath, setWhisperKitExecutablePath] = useState("");
  const [whisperKitModel, setWhisperKitModel] = useState("");
  const [whisperKitModelPath, setWhisperKitModelPath] = useState("");
  const [clearProviderApiKey, setClearProviderApiKey] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) {
      return;
    }
    if (open && !dialog.open) {
      if (typeof dialog.showModal === "function") {
        dialog.showModal();
      } else {
        dialog.setAttribute("open", "");
      }
    }
    if (!open && dialog.open) {
      if (typeof dialog.close === "function") {
        dialog.close();
      } else {
        dialog.removeAttribute("open");
      }
    }
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    setLoading(true);
    setError(null);
    setMessage(null);
    fetchSettings()
      .then((next) => {
        setSettings(next);
        setProviderBaseUrl(next.provider_base_url);
        setProviderModel(next.provider_model);
        setProviderApiKey("");
        setWhisperKitExecutablePath(next.whisperkit_executable_path);
        setWhisperKitModel(next.whisperkit_model);
        setWhisperKitModelPath(next.whisperkit_model_path);
        setClearProviderApiKey(false);
      })
      .catch((fetchError) => {
        setError(
          fetchError instanceof Error ? fetchError.message : t.settingsLoadError,
        );
      })
      .finally(() => setLoading(false));
  }, [open, t.settingsLoadError]);

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const next = await updateSettings({
        provider_base_url: providerBaseUrl,
        provider_model: providerModel,
        ...(providerApiKey.trim()
          ? { provider_api_key: providerApiKey.trim() }
          : {}),
        clear_provider_api_key: clearProviderApiKey,
        whisperkit_executable_path: whisperKitExecutablePath,
        whisperkit_model: whisperKitModel,
        whisperkit_model_path: whisperKitModelPath,
        onboarding_completed: true,
      });
      setSettings(next);
      setProviderApiKey("");
      setClearProviderApiKey(false);
      setMessage(t.settingsSaved);
      onSaved(next);
    } catch (saveError) {
      setError(
        saveError instanceof Error ? saveError.message : t.settingsSaveError,
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleTestProvider() {
    setTesting(true);
    setError(null);
    setMessage(null);
    try {
      await testProviderSettings({
        base_url: providerBaseUrl,
        model: providerModel,
        api_key: providerApiKey,
      });
      setMessage(t.providerConnectionOk);
    } catch (testError) {
      setError(
        testError instanceof Error ? testError.message : t.providerConnectionError,
      );
    } finally {
      setTesting(false);
    }
  }

  const runtimeReady =
    settings?.whisperkit_executable_ready && settings.whisperkit_model_ready;

  return (
    <dialog
      ref={dialogRef}
      className="settings-dialog"
      aria-labelledby="settings-dialog-title"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClose={onClose}
    >
      <form className="settings-dialog-body" onSubmit={handleSave}>
        <header className="about-dialog-header">
          <div>
            <p className="panel-eyebrow">
              {settings?.onboarding_completed ? t.settings : t.firstRun}
            </p>
            <h2 id="settings-dialog-title">{t.settingsTitle}</h2>
          </div>
          <button
            className="about-dialog-close"
            type="button"
            aria-label={t.closeSettings}
            onClick={onClose}
          >
            ×
          </button>
        </header>

        <p className="settings-intro">
          {settings?.onboarding_completed
            ? t.settingsDescription
            : t.firstRunDescription}
        </p>

        {loading ? <p>{t.settingsLoading}</p> : null}
        {!loading && settings ? (
          <>
            <section className="settings-section">
              <div className="settings-section-heading">
                <div>
                  <h3>{t.whisperKitRuntime}</h3>
                  <p>{t.whisperKitRuntimeHint}</p>
                </div>
                <span className={`readiness-badge ${runtimeReady ? "ready" : "not-ready"}`}>
                  {runtimeReady ? t.runtimeReady : t.runtimeNotReady}
                </span>
              </div>
              <label>
                {t.whisperKitExecutablePath}
                <input
                  type="text"
                  value={whisperKitExecutablePath}
                  onChange={(event) =>
                    setWhisperKitExecutablePath(event.target.value)
                  }
                />
              </label>
              <label>
                {t.whisperKitModel}
                <input
                  type="text"
                  value={whisperKitModel}
                  onChange={(event) => setWhisperKitModel(event.target.value)}
                />
              </label>
              <label>
                {t.whisperKitModelPath}
                <input
                  type="text"
                  value={whisperKitModelPath}
                  onChange={(event) => setWhisperKitModelPath(event.target.value)}
                />
              </label>
              {!runtimeReady ? (
                <p className="settings-warning">{t.whisperKitSetupHint}</p>
              ) : null}
            </section>

            <section className="settings-section">
              <div className="settings-section-heading">
                <div>
                  <h3>{t.providerSettings}</h3>
                  <p>{t.providerOptionalHint}</p>
                </div>
              </div>
              <label>
                {t.providerBaseUrl}
                <input
                  type="url"
                  value={providerBaseUrl}
                  placeholder="https://api.openai.com/v1"
                  onChange={(event) => setProviderBaseUrl(event.target.value)}
                />
              </label>
              <label>
                {t.providerModel}
                <input
                  type="text"
                  value={providerModel}
                  onChange={(event) => setProviderModel(event.target.value)}
                />
              </label>
              <label>
                {t.providerApiKey}
                <input
                  type="password"
                  value={providerApiKey}
                  placeholder={
                    settings.provider_api_key_configured
                      ? t.providerApiKeyStored
                      : t.providerApiKeyPlaceholder
                  }
                  onChange={(event) => {
                    setProviderApiKey(event.target.value);
                    if (event.target.value) {
                      setClearProviderApiKey(false);
                    }
                  }}
                />
              </label>
              {settings.provider_api_key_configured ? (
                <label className="settings-checkbox">
                  <input
                    type="checkbox"
                    checked={clearProviderApiKey}
                    onChange={(event) =>
                      setClearProviderApiKey(event.target.checked)
                    }
                  />
                  {t.clearProviderApiKey}
                </label>
              ) : null}
              <button
                className="secondary-button"
                type="button"
                disabled={
                  testing || !providerBaseUrl.trim() || !providerModel.trim()
                }
                onClick={() => void handleTestProvider()}
              >
                {testing ? t.testingProvider : t.testProvider}
              </button>
            </section>

            <section className="settings-paths">
              <p>{t.applicationData}: {settings.data_dir}</p>
              <p>{t.applicationModels}: {settings.models_dir}</p>
              <p>{t.applicationLogs}: {settings.logs_dir}</p>
            </section>
          </>
        ) : null}

        {error ? <p className="form-error" role="alert">{error}</p> : null}
        {message ? <p className="settings-success" role="status">{message}</p> : null}

        <div className="settings-actions">
          <button className="secondary-button" type="button" onClick={onClose}>
            {t.closeSettings}
          </button>
          <button className="primary-button" type="submit" disabled={saving || loading}>
            {saving ? t.savingSettings : t.saveSettings}
          </button>
        </div>
      </form>
    </dialog>
  );
}
