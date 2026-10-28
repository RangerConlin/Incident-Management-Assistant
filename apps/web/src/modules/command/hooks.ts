import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../../api/endpoints";

const invalidate = (client: ReturnType<typeof useQueryClient>, id: string, collection: string) => () => client.invalidateQueries({ queryKey: ["incident", id, collection] });
export const useIncidentProfile = (id: string) => useQuery({ queryKey: ["incident", id, "profile"], queryFn: () => api.getIncidentProfile(id), refetchInterval: 20_000 });
export function useProfileSave(id: string) { const c = useQueryClient(); return useMutation({ mutationFn: (body: Record<string, unknown>) => api.updateIncidentProfile(id, body), onSuccess: invalidate(c,id,"profile") }); }
export const useOrg = (id: string) => useQuery({ queryKey: ["incident",id,"incident_org"], queryFn: () => Promise.all([api.listOrgPositions(id),api.listOrgAssignments(id),api.listOrgTemplates(id)]).then(([positions,assignments,templates]) => ({ positions,assignments,templates })), refetchInterval: 20_000 });
export function useOrgWrites(id: string) { const c=useQueryClient(); const done=invalidate(c,id,"incident_org"); return {
  position: useMutation({ mutationFn: (body: Record<string,unknown>) => api.saveOrgPosition(id,body), onSuccess: done }),
  remove: useMutation({ mutationFn: (positionId: number) => api.deleteOrgPosition(id,positionId), onSuccess: done }),
  move: useMutation({ mutationFn: (v: { positionId: number; parentPositionId: number|null }) => api.moveOrgPosition(id,v.positionId,v.parentPositionId), onSuccess: done }),
  apply: useMutation({ mutationFn: (payload: Record<string,unknown>[]) => api.applyOrgTemplate(id,payload), onSuccess: done }),
  assign: useMutation({ mutationFn: (body: Record<string,unknown>) => api.addOrgAssignment(id,body), onSuccess: done }),
  end: useMutation({ mutationFn: (assignmentId: string) => api.endOrgAssignment(id,assignmentId), onSuccess: done }),
}; }
export const useIapPackages = (id: string) => useQuery({ queryKey: ["incident",id,"iap_packages"], queryFn: () => api.listIapPackages(id), refetchInterval: 20_000 });
export const useIapPackage = (id: string, op: number) => useQuery({ queryKey: ["incident",id,"iap_packages",op], queryFn: () => api.getIapPackage(id,op), refetchInterval: 20_000 });
export function useIapWrites(id: string, op: number) { const c=useQueryClient(); const done=invalidate(c,id,"iap_packages"); return {
  save: useMutation({ mutationFn: (body: Record<string,unknown>) => api.saveIapPackage(id,op,body), onSuccess: done }),
  form: useMutation({ mutationFn: (v: { formId:string; body:Record<string,unknown> }) => api.saveIapForm(id,op,v.formId,v.body), onSuccess: done }),
  removeForm: useMutation({ mutationFn: (formId:string) => api.deleteIapForm(id,op,formId), onSuccess: done }),
  order: useMutation({ mutationFn: (order:string[]) => api.orderIapForms(id,op,order), onSuccess: done }),
}; }
