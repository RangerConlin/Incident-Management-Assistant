import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../../../api/endpoints";

const POLL_FLOOR_MS = 20_000;
// NOTE: work_assignments.py writes directly to its raw Mongo collection
// instead of a BaseRepository subclass (same hard-rule violation
// operational_periods.py had, flagged separately), so it never broadcasts
// over the incident WebSocket -- this collection only ever updates via the
// poll floor below, never live.
const COLLECTION = "work_assignments";

export function useWorkAssignments(incidentId: string) {
  return useQuery({
    queryKey: ["incident", incidentId, COLLECTION],
    queryFn: () => api.listWorkAssignments(incidentId),
    refetchInterval: POLL_FLOOR_MS,
  });
}

export function useWorkAssignmentDetail(incidentId: string, waId: number) {
  return useQuery({
    queryKey: ["incident", incidentId, COLLECTION, waId],
    queryFn: () => api.getWorkAssignment(incidentId, waId),
    refetchInterval: POLL_FLOOR_MS,
  });
}

function useInvalidateWorkAssignments(incidentId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["incident", incidentId, COLLECTION] });
}

export function useCreateWorkAssignment(incidentId: string) {
  const invalidate = useInvalidateWorkAssignments(incidentId);
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.createWorkAssignment(incidentId, body),
    onSuccess: invalidate,
  });
}

export function useUpdateWorkAssignment(incidentId: string) {
  const invalidate = useInvalidateWorkAssignments(incidentId);
  return useMutation({
    mutationFn: ({ waId, body }: { waId: number; body: Record<string, unknown> }) =>
      api.updateWorkAssignment(incidentId, waId, body),
    onSuccess: invalidate,
  });
}

export function useArchiveWorkAssignment(incidentId: string) {
  const invalidate = useInvalidateWorkAssignments(incidentId);
  return useMutation({
    mutationFn: (waId: number) => api.archiveWorkAssignment(incidentId, waId),
    onSuccess: invalidate,
  });
}

export function useCloneWorkAssignment(incidentId: string) {
  const invalidate = useInvalidateWorkAssignments(incidentId);
  return useMutation({
    mutationFn: (waId: number) => api.cloneWorkAssignment(incidentId, waId),
    onSuccess: invalidate,
  });
}

export function useAddWorkAssignmentResource(incidentId: string, waId: number) {
  const invalidate = useInvalidateWorkAssignments(incidentId);
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.addWorkAssignmentResource(incidentId, waId, body),
    onSuccess: invalidate,
  });
}

export function useRemoveWorkAssignmentResource(incidentId: string, waId: number) {
  const invalidate = useInvalidateWorkAssignments(incidentId);
  return useMutation({
    mutationFn: (reqId: number) => api.removeWorkAssignmentResource(incidentId, waId, reqId),
    onSuccess: invalidate,
  });
}

export function useAssignWorkAssignmentResource(incidentId: string, waId: number) {
  const invalidate = useInvalidateWorkAssignments(incidentId);
  return useMutation({
    mutationFn: ({ reqId, body }: { reqId: number; body: Record<string, unknown> }) =>
      api.assignWorkAssignmentResource(incidentId, waId, reqId, body),
    onSuccess: invalidate,
  });
}

export function useRemoveWorkAssignmentAssignment(incidentId: string, waId: number) {
  const invalidate = useInvalidateWorkAssignments(incidentId);
  return useMutation({
    mutationFn: ({ reqId, assignmentId }: { reqId: number; assignmentId: number }) =>
      api.removeWorkAssignmentAssignment(incidentId, waId, reqId, assignmentId),
    onSuccess: invalidate,
  });
}

export function useLinkWorkAssignmentTask(incidentId: string, waId: number) {
  const invalidate = useInvalidateWorkAssignments(incidentId);
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.linkWorkAssignmentTask(incidentId, waId, body),
    onSuccess: invalidate,
  });
}

export function useUnlinkWorkAssignmentTask(incidentId: string, waId: number) {
  const invalidate = useInvalidateWorkAssignments(incidentId);
  return useMutation({
    mutationFn: (linkId: number) => api.unlinkWorkAssignmentTask(incidentId, waId, linkId),
    onSuccess: invalidate,
  });
}
