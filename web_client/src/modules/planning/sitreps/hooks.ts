import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../../../api/endpoints";

const POLL_FLOOR_MS = 20_000;
// sitrep.py's SitrepRepository/SitrepEventsRepository both extend
// BaseRepository with these collection names, so they broadcast; events are
// a separate collection from the sitrep documents themselves.
const COLLECTION = "sitreps";
const EVENTS_COLLECTION = "sitrep_events";

export function useSitreps(incidentId: string) {
  return useQuery({
    queryKey: ["incident", incidentId, COLLECTION],
    queryFn: () => api.listSitreps(incidentId),
    refetchInterval: POLL_FLOOR_MS,
  });
}

export function useSitrepDetail(incidentId: string, sitrepId: string) {
  return useQuery({
    queryKey: ["incident", incidentId, COLLECTION, sitrepId],
    queryFn: () => api.getSitrep(incidentId, sitrepId),
    refetchInterval: POLL_FLOOR_MS,
  });
}

export function useSitrepOperationalSummary(incidentId: string) {
  return useQuery({
    queryKey: ["incident", incidentId, "sitrep-operational-summary"],
    queryFn: () => api.getSitrepOperationalSummary(incidentId),
    refetchInterval: POLL_FLOOR_MS,
  });
}

export function useSitrepEvents(incidentId: string, sitrepId?: string) {
  return useQuery({
    queryKey: ["incident", incidentId, EVENTS_COLLECTION, sitrepId ?? "all"],
    queryFn: () => api.listSitrepEvents(incidentId, sitrepId),
    refetchInterval: POLL_FLOOR_MS,
  });
}

export function useSitrepDistributions(incidentId: string, sitrepId: string) {
  return useQuery({
    queryKey: ["incident", incidentId, COLLECTION, sitrepId, "distributions"],
    queryFn: () => api.listSitrepDistributions(incidentId, sitrepId),
  });
}

function useInvalidateSitreps(incidentId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["incident", incidentId, COLLECTION] });
}

export function useCreateSitrep(incidentId: string) {
  const invalidate = useInvalidateSitreps(incidentId);
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.createSitrep(incidentId, body),
    onSuccess: invalidate,
  });
}

export function useUpdateSitrep(incidentId: string) {
  const invalidate = useInvalidateSitreps(incidentId);
  return useMutation({
    mutationFn: ({ sitrepId, body }: { sitrepId: string; body: Record<string, unknown> }) =>
      api.updateSitrep(incidentId, sitrepId, body),
    onSuccess: invalidate,
  });
}

export function useDeleteSitrep(incidentId: string) {
  const invalidate = useInvalidateSitreps(incidentId);
  return useMutation({
    mutationFn: (sitrepId: string) => api.deleteSitrep(incidentId, sitrepId),
    onSuccess: invalidate,
  });
}

export function useDuplicateSitrep(incidentId: string) {
  const invalidate = useInvalidateSitreps(incidentId);
  return useMutation({
    mutationFn: (sitrepId: string) => api.duplicateSitrep(incidentId, sitrepId),
    onSuccess: invalidate,
  });
}

export function useRefreshSitrep(incidentId: string) {
  const invalidate = useInvalidateSitreps(incidentId);
  return useMutation({
    mutationFn: (sitrepId: string) => api.refreshSitrep(incidentId, sitrepId),
    onSuccess: invalidate,
  });
}

export function useCreateSitrepDistribution(incidentId: string, sitrepId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.createSitrepDistribution(incidentId, sitrepId, body),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["incident", incidentId, COLLECTION, sitrepId, "distributions"] }),
  });
}
