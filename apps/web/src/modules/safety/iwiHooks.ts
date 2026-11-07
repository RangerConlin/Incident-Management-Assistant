import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../../api/endpoints";

const POLL_FLOOR_MS = 20_000;
const COLLECTION = "iwi_reports";

export function useIwiReports(incidentId: string, filters: { severity?: string; status?: string } = {}) {
  return useQuery({
    queryKey: ["incident", incidentId, COLLECTION, filters],
    queryFn: () => api.listIwiReports(incidentId, filters),
    refetchInterval: POLL_FLOOR_MS,
  });
}

export function useIwiReport(incidentId: string, reportId: string) {
  return useQuery({
    queryKey: ["incident", incidentId, COLLECTION, reportId],
    queryFn: () => api.getIwiReport(incidentId, reportId),
    enabled: Boolean(reportId),
    refetchInterval: POLL_FLOOR_MS,
  });
}

function useInvalidateIwi(incidentId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["incident", incidentId, COLLECTION] });
}

export function useCreateIwiReport(incidentId: string) {
  const invalidate = useInvalidateIwi(incidentId);
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.createIwiReport(incidentId, body),
    onSuccess: invalidate,
  });
}

export function useUpdateIwiReport(incidentId: string) {
  const invalidate = useInvalidateIwi(incidentId);
  return useMutation({
    mutationFn: ({ reportId, body }: { reportId: string; body: Record<string, unknown> }) => api.updateIwiReport(incidentId, reportId, body),
    onSuccess: invalidate,
  });
}

export function useSignoffIwiReport(incidentId: string) {
  const invalidate = useInvalidateIwi(incidentId);
  return useMutation({
    mutationFn: ({ reportId, role, name }: { reportId: string; role: string; name: string }) => api.signoffIwiReport(incidentId, reportId, role, name),
    onSuccess: invalidate,
  });
}

export function useDeleteIwiReport(incidentId: string) {
  const invalidate = useInvalidateIwi(incidentId);
  return useMutation({
    mutationFn: (reportId: string) => api.deleteIwiReport(incidentId, reportId),
    onSuccess: invalidate,
  });
}
