import { useEffect, useRef } from "react";

import type { Translations } from "../i18n";
import { openExternalUrl } from "../utils/openExternalUrl";

const REPO_URL = "https://github.com/StoneLzy/CaptionFlow";
const README_URL = `${REPO_URL}/blob/main/README.md`;
const MATURITY_URL = `${REPO_URL}/blob/main/docs/maturity-audit.md`;

interface Props {
  open: boolean;
  onClose: () => void;
  t: Translations;
}

export function AboutDialog({ open, onClose, t }: Props) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) {
      return;
    }
    if (open && !dialog.open) {
      dialog.showModal();
    }
    if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  return (
    <dialog
      ref={dialogRef}
      className="about-dialog"
      aria-labelledby="about-dialog-title"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClose={onClose}
    >
      <div className="about-dialog-body">
        <header className="about-dialog-header">
          <h2 id="about-dialog-title">{t.aboutTitle}</h2>
          <button className="about-dialog-close" type="button" aria-label={t.closeAbout} onClick={onClose}>
            ×
          </button>
        </header>
        <p>{t.aboutDescription}</p>
        <ul className="about-dialog-list">
          {t.aboutFeatures.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        <p className="about-dialog-note">{t.aboutLocalOnly}</p>
        <div className="about-dialog-links">
          <button type="button" className="about-dialog-link" onClick={() => void openExternalUrl(REPO_URL)}>
            {t.aboutGithub}
          </button>
          <button type="button" className="about-dialog-link" onClick={() => void openExternalUrl(README_URL)}>
            {t.aboutReadme}
          </button>
          <button
            type="button"
            className="about-dialog-link"
            onClick={() => void openExternalUrl(MATURITY_URL)}
          >
            {t.aboutMaturityDoc}
          </button>
        </div>
        <p className="about-dialog-version">{t.aboutVersion}</p>
      </div>
    </dialog>
  );
}
