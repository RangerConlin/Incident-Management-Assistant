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

export function useTaskWorkAssignments(incidentId: string, taskId: number) {
  return useQuery({
    queryKey: ["incident", incidentId, "work_assignments", "task-links", taskId],
    queryFn: () => api.listWorkAssignmentsForTask(incidentId, taskId),
    refetchInterval: POLL_FLOOR_MS,
  });
}

function useInvalidateTaskWorkAssignments(incidentId: string, taskId: number) {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: ["incident", incidentId, "work_assignments"] });
    queryClient.invalidateQueries({ queryKey: ["incident", incidentId, "tasks", taskId] });
  };
}

export function useLinkTaskWorkAssignment(incidentId: string, taskId: number) {
  const invalidate = useInvalidateTaskWorkAssignments(incidentId, taskId);
  return useMutation({
    mutationFn: (waId: number) => api.linkWorkAssignmentTask(incidentId, waId, { task_id: taskId }),
    onSuccess: invalidate,
  });
}

export function useUnlinkTaskWorkAssignment(incidentId: string, taskId: number) {
  const invalidate = useInvalidateTaskWorkAssignments(incidentId, taskId);
  return useMutation({
    mutationFn: ({ waId, linkId }: { waId: number; linkId: number }) =>
      api.unlinkWorkAssignmentTask(incidentId, waId, linkId),
    onSuccess: invalidate,
  });
}

// Mirrors desktop's modules/operations/taskings/data/lookups.py — category
// gates the available task types there via a cascading dropdown.
export const TASK_CATEGORIES = [
  "Air SAR",
  "Damage Assessment",
  "Ground SAR",
  "Logistics Support",
  "Other",
  "Photography",
  "Relocation",
];

export const TASK_TYPES_BY_CATEGORY: Record<string, string[]> = {
  "Air SAR": ["ELT Search", "Creeping Line", "Parallel Track", "Sector Search", "Photo Recon", "Route Search"],
  "Ground SAR": ["Hasty", "Area", "Grid", "Tracking", "Clue Follow-up", "Electronic Grid Search"],
  "Damage Assessment": ["Wind/Storm Survey", "Flood Assessment", "Wildfire Perimeter", "Infrastructure Survey"],
  "Logistics Support": ["Transport", "Supply Run", "Staging Support", "Shelter Support"],
  "Photography": ["Aerial Photo", "Ground Photo", "Video Recon"],
  "Relocation": ["Relocate Team", "Relocate Aircraft", "Relocate Equipment"],
  "Other": ["Other/Custom"],
};

export const TASK_PRIORITIES = ["Low", "Medium", "High", "Critical"];

export const TASK_STATUS_OPTIONS: { key: string; label: string }[] = [
  { key: "created", label: "Created" },
  { key: "planned", label: "Planned" },
  { key: "assigned", label: "Assigned" },
  { key: "in progress", label: "In Progress" },
  { key: "complete", label: "Complete" },
  { key: "cancelled", label: "Cancelled" },
];
