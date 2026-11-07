import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../../api/endpoints";
import type { MedicalPlanTable } from "../../api/types";

const POLL_FLOOR_MS = 20_000;
const COLLECTION = "medical_plan";

export function useMedicalPlan(incidentId: string, op: number, version?: number) {
  return useQuery({
    queryKey: ["incident", incidentId, COLLECTION, op, version ?? "latest"],
    queryFn: () => api.getMedicalPlan(incidentId, op, version),
    refetchInterval: POLL_FLOOR_MS,
  });
}

export function useMedicalPlanVersions(incidentId: string, op: number) {
  return useQuery({
    queryKey: ["incident", incidentId, COLLECTION, op, "versions"],
    queryFn: () => api.listMedicalPlanVersions(incidentId, op),
    refetchInterval: POLL_FLOOR_MS,
  });
}

export function useMedicalAidStations(incidentId: string, op: number, version?: number) {
  return useQuery({
    queryKey: ["incident", incidentId, "medical_aid_stations", op, version ?? "latest"],
    queryFn: () => api.listMedicalAidStations(incidentId, op, version),
    refetchInterval: POLL_FLOOR_MS,
  });
}

function useInvalidateMedicalPlan(incidentId: string) {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: ["incident", incidentId, COLLECTION] });
    queryClient.invalidateQueries({ queryKey: ["incident", incidentId, "medical_aid_stations"] });
  };
}

export function useCreateMedicalPlanVersion(incidentId: string) {
  const invalidate = useInvalidateMedicalPlan(incidentId);
  return useMutation({
    mutationFn: ({ op, version, changeNote, person }: { op: number; version?: number; changeNote: string; person: Record<string, unknown> }) =>
      api.createMedicalPlanNewVersion(incidentId, op, version, { change_note: changeNote, person }),
    onSuccess: invalidate,
  });
}

export function useDuplicateMedicalPlanLastOp(incidentId: string) {
  const invalidate = useInvalidateMedicalPlan(incidentId);
  return useMutation({
    mutationFn: ({ op, version, person }: { op: number; version?: number; person: Record<string, unknown> }) =>
      api.duplicateMedicalPlanLastOp(incidentId, op, version, { person }),
    onSuccess: invalidate,
  });
}

export function useSaveMedicalPlanProcedures(incidentId: string) {
  const invalidate = useInvalidateMedicalPlan(incidentId);
  return useMutation({
    mutationFn: ({ op, version, content }: { op: number; version?: number; content: string }) =>
      api.saveMedicalPlanProcedures(incidentId, op, version, content),
    onSuccess: invalidate,
  });
}

export function useSubmitMedicalPlanForApproval(incidentId: string) {
  const invalidate = useInvalidateMedicalPlan(incidentId);
  return useMutation({
    mutationFn: ({ op, version }: { op: number; version?: number }) => api.submitMedicalPlanForApproval(incidentId, op, version),
    onSuccess: invalidate,
  });
}

export function useAddMedicalPlanRow(incidentId: string) {
  const invalidate = useInvalidateMedicalPlan(incidentId);
  return useMutation({
    mutationFn: ({ table, op, version, body }: { table: MedicalPlanTable; op: number; version?: number; body: Record<string, unknown> }) =>
      api.addMedicalPlanRow(incidentId, table, op, version, body),
    onSuccess: invalidate,
  });
}

export function useUpdateMedicalPlanRow(incidentId: string) {
  const invalidate = useInvalidateMedicalPlan(incidentId);
  return useMutation({
    mutationFn: ({ table, rowId, op, version, body }: { table: MedicalPlanTable; rowId: number; op: number; version?: number; body: Record<string, unknown> }) =>
      api.updateMedicalPlanRow(incidentId, table, rowId, op, version, body),
    onSuccess: invalidate,
  });
}

export function useDeleteMedicalPlanRow(incidentId: string) {
  const invalidate = useInvalidateMedicalPlan(incidentId);
  return useMutation({
    mutationFn: ({ table, rowId, op, version }: { table: MedicalPlanTable; rowId: number; op: number; version?: number }) =>
      api.deleteMedicalPlanRow(incidentId, table, rowId, op, version),
    onSuccess: invalidate,
  });
}

export function useImportMedicalPlanTable(incidentId: string) {
  const invalidate = useInvalidateMedicalPlan(incidentId);
  return useMutation({
    mutationFn: ({ table, op, version }: { table: MedicalPlanTable; op: number; version?: number }) =>
      api.importMedicalPlanTable(incidentId, table, op, version),
    onSuccess: invalidate,
  });
}

export function useAddMedicalAidStation(incidentId: string) {
  const invalidate = useInvalidateMedicalPlan(incidentId);
  return useMutation({
    mutationFn: ({ op, version, body }: { op: number; version?: number; body: Record<string, unknown> }) =>
      api.createMedicalAidStation(incidentId, op, version, body),
    onSuccess: invalidate,
  });
}

export function useUpdateMedicalAidStation(incidentId: string) {
  const invalidate = useInvalidateMedicalPlan(incidentId);
  return useMutation({
    mutationFn: ({ rowId, op, version, body }: { rowId: number; op: number; version?: number; body: Record<string, unknown> }) =>
      api.updateMedicalAidStation(incidentId, rowId, op, version, body),
    onSuccess: invalidate,
  });
}

export function useDeleteMedicalAidStation(incidentId: string) {
  const invalidate = useInvalidateMedicalPlan(incidentId);
  return useMutation({
    mutationFn: ({ rowId, op, version }: { rowId: number; op: number; version?: number }) =>
      api.deleteMedicalAidStation(incidentId, rowId, op, version),
    onSuccess: invalidate,
  });
}

export function useImportMedicalAidStations(incidentId: string) {
  const invalidate = useInvalidateMedicalPlan(incidentId);
  return useMutation({
    mutationFn: ({ op, version }: { op: number; version?: number }) => api.importMedicalAidStations(incidentId, op, version),
    onSuccess: invalidate,
  });
}
