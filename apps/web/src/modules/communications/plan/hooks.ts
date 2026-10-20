import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../../../api/endpoints";

const POLL_FLOOR_MS = 20_000;

export function useChannelsPlan(incidentId: string) {
  return useQuery({
    queryKey: ["incident", incidentId, "channels_plan"],
    queryFn: () => api.listChannelsPlan(incidentId),
    refetchInterval: POLL_FLOOR_MS,
  });
}

export function useMasterChannels(search = "") {
  return useQuery({
    queryKey: ["master_channels", search],
    queryFn: () => api.listMasterChannels(search),
  });
}

export function useCommunicationsPlan(incidentId: string, opPeriodId: string | null) {
  return useQuery({
    queryKey: ["incident", incidentId, "communications_plan", opPeriodId],
    queryFn: () => api.getCommunicationsPlan(incidentId, opPeriodId),
    enabled: Boolean(incidentId),
  });
}

export function useChannelsPlanValidation(incidentId: string) {
  return useQuery({
    queryKey: ["incident", incidentId, "channels_plan", "validate"],
    queryFn: () => api.validateChannelsPlan(incidentId),
    enabled: false,
  });
}

function useInvalidateChannelsPlan(incidentId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["incident", incidentId, "channels_plan"] });
}

export function useAddChannelFromMaster(incidentId: string) {
  const invalidate = useInvalidateChannelsPlan(incidentId);
  return useMutation({
    mutationFn: ({ masterId, defaults }: { masterId: number; defaults?: Record<string, unknown> }) =>
      api.addChannelFromMaster(incidentId, masterId, defaults),
    onSuccess: invalidate,
  });
}

export function useUpdateChannelPlanRow(incidentId: string) {
  const invalidate = useInvalidateChannelsPlan(incidentId);
  return useMutation({
    mutationFn: ({ rowId, patch }: { rowId: number; patch: Record<string, unknown> }) =>
      api.updateChannelPlanRow(incidentId, rowId, patch),
    onSuccess: invalidate,
  });
}

export function useDeleteChannelPlanRow(incidentId: string) {
  const invalidate = useInvalidateChannelsPlan(incidentId);
  return useMutation({
    mutationFn: (rowId: number) => api.deleteChannelPlanRow(incidentId, rowId),
    onSuccess: invalidate,
  });
}

export function useReorderChannelPlanRow(incidentId: string) {
  const invalidate = useInvalidateChannelsPlan(incidentId);
  return useMutation({
    mutationFn: ({ rowId, direction }: { rowId: number; direction: "up" | "down" }) =>
      api.reorderChannelPlanRow(incidentId, rowId, direction),
    onSuccess: invalidate,
  });
}

export function useSaveCommunicationsPlan(incidentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.saveCommunicationsPlan(incidentId, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["incident", incidentId, "communications_plan"] }),
  });
}

// Matches desktop's ICS-205 editor vocabulary (controller.py COMBO_COLUMN_OPTIONS).
export const CHANNEL_PRIORITY_OPTIONS = ["Primary", "Alternate", "Emergency"];
export const CHANNEL_ENCRYPTION_OPTIONS = ["No", "Yes"];
