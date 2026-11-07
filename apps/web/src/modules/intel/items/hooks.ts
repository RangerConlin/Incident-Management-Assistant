import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../../../api/endpoints";

const POLL_FLOOR_MS = 20_000;
const COLLECTION = "intel_items";

export function useItemRows(incidentId: string) {
  return useQuery({
    queryKey: ["incident", incidentId, COLLECTION],
    queryFn: () => api.listIntelItems(incidentId),
    refetchInterval: POLL_FLOOR_MS,
  });
}

export function useItemDetail(incidentId: string, itemId: string) {
  return useQuery({
    queryKey: ["incident", incidentId, COLLECTION, itemId],
    queryFn: () => api.getIntelItem(incidentId, itemId),
    refetchInterval: POLL_FLOOR_MS,
  });
}

function useInvalidateItems(incidentId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["incident", incidentId, COLLECTION] });
}

export function useCreateItem(incidentId: string) {
  const invalidate = useInvalidateItems(incidentId);
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.createIntelItem(incidentId, body),
    onSuccess: invalidate,
  });
}

export function useUpdateItem(incidentId: string) {
  const invalidate = useInvalidateItems(incidentId);
  return useMutation({
    mutationFn: ({ itemId, body }: { itemId: string; body: Record<string, unknown> }) =>
      api.updateIntelItem(incidentId, itemId, body),
    onSuccess: invalidate,
  });
}

export function useArchiveItem(incidentId: string) {
  const invalidate = useInvalidateItems(incidentId);
  return useMutation({
    mutationFn: (itemId: string) => api.archiveIntelItem(incidentId, itemId),
    onSuccess: invalidate,
  });
}

export function useAddObservation(incidentId: string) {
  const invalidate = useInvalidateItems(incidentId);
  return useMutation({
    mutationFn: ({ itemId, body }: { itemId: string; body: Record<string, unknown> }) =>
      api.addIntelObservation(incidentId, itemId, body),
    onSuccess: invalidate,
  });
}
