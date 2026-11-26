import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../../api/endpoints";
import { ApiError } from "../../api/client";
import type { PlannedRecord, PlannedTool, ScheduleAction, ScheduleTrigger } from "./model";

export const COLLECTIONS = {
  schedule: "planned_event_schedules",
  triggers: "planned_schedule_triggers",
  promotions: "planned_campaigns",
  vendors: "planned_vendors",
  permits: "planned_permits",
  "quick-assignments": "planned_quick_assignments",
  "health-inspections": "planned_health_inspections",
} as const;

const POLL = 20_000;

export function useScheduleItems(id: string) {
  return useQuery({ queryKey: ["incident", id, COLLECTIONS.schedule], queryFn: () => api.listScheduleItems(id), refetchInterval: POLL });
}
export function useScheduleTriggers(id: string) {
  return useQuery({ queryKey: ["incident", id, COLLECTIONS.triggers], queryFn: () => api.listScheduleTriggers(id), refetchInterval: POLL });
}
export function usePlannedRecords(id: string, tool: PlannedTool) {
  return useQuery({ queryKey: ["incident", id, COLLECTIONS[tool]], queryFn: () => api.listPlannedRecords(id, tool), refetchInterval: POLL });
}
export function usePlannedTeams(id: string) {
  return useQuery({ queryKey: ["incident", id, "teams"], queryFn: () => api.listTeams(id), refetchInterval: POLL });
}

/** The server's 409 stale-revision body carries the current record; pull it out when present. */
export function staleCurrent(error: unknown): PlannedRecord | null {
  if (!(error instanceof ApiError) || error.status !== 409) return null;
  const detail = error.detail as { current?: PlannedRecord } | undefined;
  return detail?.current ?? null;
}

export function describeError(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong. Try again.";
}

function useInvalidate(id: string) {
  const client = useQueryClient();
  return (...collections: string[]) => {
    for (const c of collections) void client.invalidateQueries({ queryKey: ["incident", id, c] });
  };
}

export function useScheduleWrites(incidentId: string) {
  const invalidate = useInvalidate(incidentId);
  const all = () => invalidate(COLLECTIONS.schedule, COLLECTIONS.triggers, COLLECTIONS["quick-assignments"]);
  const save = useMutation({
    mutationFn: (v: { recordId?: number; body: Record<string, unknown> }) =>
      v.recordId ? api.updateScheduleItem(incidentId, v.recordId, v.body) : api.createScheduleItem(incidentId, v.body),
    onSuccess: all,
  });
  const act = useMutation({
    mutationFn: (v: { recordId: number; action: ScheduleAction; body: Record<string, unknown> }) => api.runScheduleAction(incidentId, v.recordId, v.action, v.body),
    onSuccess: all,
  });
  const correct = useMutation({
    mutationFn: (v: { recordId: number; body: Record<string, unknown> }) => api.correctScheduleItem(incidentId, v.recordId, v.body),
    onSuccess: all,
  });
  const remove = useMutation({ mutationFn: (recordId: number) => api.deleteScheduleItem(incidentId, recordId), onSuccess: all });
  const createAssignment = useMutation({ mutationFn: (recordId: number) => api.createAssignmentFromActivity(incidentId, recordId), onSuccess: all });
  return { save, act, correct, remove, createAssignment };
}

export function useReminderWrites(incidentId: string) {
  const invalidate = useInvalidate(incidentId);
  const done = () => invalidate(COLLECTIONS.triggers);
  const create = useMutation({ mutationFn: (body: Record<string, unknown>) => api.createScheduleTrigger(incidentId, body), onSuccess: done });
  const update = useMutation({ mutationFn: (v: { recordId: number; body: Record<string, unknown> }) => api.updateScheduleTrigger(incidentId, v.recordId, v.body), onSuccess: done });
  const remove = useMutation({ mutationFn: (t: ScheduleTrigger) => api.deleteScheduleTrigger(incidentId, t.id), onSuccess: done });
  return { create, update, remove };
}

export function usePlannedWrites(incidentId: string, tool: PlannedTool) {
  const invalidate = useInvalidate(incidentId);
  const done = () => invalidate(COLLECTIONS[tool], COLLECTIONS.schedule);
  const save = useMutation({
    mutationFn: (v: { recordId?: number; body: Record<string, unknown> }) =>
      v.recordId ? api.updatePlannedRecord(incidentId, tool, v.recordId, v.body) : api.createPlannedRecord(incidentId, tool, v.body),
    onSuccess: done,
  });
  const remove = useMutation({ mutationFn: (recordId: number) => api.deletePlannedRecord(incidentId, tool, recordId), onSuccess: done });
  const promote = useMutation({
    mutationFn: (v: { recordId: number; by: string }) => api.promoteAssignment(incidentId, v.recordId, v.by),
    onSuccess: () => { done(); invalidate("tasks"); },
  });
  return { save, remove, promote };
}
