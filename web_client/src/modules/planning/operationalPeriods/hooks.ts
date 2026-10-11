import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../../../api/endpoints";

const POLL_FLOOR_MS = 20_000;

// NOTE: operational_periods.py writes directly to its raw Mongo collection
// instead of going through a BaseRepository subclass, so it never broadcasts
// over the incident WebSocket like objectives/meetings do (flagged
// separately as a hard-rule violation to fix). Until that's fixed, this
// collection only ever updates via the poll floor below, never live.
const COLLECTION = "operational_periods";

export function useOperationalPeriods(incidentId: string) {
  return useQuery({
    queryKey: ["incident", incidentId, COLLECTION],
    queryFn: () => api.listOperationalPeriods(incidentId),
    refetchInterval: POLL_FLOOR_MS,
  });
}

export function useActiveOperationalPeriod(incidentId: string) {
  return useQuery({
    queryKey: ["incident", incidentId, COLLECTION, "active"],
    queryFn: () => api.getActiveOperationalPeriod(incidentId),
    refetchInterval: POLL_FLOOR_MS,
  });
}

function useInvalidateOperationalPeriods(incidentId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["incident", incidentId, COLLECTION] });
}

export function useCreateOperationalPeriod(incidentId: string) {
  const invalidate = useInvalidateOperationalPeriods(incidentId);
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.createOperationalPeriod(incidentId, body),
    onSuccess: invalidate,
  });
}

export function useUpdateOperationalPeriod(incidentId: string) {
  const invalidate = useInvalidateOperationalPeriods(incidentId);
  return useMutation({
    mutationFn: ({ periodId, body }: { periodId: number; body: Record<string, unknown> }) =>
      api.updateOperationalPeriod(incidentId, periodId, body),
    onSuccess: invalidate,
  });
}

export function useSetActiveOperationalPeriod(incidentId: string) {
  const invalidate = useInvalidateOperationalPeriods(incidentId);
  return useMutation({
    mutationFn: (periodId: number) => api.setActiveOperationalPeriod(incidentId, periodId),
    onSuccess: invalidate,
  });
}

export function useCloneOperationalPeriod(incidentId: string) {
  const invalidate = useInvalidateOperationalPeriods(incidentId);
  return useMutation({
    mutationFn: (periodId: number) => api.cloneOperationalPeriod(incidentId, periodId),
    onSuccess: invalidate,
  });
}
