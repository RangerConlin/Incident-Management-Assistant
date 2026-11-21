import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../../api/endpoints";

const POLL_FLOOR_MS = 20_000;

// Generic attachment hooks — any module can use these against the shared
// GridFS-backed attachments router (owner_type/owner_id), not just Intel.
// Query key includes ownerType/ownerId so different owners never collide.
export function useAttachmentRows(incidentId: string, ownerType: string, ownerId: string) {
  return useQuery({
    queryKey: ["incident", incidentId, "attachments", ownerType, ownerId],
    queryFn: () => api.listAttachments(incidentId, ownerType, ownerId),
    refetchInterval: POLL_FLOOR_MS,
    enabled: Boolean(ownerId),
  });
}

function useInvalidateAttachments(incidentId: string, ownerType: string, ownerId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["incident", incidentId, "attachments", ownerType, ownerId] });
}

export function useUploadAttachment(incidentId: string, ownerType: string, ownerId: string) {
  const invalidate = useInvalidateAttachments(incidentId, ownerType, ownerId);
  return useMutation({
    mutationFn: ({ file, category, uploadedBy, description }: { file: File; category?: string; uploadedBy?: string; description?: string }) =>
      api.uploadAttachment(incidentId, file, {
        owner_type: ownerType,
        owner_id: ownerId,
        category,
        uploaded_by: uploadedBy,
        description,
      }),
    onSuccess: invalidate,
  });
}

export function useDeleteAttachment(incidentId: string, ownerType: string, ownerId: string) {
  const invalidate = useInvalidateAttachments(incidentId, ownerType, ownerId);
  return useMutation({
    mutationFn: (attachmentId: string) => api.deleteAttachment(incidentId, attachmentId),
    onSuccess: invalidate,
  });
}

export function useDownloadAttachment() {
  return useMutation({
    mutationFn: ({ incidentId, attachmentId }: { incidentId: string; attachmentId: string }) => api.downloadAttachment(incidentId, attachmentId),
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
  });
}
