import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../../api/endpoints";
import type { ResourceRequestDetail, Facility } from "../../api/types";
export function useResourceRequests(id: string) { return useQuery({ queryKey: ["incident", id, "resource_requests"], queryFn: () => api.listResourceRequests(id), refetchInterval: 20_000 }); }
export function useResourceRequest(id: string, requestId: string) { return useQuery({ queryKey: ["incident", id, "resource_requests", requestId], queryFn: () => api.getResourceRequest(id, requestId), enabled: Boolean(requestId) && requestId !== "new", refetchInterval: 20_000 }); }
export function useFacilities(id: string) { return useQuery({ queryKey: ["incident", id, "facilities"], queryFn: () => api.listFacilities(id), refetchInterval: 20_000 }); }
export function useFacility(id: string, facilityId: string) { return useQuery({ queryKey: ["incident", id, "facilities", facilityId], queryFn: () => api.getFacility(id, facilityId), enabled: Boolean(facilityId) && facilityId !== "new", refetchInterval: 20_000 }); }
export function useRequestWrites(id: string, requestId: string) {
  const client = useQueryClient();
  const invalidate = () => client.invalidateQueries({ queryKey: ["incident", id, "resource_requests"] });
  const success = (data: ResourceRequestDetail) => { client.setQueryData(["incident", id, "resource_requests", data.id], data); return invalidate(); };
  const save = useMutation({ mutationFn: (body: Record<string, unknown>) => requestId === "new" ? api.createResourceRequest(id, body) : api.updateResourceRequest(id, requestId, body), onSuccess: success });
  const approval = useMutation({ mutationFn: (v: { action: string; actor: string; note: string }) => api.resourceRequestApproval(id, requestId, v.action, v.actor, v.note), onSuccess: invalidate });
  const status = useMutation({ mutationFn: (v: { status: string; actor: string; note: string }) => api.resourceRequestStatus(id, requestId, v.status, v.actor, v.note), onSuccess: success });
  const items = useMutation({ mutationFn: (body: apiParametersItems) => api.replaceResourceRequestItems(id, requestId, body), onSuccess: invalidate });
  const fulfillment = useMutation({ mutationFn: async (v: { fulfillmentId?: string; body: Record<string, unknown> }): Promise<unknown> => v.fulfillmentId ? api.updateResourceRequestFulfillment(id, requestId, v.fulfillmentId, v.body) : api.assignResourceRequestFulfillment(id, requestId, v.body), onSuccess: invalidate });
  return { save, approval, status, items, fulfillment };
}
type apiParametersItems = Parameters<typeof api.replaceResourceRequestItems>[2];
export function useFacilityWrites(id: string, facilityId: string) {
  const client = useQueryClient(); const invalidate = () => client.invalidateQueries({ queryKey: ["incident", id, "facilities"] });
  const save = useMutation({ mutationFn: (body: Record<string, unknown>) => facilityId === "new" ? api.createFacility(id, body) : api.updateFacility(id, facilityId, body), onSuccess: (data: Facility) => { client.setQueryData(["incident", id, "facilities", data.id], data); return invalidate(); } });
  const remove = useMutation({ mutationFn: () => api.deleteFacility(id, facilityId), onSuccess: invalidate });
  return { save, remove };
}

export function useFacilityPersonnel(id: string, search: string) { return useQuery({ queryKey: ["incident", id, "master_personnel", "facility-manager", search], queryFn: () => api.searchCheckinPersonnel(id,search), enabled: Boolean(search.trim()), refetchInterval: 20_000 }); }
