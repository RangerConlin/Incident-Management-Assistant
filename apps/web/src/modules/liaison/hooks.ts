import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../../api/endpoints";
import type { LiaisonRecord } from "../../api/types";
export const COLLECTIONS: Record<api.LiaisonSection, string> = {
  agencies: "liaison_agencies", requests: "liaison_requests", "reporting-digests": "liaison_reporting_digests", interactions: "liaison_interactions",
};
export function useLiaisonRecords(id: string, section: api.LiaisonSection) {
  return useQuery({ queryKey: ["incident", id, COLLECTIONS[section]], queryFn: () => api.listLiaisonRecords(id, section), refetchInterval: 20_000 });
}
export function useAgencyDetail(id: string, agencyId: number) {
  return useQuery({ queryKey: ["incident", id, "liaison_agencies", agencyId, "detail"], queryFn: () => api.getLiaisonAgencyDetail(id, agencyId), enabled: Number.isInteger(agencyId) && agencyId > 0, refetchInterval: 20_000 });
}
export function useLiaisonResourceLinks(id: string) {
  return useQuery({ queryKey: ["incident", id, "resource_requests"], queryFn: () => api.listLiaisonResourceLinks(id), refetchInterval: 20_000 });
}
export function useLiaisonWrites(id: string) {
  const client = useQueryClient();
  const invalidate = () => {
    for (const collection of Object.values(COLLECTIONS)) void client.invalidateQueries({ queryKey: ["incident", id, collection] });
  };
  const save = useMutation({ mutationFn: (v: { section: api.LiaisonSection; recordId?: number; body: Record<string, unknown> }) => {
    if (!v.recordId) return api.createLiaisonRecord(id, v.section, v.body);
    if (v.section === "interactions") throw new Error("Interaction editing is not supported by the API.");
    return api.updateLiaisonRecord(id, v.section, v.recordId, v.body);
  }, onSuccess: (saved: LiaisonRecord, v) => {
    client.setQueryData<LiaisonRecord[]>(["incident", id, COLLECTIONS[v.section]], old => [...(old ?? []).filter(r => r.int_id !== saved.int_id), saved]); invalidate();
  } });
  const remove = useMutation({ mutationFn: (v: { section: "requests" | "reporting-digests"; recordId: number }) => api.deleteLiaisonRecord(id, v.section, v.recordId), onSuccess: (_, v) => {
    client.setQueryData<LiaisonRecord[]>(["incident", id, COLLECTIONS[v.section]], old => (old ?? []).filter(r => r.int_id !== v.recordId)); invalidate();
  } });
  const narrative = useMutation({ mutationFn: (v: { requestId: number; text: string; category: string; author: string }) => api.addLiaisonNarrative(id, v.requestId, { text: v.text, category: v.category, author: v.author }), onSuccess: saved => {
    client.setQueryData<LiaisonRecord[]>(["incident", id, "liaison_requests"], old => [...(old ?? []).filter(r => r.int_id !== saved.int_id), saved]); invalidate();
  } });
  const contact = useMutation({ mutationFn: (v: { agencyId: number; body: Record<string, unknown> }) => api.createLiaisonContact(id, v.agencyId, v.body), onSuccess: invalidate });
  return { save, remove, narrative, contact };
}
