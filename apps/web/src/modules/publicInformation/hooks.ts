import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../../api/endpoints";
import type { PioMessage, PioRecord, PioTimelineEvent } from "../../api/types";

const POLL = 20_000;
export const pioKey = (id: string, collection: string) => ["incident", id, collection];
export function usePioMessages(id: string) {
  return useQuery({ queryKey: pioKey(id, "pio_messages"), queryFn: () => api.listPioMessages(id), refetchInterval: POLL });
}
export function usePioMessage(id: string, messageId: number) {
  return useQuery({ queryKey: [...pioKey(id, "pio_messages"), messageId], queryFn: () => api.getPioMessage(id, messageId), enabled: Number.isInteger(messageId) && messageId > 0, refetchInterval: POLL });
}
export function usePioApprovals(id: string, messageId: number) {
  return useQuery({ queryKey: [...pioKey(id, "pio_messages"), messageId, "approvals"], queryFn: () => api.listPioApprovals(id, messageId), enabled: messageId > 0, refetchInterval: POLL });
}
export function usePioRecords(id: string, collection: string) {
  return useQuery({ queryKey: pioKey(id, collection), queryFn: () => collection === "pio_templates" ? api.listPioTemplates(id) : api.listPioRecords(id, collection), refetchInterval: POLL });
}
export function usePioTimeline(id: string, itemId: number, enabled: boolean) {
  return useQuery({ queryKey: [...pioKey(id, "pio_misinformation_items"), itemId, "timeline"], queryFn: () => api.listPioTimeline(id, itemId), enabled: enabled && itemId > 0, refetchInterval: POLL });
}
export function usePioSummary(id: string) {
  // Summary joins several collections: poll plus invalidate on local writes.
  return useQuery({ queryKey: ["incident", id, "pio_summary"], queryFn: () => api.getPioSummary(id), refetchInterval: POLL });
}
export function usePioWrites(id: string) {
  const client = useQueryClient();
  const invalidate = () => {
    for (const collection of ["pio_messages", "pio_templates", "pio_media_log", "pio_misinformation_items", "pio_talking_points", "pio_distribution_log", "pio_summary"])
      void client.invalidateQueries({ queryKey: pioKey(id, collection) });
  };
  const messageSuccess = (message: PioMessage) => { client.setQueryData([...pioKey(id, "pio_messages"), message.id], message); invalidate(); };
  const save = useMutation({ mutationFn: (body: Record<string, unknown>) => api.savePioMessage(id, body), onSuccess: messageSuccess });
  const transition = useMutation({ mutationFn: (v: { messageId: number; status: string; user: string; comment: string }) => api.setPioMessageStatus(id, v.messageId, v.status, v.user, v.comment), onSuccess: messageSuccess });
  const record = useMutation({ mutationFn: (v: { collection: string; body: Record<string, unknown> }) => v.collection === "pio_templates" ? api.savePioTemplate(id, v.body) : api.savePioRecord(id, v.collection, v.body), onSuccess: (saved: PioRecord, v) => {
    client.setQueryData<PioRecord[]>(pioKey(id, v.collection), old => [...(old ?? []).filter(r => r.id !== saved.id), saved].filter(r => !r.deleted)); invalidate();
  } });
  const response = useMutation({ mutationFn: (v: { mediaId: number; user: string }) => api.createPioResponse(id, v.mediaId, v.user), onSuccess: messageSuccess });
  const timeline = useMutation({ mutationFn: (v: { itemId: number; text: string; user: string }) => api.addPioTimeline(id, v.itemId, v.text, v.user), onSuccess: (event, v) => {
    client.setQueryData<PioTimelineEvent[]>([...pioKey(id, "pio_misinformation_items"), v.itemId, "timeline"], old => [...(old ?? []), event]);
    invalidate();
  } });
  return { save, transition, record, response, timeline };
}
