import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../../../api/endpoints";

const POLL_FLOOR_MS = 20_000;

// "incident_objectives" matches ObjectivesRepository.collection_name
// (data/db/sarapp_db/api/routers/objectives.py) exactly, which is the
// string IncidentSocketProvider's invalidation uses as msg.collection — see
// web_client/AGENTS.md's real-time section for why this has to match.
const COLLECTION = "incident_objectives";

export function useObjectiveRows(incidentId: string) {
  return useQuery({
    queryKey: ["incident", incidentId, COLLECTION],
    queryFn: () => api.listObjectives(incidentId),
    refetchInterval: POLL_FLOOR_MS,
  });
}

export function useObjectiveDetail(incidentId: string, objectiveId: string) {
  return useQuery({
    queryKey: ["incident", incidentId, COLLECTION, objectiveId],
    queryFn: () => api.getObjective(incidentId, objectiveId),
    refetchInterval: POLL_FLOOR_MS,
  });
}

function useInvalidateObjectives(incidentId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["incident", incidentId, COLLECTION] });
}

export function useCreateObjective(incidentId: string) {
  const invalidate = useInvalidateObjectives(incidentId);
  return useMutation({
    mutationFn: (body: Parameters<typeof api.createObjective>[1]) => api.createObjective(incidentId, body),
    onSuccess: invalidate,
  });
}

export function useUpdateObjective(incidentId: string) {
  const invalidate = useInvalidateObjectives(incidentId);
  return useMutation({
    mutationFn: ({ objectiveId, body }: { objectiveId: string; body: Parameters<typeof api.updateObjective>[2] }) =>
      api.updateObjective(incidentId, objectiveId, body),
    onSuccess: invalidate,
  });
}

export function useDeleteObjective(incidentId: string) {
  const invalidate = useInvalidateObjectives(incidentId);
  return useMutation({
    mutationFn: (objectiveId: string) => api.deleteObjective(incidentId, objectiveId),
    onSuccess: invalidate,
  });
}

export function useReorderObjectives(incidentId: string) {
  const invalidate = useInvalidateObjectives(incidentId);
  return useMutation({
    mutationFn: (ids: string[]) => api.reorderObjectives(incidentId, ids),
    onSuccess: invalidate,
  });
}

export function useLinkObjectiveTask(incidentId: string, objectiveId: string) {
  const invalidate = useInvalidateObjectives(incidentId);
  return useMutation({
    mutationFn: (body: Parameters<typeof api.linkObjectiveTask>[2]) =>
      api.linkObjectiveTask(incidentId, objectiveId, body),
    onSuccess: invalidate,
  });
}

export function useUnlinkObjectiveTask(incidentId: string, objectiveId: string) {
  const invalidate = useInvalidateObjectives(incidentId);
  return useMutation({
    mutationFn: (linkId: number) => api.unlinkObjectiveTask(incidentId, objectiveId, linkId),
    onSuccess: invalidate,
  });
}

export function useObjectiveAudit(incidentId: string, objectiveId: string) {
  return useQuery({
    queryKey: ["incident", incidentId, COLLECTION, objectiveId, "audit"],
    queryFn: () => api.listObjectiveAudit(incidentId, objectiveId),
  });
}
