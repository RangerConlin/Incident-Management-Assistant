import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../../../api/endpoints";

const POLL_FLOOR_MS = 20_000;

export function useCheckinRoster(
  incidentId: string,
  filters: { q?: string; ci_status?: string; include_no_show?: boolean } = {}
) {
  return useQuery({
    queryKey: ["incident", incidentId, "resource_status", "checkin-roster", filters],
    queryFn: () => api.fetchCheckinRoster(incidentId, filters),
    refetchInterval: POLL_FLOOR_MS,
  });
}

function useInvalidateRoster(incidentId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["incident", incidentId, "resource_status"] });
}

export function useSetCheckinStatus(incidentId: string) {
  const invalidate = useInvalidateRoster(incidentId);
  return useMutation({
    mutationFn: ({ personRecord, status }: { personRecord: number; status: string }) =>
      api.setCheckinStatus(incidentId, personRecord, status),
    onSuccess: invalidate,
  });
}

export function usePatchCheckin(incidentId: string) {
  const invalidate = useInvalidateRoster(incidentId);
  return useMutation({
    mutationFn: ({ personRecord, body }: { personRecord: number; body: Record<string, unknown> }) =>
      api.patchCheckin(incidentId, personRecord, body),
    onSuccess: invalidate,
  });
}

export function useSaveCheckin(incidentId: string) {
  const invalidate = useInvalidateRoster(incidentId);
  return useMutation({
    mutationFn: ({ personRecord, body }: { personRecord: number; body: Record<string, unknown> }) =>
      api.saveCheckin(incidentId, personRecord, body),
    onSuccess: invalidate,
  });
}

export function useCheckinHistory(incidentId: string, personRecord: number | null) {
  return useQuery({
    queryKey: ["incident", incidentId, "resource_status", "checkin-history", personRecord],
    queryFn: () => api.listCheckinHistory(incidentId, personRecord as number),
    enabled: personRecord !== null,
  });
}

// ---- Groups / Teams tab -----------------------------------------------

export function useCheckinTeams(incidentId: string, checkedIn: boolean) {
  return useQuery({
    queryKey: ["incident", incidentId, "teams", "checkin-state", checkedIn],
    queryFn: () => api.listCheckinTeams(incidentId, checkedIn, false),
    refetchInterval: POLL_FLOOR_MS,
  });
}

function useInvalidateTeams(incidentId: string) {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: ["incident", incidentId, "teams"] });
    queryClient.invalidateQueries({ queryKey: ["incident", incidentId, "resource_status"] });
  };
}

export function useTeamCheckIn(incidentId: string) {
  const invalidate = useInvalidateTeams(incidentId);
  return useMutation({
    mutationFn: ({
      teamId,
      keepTogether,
    }: {
      teamId: number;
      keepTogether: boolean;
    }) => api.teamCheckIn(incidentId, teamId, { keep_together: keepTogether, checked_in_by: "Check-In" }),
    onSuccess: invalidate,
  });
}

export function useTeamDisband(incidentId: string) {
  const invalidate = useInvalidateTeams(incidentId);
  return useMutation({
    mutationFn: ({ teamId }: { teamId: number }) => api.teamDisband(incidentId, teamId, { disbanded_by: "Check-In" }),
    onSuccess: invalidate,
  });
}

export function useSetTeamPlanningStatus(incidentId: string) {
  const invalidate = useInvalidateTeams(incidentId);
  return useMutation({
    mutationFn: ({ teamId, status }: { teamId: number; status: string }) => api.updateTeam(incidentId, teamId, { status }),
    onSuccess: invalidate,
  });
}

// ---- Vehicle / Aircraft / Equipment status actions ----------------------

export function useSetResourceStatusByEntity(incidentId: string) {
  const invalidate = useInvalidateRoster(incidentId);
  return useMutation({
    mutationFn: async ({
      entityType,
      recordId,
      status,
    }: {
      entityType: string;
      recordId: string | number;
      status: string;
    }) => {
      const existing = await api.getResourceStatusByEntity(incidentId, entityType, recordId);
      const itemId = existing?.id;
      if (!itemId) throw new Error("This resource has no check-in record yet — check it in first.");
      return api.setResourceStatusStatus(incidentId, itemId, status);
    },
    onSuccess: invalidate,
  });
}

// ---- Add New Record ------------------------------------------------------

export function useCreateMasterRecord(kind: "personnel" | "vehicle" | "aircraft" | "equipment") {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: Record<string, unknown>): Promise<unknown> => {
      if (kind === "personnel") return api.createMasterPersonnel(body);
      if (kind === "vehicle") return api.createMasterVehicle(body);
      if (kind === "aircraft") return api.createMasterAircraft(body);
      return api.createMasterEquipment(body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["master", kind] });
    },
  });
}

export const PERSONNEL_STATUS_OPTIONS: { key: string; label: string }[] = [
  { key: "Checked In", label: "Checked In" },
  { key: "Available", label: "Available" },
  { key: "Assigned", label: "Assigned" },
  { key: "Out of Service", label: "Out of Service" },
  { key: "Preparing for Demobilization", label: "Preparing for Demobilization" },
  { key: "Demobilized", label: "Demobilized" },
  { key: "Cancelled", label: "Cancelled" },
];
