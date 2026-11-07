import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../../api/endpoints";

const POLL_FLOOR_MS = 20_000;

export function useHazards(incidentId: string, opPeriod?: number) {
  return useQuery({
    queryKey: ["incident", incidentId, "hazards", opPeriod ?? "all"],
    queryFn: () => api.listHazards(incidentId, opPeriod),
    refetchInterval: POLL_FLOOR_MS,
  });
}

function useInvalidateHazards(incidentId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["incident", incidentId, "hazards"] });
}

export function useCreateHazard(incidentId: string) {
  const invalidate = useInvalidateHazards(incidentId);
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.createHazard(incidentId, body),
    onSuccess: invalidate,
  });
}

export function useUpdateHazard(incidentId: string) {
  const invalidate = useInvalidateHazards(incidentId);
  return useMutation({
    mutationFn: ({ hazardId, body }: { hazardId: number; body: Record<string, unknown> }) => api.updateHazard(incidentId, hazardId, body),
    onSuccess: invalidate,
  });
}

export function useDeleteHazard(incidentId: string) {
  const invalidate = useInvalidateHazards(incidentId);
  return useMutation({
    mutationFn: (hazardId: number) => api.deleteHazard(incidentId, hazardId),
    onSuccess: invalidate,
  });
}

export function useIcs208(incidentId: string, op: number) {
  return useQuery({
    queryKey: ["incident", incidentId, "ics208", op],
    queryFn: () => api.getIcs208(incidentId, op),
    refetchInterval: POLL_FLOOR_MS,
  });
}

export function useSaveIcs208(incidentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.saveIcs208(incidentId, body),
    onSuccess: (_data, variables) =>
      queryClient.invalidateQueries({ queryKey: ["incident", incidentId, "ics208", (variables as { op_period: number }).op_period] }),
  });
}

// ---------------------------------------------------------------------------
// CAP ORM Worksheet
// ---------------------------------------------------------------------------

export function useCapOrmForm(incidentId: string, op: number) {
  return useQuery({
    queryKey: ["incident", incidentId, "cap_orm_form", op],
    queryFn: () => api.getCapOrmForm(incidentId, op),
    refetchInterval: POLL_FLOOR_MS,
  });
}

export function useCapOrmHazards(incidentId: string, op: number) {
  return useQuery({
    queryKey: ["incident", incidentId, "cap_orm_hazards", op],
    queryFn: () => api.listCapOrmHazards(incidentId, op),
    refetchInterval: POLL_FLOOR_MS,
  });
}

function useInvalidateCapOrm(incidentId: string, op: number) {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: ["incident", incidentId, "cap_orm_form", op] });
    queryClient.invalidateQueries({ queryKey: ["incident", incidentId, "cap_orm_hazards", op] });
  };
}

export function useSaveCapOrmForm(incidentId: string, op: number) {
  const invalidate = useInvalidateCapOrm(incidentId, op);
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.saveCapOrmForm(incidentId, body),
    onSuccess: invalidate,
  });
}

export function useCreateCapOrmHazard(incidentId: string, op: number) {
  const invalidate = useInvalidateCapOrm(incidentId, op);
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.createCapOrmHazard(incidentId, body),
    onSuccess: invalidate,
  });
}

export function useUpdateCapOrmHazard(incidentId: string, op: number) {
  const invalidate = useInvalidateCapOrm(incidentId, op);
  return useMutation({
    mutationFn: ({ hazardId, body }: { hazardId: number; body: Record<string, unknown> }) => api.updateCapOrmHazard(incidentId, hazardId, op, body),
    onSuccess: invalidate,
  });
}

export function useDeleteCapOrmHazard(incidentId: string, op: number) {
  const invalidate = useInvalidateCapOrm(incidentId, op);
  return useMutation({
    mutationFn: (hazardId: number) => api.deleteCapOrmHazard(incidentId, hazardId, op),
    onSuccess: invalidate,
  });
}

export function useApproveCapOrmForm(incidentId: string, op: number) {
  const invalidate = useInvalidateCapOrm(incidentId, op);
  return useMutation({
    mutationFn: () => api.approveCapOrmForm(incidentId, op),
    onSuccess: invalidate,
  });
}
