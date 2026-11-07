import { useQuery } from "@tanstack/react-query";
import * as api from "../../api/endpoints";

const POLL_FLOOR_MS = 20_000;

export function useIntelDashboard(incidentId: string) {
  return useQuery({
    queryKey: ["incident", incidentId, "intel_dashboard"],
    queryFn: () => api.getIntelDashboard(incidentId),
    refetchInterval: POLL_FLOOR_MS,
  });
}

export function useIntelLog(
  incidentId: string,
  params: { entity_type?: string; entity_id?: string; event_type?: string; limit?: number } = {},
) {
  return useQuery({
    queryKey: ["incident", incidentId, "intel_log", params],
    queryFn: () => api.getIntelLog(incidentId, params),
    refetchInterval: POLL_FLOOR_MS,
  });
}
