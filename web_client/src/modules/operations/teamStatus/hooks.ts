import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../../../api/endpoints";

const POLL_FLOOR_MS = 20_000;

export function useTeamRows(incidentId: string) {
  return useQuery({
    queryKey: ["incident", incidentId, "teams"],
    queryFn: () => api.fetchTeamAssignmentRows(incidentId),
    refetchInterval: POLL_FLOOR_MS,
  });
}

export function useTeamDetail(incidentId: string, teamId: number) {
  return useQuery({
    queryKey: ["incident", incidentId, "teams", teamId],
    queryFn: () => api.getTeam(incidentId, teamId),
    refetchInterval: POLL_FLOOR_MS,
  });
}

function useInvalidateTeams(incidentId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["incident", incidentId, "teams"] });
}

export function useSetTeamStatus(incidentId: string) {
  const invalidate = useInvalidateTeams(incidentId);
  return useMutation({
    mutationFn: ({ teamId, statusKey }: { teamId: number; statusKey: string }) =>
      api.setTeamStatus(incidentId, teamId, statusKey),
    onSuccess: invalidate,
  });
}

export function useUpdateTeam(incidentId: string) {
  const invalidate = useInvalidateTeams(incidentId);
  return useMutation({
    mutationFn: ({ teamId, body }: { teamId: number; body: Record<string, unknown> }) =>
      api.updateTeam(incidentId, teamId, body),
    onSuccess: invalidate,
  });
}

export function useCreateTeam(incidentId: string) {
  const invalidate = useInvalidateTeams(incidentId);
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.createTeam(incidentId, body),
    onSuccess: invalidate,
  });
}

export function useResetCommPing(incidentId: string) {
  const invalidate = useInvalidateTeams(incidentId);
  return useMutation({
    mutationFn: (teamId: number) => api.resetTeamCommPing(incidentId, teamId),
    onSuccess: invalidate,
  });
}

export function useAssignTeamToTask(incidentId: string) {
  const invalidate = useInvalidateTeams(incidentId);
  return useMutation({
    mutationFn: ({ taskId, teamId }: { taskId: number; teamId: number }) =>
      api.addTaskTeam(incidentId, taskId, teamId),
    onSuccess: invalidate,
  });
}

// Statuses that advance a task_teams timestamp and read oddly with no
// current task assigned — picking one with no task prompts a task picker
// first (TaskPickerDialog), mirroring desktop's status-menu grouping.
export const STATUSES_REQUIRING_TASK = new Set([
  "assigned",
  "briefed",
  "enroute",
  "arrival",
  "find",
  "complete",
  "returning",
]);

export const TEAM_STATUS_OTHER: { key: string; label: string }[] = [
  { key: "available", label: "Available" },
  { key: "out of service", label: "Out of Service" },
  { key: "break", label: "Break" },
  { key: "crew rest", label: "Crew Rest" },
];
