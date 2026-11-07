import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../../../api/endpoints";

const POLL_FLOOR_MS = 20_000;
const COLLECTION = "intel_assessments";

export function useAssessmentRows(incidentId: string) {
  return useQuery({
    queryKey: ["incident", incidentId, COLLECTION],
    queryFn: () => api.listIntelAssessments(incidentId),
    refetchInterval: POLL_FLOOR_MS,
  });
}

export function useAssessmentDetail(incidentId: string, assessmentId: string) {
  return useQuery({
    queryKey: ["incident", incidentId, COLLECTION, assessmentId],
    queryFn: () => api.getIntelAssessment(incidentId, assessmentId),
    refetchInterval: POLL_FLOOR_MS,
  });
}

function useInvalidateAssessments(incidentId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["incident", incidentId, COLLECTION] });
}

export function useCreateAssessment(incidentId: string) {
  const invalidate = useInvalidateAssessments(incidentId);
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.createIntelAssessment(incidentId, body),
    onSuccess: invalidate,
  });
}

export function useUpdateAssessment(incidentId: string) {
  const invalidate = useInvalidateAssessments(incidentId);
  return useMutation({
    mutationFn: ({ assessmentId, body }: { assessmentId: string; body: Record<string, unknown> }) =>
      api.updateIntelAssessment(incidentId, assessmentId, body),
    onSuccess: invalidate,
  });
}

export function useArchiveAssessment(incidentId: string) {
  const invalidate = useInvalidateAssessments(incidentId);
  return useMutation({
    mutationFn: (assessmentId: string) => api.archiveIntelAssessment(incidentId, assessmentId),
    onSuccess: invalidate,
  });
}
