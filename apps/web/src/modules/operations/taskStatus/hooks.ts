import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../../../api/endpoints";

const POLL_FLOOR_MS = 20_000;

export function useTaskRows(incidentId: string) {
  return useQuery({
    queryKey: ["incident", incidentId, "tasks"],
    queryFn: () => api.fetchTaskRows(incidentId),
    refetchInterval: POLL_FLOOR_MS,
  });
}

export function useTaskDetail(incidentId: string, taskId: number) {
  return useQuery({
    queryKey: ["incident", incidentId, "tasks", taskId],
    queryFn: () => api.getTask(incidentId, taskId),
    refetchInterval: POLL_FLOOR_MS,
  });
}

function useInvalidateTasks(incidentId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["incident", incidentId, "tasks"] });
}

export function useCreateTask(incidentId: string) {
  const invalidate = useInvalidateTasks(incidentId);
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.createTask(incidentId, body),
    onSuccess: invalidate,
  });
}

export function useUpdateTask(incidentId: string) {
  const invalidate = useInvalidateTasks(incidentId);
  return useMutation({
    mutationFn: ({ taskId, body }: { taskId: number; body: Record<string, unknown> }) =>
      api.updateTask(incidentId, taskId, body),
    onSuccess: invalidate,
  });
}

export function useSetTaskStatus(incidentId: string) {
  const invalidate = useInvalidateTasks(incidentId);
  return useMutation({
    mutationFn: ({ taskId, statusKey }: { taskId: number; statusKey: string }) =>
      api.setTaskStatus(incidentId, taskId, statusKey),
    onSuccess: invalidate,
  });
}

export function useAddTaskTeam(incidentId: string) {
  const invalidate = useInvalidateTasks(incidentId);
  return useMutation({
    mutationFn: ({ taskId, teamId }: { taskId: number; teamId?: number }) => api.addTaskTeam(incidentId, taskId, teamId),
    onSuccess: invalidate,
  });
}

export function useRemoveTaskTeam(incidentId: string) {
  const invalidate = useInvalidateTasks(incidentId);
  return useMutation({
    mutationFn: ({ taskId, ttId }: { taskId: number; ttId: number }) => api.removeTaskTeam(incidentId, taskId, ttId),
    onSuccess: invalidate,
  });
}

export function useSetTaskTeamPrimary(incidentId: string) {
  const invalidate = useInvalidateTasks(incidentId);
  return useMutation({
    mutationFn: ({ taskId, ttId }: { taskId: number; ttId: number }) => api.setTaskTeamPrimary(incidentId, taskId, ttId),
    onSuccess: invalidate,
  });
}

export function useSetTaskTeamSortie(incidentId: string) {
  const invalidate = useInvalidateTasks(incidentId);
  return useMutation({
    mutationFn: ({ taskId, ttId, sortieId }: { taskId: number; ttId: number; sortieId: string }) =>
      api.setTaskTeamSortie(incidentId, taskId, ttId, sortieId),
    onSuccess: invalidate,
  });
}

export const TASK_STATUS_OPTIONS: { key: string; label: string }[] = [
  { key: "created", label: "Created" },
  { key: "planned", label: "Planned" },
  { key: "assigned", label: "Assigned" },
  { key: "in progress", label: "In Progress" },
  { key: "complete", label: "Complete" },
  { key: "cancelled", label: "Cancelled" },
];
