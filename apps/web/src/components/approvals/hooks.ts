import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../../api/endpoints";
import { ApiError } from "../../api/client";
import type { ApprovalInstance } from "../../api/types";

const POLL_FLOOR_MS = 20_000;

export function useApprovalInstance(incidentId: string, entityType: string, entityId: string | null) {
  return useQuery({
    queryKey: ["incident", incidentId, "approval_instances", entityType, entityId],
    queryFn: async (): Promise<ApprovalInstance | null> => {
      try {
        return await api.getApprovalInstance(incidentId, entityType, entityId!);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null;
        throw err;
      }
    },
    enabled: Boolean(incidentId) && Boolean(entityId),
    refetchInterval: POLL_FLOOR_MS,
  });
}

function useInvalidateApprovalInstance(incidentId: string, entityType: string, entityId: string | null) {
  const queryClient = useQueryClient();
  return () =>
    queryClient.invalidateQueries({
      queryKey: ["incident", incidentId, "approval_instances", entityType, entityId],
    });
}

export function useStartApproval(incidentId: string, entityType: string, entityId: string | null) {
  const invalidate = useInvalidateApprovalInstance(incidentId, entityType, entityId);
  return useMutation({
    mutationFn: () => api.startApproval(incidentId, entityType, entityId!),
    onSuccess: invalidate,
  });
}

export function useSignApprovalStep(incidentId: string, entityType: string, entityId: string | null) {
  const invalidate = useInvalidateApprovalInstance(incidentId, entityType, entityId);
  return useMutation({
    mutationFn: (body: { step_id: string; actor_id: number; action: "approved" | "rejected" | "acknowledged"; notes?: string }) =>
      api.signApprovalStep(incidentId, entityType, entityId!, body),
    onSuccess: invalidate,
  });
}

export function useAssignApprovalStep(incidentId: string, entityType: string, entityId: string | null) {
  const invalidate = useInvalidateApprovalInstance(incidentId, entityType, entityId);
  return useMutation({
    mutationFn: (body: { step_id: string; actor_id: number }) => api.assignApprovalStep(incidentId, entityType, entityId!, body),
    onSuccess: invalidate,
  });
}

export function usePersonnelSearch(query: string) {
  return useQuery({
    queryKey: ["master_personnel_search", query],
    queryFn: () => api.searchPersonnel(query),
    enabled: query.trim().length > 0,
  });
}
