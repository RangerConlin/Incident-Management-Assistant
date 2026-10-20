import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../../../api/endpoints";

const POLL_FLOOR_MS = 20_000;

export function useResourceStatusRows(incidentId: string, resourceType = "") {
  return useQuery({
    queryKey: ["incident", incidentId, "resource_status", resourceType],
    queryFn: () => api.listResourceStatus(incidentId, resourceType),
    refetchInterval: POLL_FLOOR_MS,
  });
}

export function useResourceStatusDetail(incidentId: string, resourceType: string, recordId: string) {
  return useQuery({
    queryKey: ["incident", incidentId, "resource_status", "detail", resourceType, recordId],
    queryFn: () => api.getResourceStatus(incidentId, resourceType, recordId),
    enabled: Boolean(resourceType && recordId),
    refetchInterval: POLL_FLOOR_MS,
  });
}

function useInvalidateResourceStatus(incidentId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["incident", incidentId, "resource_status"] });
}

export function useCheckInResource(incidentId: string) {
  const invalidate = useInvalidateResourceStatus(incidentId);
  return useMutation({
    mutationFn: ({
      resourceType,
      recordId,
      overrides,
    }: {
      resourceType: string;
      recordId: string | number;
      overrides?: Record<string, unknown>;
    }) => api.checkInResource(incidentId, resourceType, recordId, overrides),
    onSuccess: invalidate,
  });
}

export function useCheckOutResource(incidentId: string) {
  const invalidate = useInvalidateResourceStatus(incidentId);
  return useMutation({
    mutationFn: ({ resourceType, recordId }: { resourceType: string; recordId: string | number }) =>
      api.checkOutResource(incidentId, resourceType, recordId),
    onSuccess: invalidate,
  });
}

export const RESOURCE_STATUS_OPTIONS: { key: string; label: string }[] = [
  { key: "Pending", label: "Pending" },
  { key: "Enroute", label: "Enroute" },
  { key: "Checked In", label: "Checked In" },
  { key: "Assigned", label: "Assigned" },
  { key: "Available", label: "Available" },
  { key: "Out of Service", label: "Out of Service" },
  { key: "Preparing for Demobilization", label: "Preparing for Demobilization" },
];

export const RESOURCE_TYPE_OPTIONS: { key: string; label: string }[] = [
  { key: "personnel", label: "Personnel" },
  { key: "vehicle", label: "Vehicle" },
  { key: "aircraft", label: "Aircraft" },
  { key: "equipment", label: "Equipment" },
];
