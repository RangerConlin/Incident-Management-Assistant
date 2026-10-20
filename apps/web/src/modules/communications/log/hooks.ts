import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../../../api/endpoints";

const POLL_FLOOR_MS = 20_000;

export function useCommsLog(incidentId: string, filters: Record<string, string | boolean> = {}) {
  return useQuery({
    queryKey: ["incident", incidentId, "communications_log", filters],
    queryFn: () => api.listCommsLog(incidentId, filters),
    refetchInterval: POLL_FLOOR_MS,
  });
}

export function useCommsContacts(incidentId: string) {
  return useQuery({
    queryKey: ["incident", incidentId, "comms-contacts"],
    queryFn: () => api.listCommsContacts(incidentId),
  });
}

function useInvalidateCommsLog(incidentId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["incident", incidentId, "communications_log"] });
}

export function useAddCommsLogEntry(incidentId: string) {
  const invalidate = useInvalidateCommsLog(incidentId);
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.addCommsLogEntry(incidentId, body),
    onSuccess: invalidate,
  });
}

export function useUpdateCommsLogEntry(incidentId: string) {
  const invalidate = useInvalidateCommsLog(incidentId);
  return useMutation({
    mutationFn: ({ entryId, patch }: { entryId: number; patch: Record<string, unknown> }) =>
      api.updateCommsLogEntry(incidentId, entryId, patch),
    onSuccess: invalidate,
  });
}

export const COMMS_PRIORITY_OPTIONS = ["Routine", "Priority", "Emergency"];
export const COMMS_DISPOSITION_OPTIONS = ["Open", "Closed"];
