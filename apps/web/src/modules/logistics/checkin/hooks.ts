import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../../../api/endpoints";

const POLL_FLOOR_MS = 20_000;

export function useCheckinRoster(incidentId: string, filters: { q?: string; include_no_show?: boolean } = {}) {
  return useQuery({
    queryKey: ["incident", incidentId, "resource_status", "checkin-roster", filters],
    queryFn: () => api.fetchCheckinRoster(incidentId, filters),
    refetchInterval: POLL_FLOOR_MS,
  });
}

function useInvalidateRoster(incidentId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["incident", incidentId, "resource_status"] });
}

export function useSetCheckinStatus(incidentId: string) {
  const invalidate = useInvalidateRoster(incidentId);
  return useMutation({
    mutationFn: ({ personRecord, status }: { personRecord: number; status: string }) =>
      api.setCheckinStatus(incidentId, personRecord, status),
    onSuccess: invalidate,
  });
}

export function usePatchCheckin(incidentId: string) {
  const invalidate = useInvalidateRoster(incidentId);
  return useMutation({
    mutationFn: ({ personRecord, body }: { personRecord: number; body: Record<string, unknown> }) =>
      api.patchCheckin(incidentId, personRecord, body),
    onSuccess: invalidate,
  });
}

export function useSaveCheckin(incidentId: string) {
  const invalidate = useInvalidateRoster(incidentId);
  return useMutation({
    mutationFn: ({ personRecord, body }: { personRecord: number; body: Record<string, unknown> }) =>
      api.saveCheckin(incidentId, personRecord, body),
    onSuccess: invalidate,
  });
}

export const PERSONNEL_STATUS_OPTIONS: { key: string; label: string }[] = [
  { key: "Checked In", label: "Checked In" },
  { key: "Available", label: "Available" },
  { key: "Assigned", label: "Assigned" },
  { key: "Out of Service", label: "Out of Service" },
  { key: "Preparing for Demobilization", label: "Preparing for Demobilization" },
  { key: "Demobilized", label: "Demobilized" },
  { key: "Cancelled", label: "Cancelled" },
];
