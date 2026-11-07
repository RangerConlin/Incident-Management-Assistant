import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../../../api/endpoints";

const POLL_FLOOR_MS = 20_000;
// Matches IncidentCollections.INTEL_SUBJECTS exactly — see apps/web/AGENTS.md's
// real-time section for why this string has to match the broadcast collection.
const COLLECTION = "intel_subjects";

export function useSubjectRows(incidentId: string) {
  return useQuery({
    queryKey: ["incident", incidentId, COLLECTION],
    queryFn: () => api.listIntelSubjects(incidentId),
    refetchInterval: POLL_FLOOR_MS,
  });
}

export function useSubjectDetail(incidentId: string, subjectId: string) {
  return useQuery({
    queryKey: ["incident", incidentId, COLLECTION, subjectId],
    queryFn: () => api.getIntelSubject(incidentId, subjectId),
    refetchInterval: POLL_FLOOR_MS,
  });
}

function useInvalidateSubjects(incidentId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["incident", incidentId, COLLECTION] });
}

export function useCreateSubject(incidentId: string) {
  const invalidate = useInvalidateSubjects(incidentId);
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.createIntelSubject(incidentId, body),
    onSuccess: invalidate,
  });
}

export function useUpdateSubject(incidentId: string) {
  const invalidate = useInvalidateSubjects(incidentId);
  return useMutation({
    mutationFn: ({ subjectId, body }: { subjectId: string; body: Record<string, unknown> }) =>
      api.updateIntelSubject(incidentId, subjectId, body),
    onSuccess: invalidate,
  });
}

export function useArchiveSubject(incidentId: string) {
  const invalidate = useInvalidateSubjects(incidentId);
  return useMutation({
    mutationFn: (subjectId: string) => api.archiveIntelSubject(incidentId, subjectId),
    onSuccess: invalidate,
  });
}
