import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../../api/endpoints";

const POLL_FLOOR_MS = 20_000;

export function useSpatialFeatures(incidentId: string) {
  return useQuery({
    queryKey: ["incident", incidentId, "spatial_features"],
    queryFn: () => api.listSpatialFeatures(incidentId),
    refetchInterval: POLL_FLOOR_MS,
  });
}

export function useArchiveSpatialFeature(incidentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (featureId: number) => api.archiveSpatialFeature(incidentId, featureId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["incident", incidentId, "spatial_features"] }),
  });
}
