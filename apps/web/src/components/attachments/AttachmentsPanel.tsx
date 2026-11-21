import { useRef, useState } from "react";
import { useSession } from "../../auth/SessionContext";
import { formatDateTime } from "../../utils/formatDateTime";
import { useAttachmentRows, useDeleteAttachment, useDownloadAttachment, useUploadAttachment } from "./hooks";

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface AttachmentsPanelProps {
  incidentId: string;
  /** A generic owner pointer into the attachments router (e.g. "intel_item") — not Intel-specific, any module can pass its own. */
  ownerType: string;
  ownerId: string;
}

// Generic attachments list + upload/download/remove UI — table shape
// matches the Intel Item Detail mockup's Attachments tab (Name/Type/Size/
// Uploaded/By/Notes/Actions), but nothing here is Intel-specific: any
// module can drop this in against its own owner_type/owner_id once it
// needs real attachment storage, same generic pointer the attachments
// router itself uses.
export default function AttachmentsPanel({ incidentId, ownerType, ownerId }: AttachmentsPanelProps) {
  const { user } = useSession();
  const fileInput = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: attachments = [], isLoading, error: loadError } = useAttachmentRows(incidentId, ownerType, ownerId);
  const upload = useUploadAttachment(incidentId, ownerType, ownerId);
  const remove = useDeleteAttachment(incidentId, ownerType, ownerId);
  const download = useDownloadAttachment();

  const onFilesPicked = (files: FileList | null) => {
    if (!files) return;
    setError(null);
    Array.from(files).forEach((file) => {
      upload.mutate(
        { file, uploadedBy: user?.display_name },
        { onError: (err) => setError(err instanceof Error ? err.message : "Upload failed.") },
      );
    });
    if (fileInput.current) fileInput.current.value = "";
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
        <span className="muted">
          {attachments.length} attachment{attachments.length === 1 ? "" : "s"}
        </span>
        <div>
          <input ref={fileInput} type="file" multiple style={{ display: "none" }} onChange={(e) => onFilesPicked(e.target.files)} />
          <button className="secondary" style={{ width: "auto" }} disabled={upload.isPending} onClick={() => fileInput.current?.click()}>
            {upload.isPending ? "Uploading…" : "+ Add File(s)"}
          </button>
        </div>
      </div>

      {error && <p className="error">{error}</p>}
      {loadError && <p className="error">Could not load attachments.</p>}
      {isLoading ? (
        <p>Loading…</p>
      ) : attachments.length === 0 ? (
        <p className="entry-empty">No attachments yet.</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Size</th>
              <th>Uploaded</th>
              <th>By</th>
              <th>Notes</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {attachments.map((a) => (
              <tr key={a.attachment_id}>
                <td>{a.filename}</td>
                <td>{a.mime_type}</td>
                <td>{formatSize(a.size_bytes)}</td>
                <td>{formatDateTime(a.uploaded_at)}</td>
                <td>{a.uploaded_by || "—"}</td>
                <td>{a.description || "—"}</td>
                <td>
                  <button
                    className="secondary"
                    style={{ width: "auto", marginRight: 6 }}
                    disabled={download.isPending}
                    onClick={() => download.mutate({ incidentId, attachmentId: a.attachment_id })}
                  >
                    Open
                  </button>
                  <button
                    className="danger"
                    style={{ width: "auto" }}
                    onClick={() => {
                      if (window.confirm(`Remove "${a.filename}"?`)) remove.mutate(a.attachment_id);
                    }}
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
