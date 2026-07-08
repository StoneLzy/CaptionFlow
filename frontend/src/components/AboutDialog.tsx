import { useEffect, useRef } from "react";

import type { Translations } from "../i18n";

const REPO_URL = "https://github.com/StoneLzy/CaptionFlow";
const README_URL = `${REPO_URL}/blob/master/README.md`;
const MATURITY_URL = `${REPO_URL}/blob/master/docs/maturity-audit.md`;

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
          <a href={REPO_URL} target="_blank" rel="noreferrer">
            {t.aboutGithub}
          </a>
          <a href={README_URL} target="_blank" rel="noreferrer">
            {t.aboutReadme}
          </a>
          <a href={MATURITY_URL} target="_blank" rel="noreferrer">
            {t.aboutMaturityDoc}
          </a>
        </div>
        <p className="about-dialog-version">{t.aboutVersion}</p>
      </div>
    </dialog>
  );
}
