import { useState } from "react";
import { useSession } from "../../auth/SessionContext";
import { useDownloadForm } from "./hooks";

// A single-click export action for a form that needs no source record or
// operational-period choice (e.g. ICS-202 from Incident Objectives) — the
// toolbar-button alternative to the old always-open FormExportControls
// panel, matching desktop's "Export" toolbar button pattern.
export default function ExportButton({ formId, label }: { formId: string; label: string }) {
  const { incidentId, user } = useSession();
  const download = useDownloadForm(incidentId!);
  const [error, setError] = useState<string | null>(null);

  const onClick = () => {
    setError(null);
    download.mutate(
      { form_id: formId, prepared_by: user?.display_name || user?.username || "" },
      {
        onSuccess: (result) => {
          const url = URL.createObjectURL(result.blob);
          const anchor = document.createElement("a");
          anchor.href = url;
          anchor.download = result.filename;
          document.body.appendChild(anchor);
          anchor.click();
          anchor.remove();
          window.setTimeout(() => URL.revokeObjectURL(url), 1000);
        },
        onError: (err) => setError(err instanceof Error ? err.message : "Export failed."),
      }
    );
  };

  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
      <button type="button" className="secondary" style={{ width: "auto" }} onClick={onClick} disabled={download.isPending}>
        {download.isPending ? "Exporting…" : label}
      </button>
      {error && <span className="error" style={{ fontSize: "0.8rem" }}>{error}</span>}
    </span>
  );
}
