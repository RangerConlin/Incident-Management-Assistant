import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../../../api/endpoints";

const POLL_FLOOR_MS = 20_000;
const COLLECTION = "intel_leads";

export function useLeadRows(incidentId: string) {
  return useQuery({
    queryKey: ["incident", incidentId, COLLECTION],
    queryFn: () => api.listIntelLeads(incidentId),
    refetchInterval: POLL_FLOOR_MS,
  });
}

export function useLeadDetail(incidentId: string, leadId: string) {
  return useQuery({
    queryKey: ["incident", incidentId, COLLECTION, leadId],
    queryFn: () => api.getIntelLead(incidentId, leadId),
    refetchInterval: POLL_FLOOR_MS,
  });
}

function useInvalidateLeads(incidentId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["incident", incidentId, COLLECTION] });
}

export function useCreateLead(incidentId: string) {
  const invalidate = useInvalidateLeads(incidentId);
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.createIntelLead(incidentId, body),
    onSuccess: invalidate,
  });
}

export function useUpdateLead(incidentId: string) {
  const invalidate = useInvalidateLeads(incidentId);
  return useMutation({
    mutationFn: ({ leadId, body }: { leadId: string; body: Record<string, unknown> }) =>
      api.updateIntelLead(incidentId, leadId, body),
    onSuccess: invalidate,
  });
}

export function useAssignLead(incidentId: string) {
  const invalidate = useInvalidateLeads(incidentId);
  return useMutation({
    mutationFn: ({ leadId, name }: { leadId: string; name: string }) =>
      api.updateIntelLead(incidentId, leadId, { assigned_to: name || null, status: name ? "Assigned" : undefined }),
    onSuccess: invalidate,
  });
}

export function useCloseLead(incidentId: string) {
  const invalidate = useInvalidateLeads(incidentId);
  return useMutation({
    mutationFn: (leadId: string) => api.closeIntelLead(incidentId, leadId),
    onSuccess: invalidate,
  });
}

// The client creates the target Intel Item, then marks the lead Converted —
// matches desktop's IntelWindow._on_convert_lead (the server's /convert
// endpoint only flips status + stores the link, it never creates anything).
export function useConvertLead(incidentId: string) {
  const invalidate = useInvalidateLeads(incidentId);
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ lead, actor }: { lead: import("../../../api/types").IntelLead; actor?: string }) => {
      const validPriorities = new Set(["Critical", "High", "Medium", "Low"]);
      const item = await api.createIntelItem(incidentId, {
        item_type: "Other",
        title: lead.title,
        priority: validPriorities.has(lead.priority) ? lead.priority : "Medium",
        notes: [lead.summary, lead.notes].filter(Boolean).join("\n\n") || undefined,
        location_text: lead.location_text,
        source_lead_id: lead.id,
        linked_subject_ids: lead.source_subject_id ? [lead.source_subject_id] : [],
        created_by: actor,
      });
      await api.convertIntelLead(incidentId, lead.id, { target_type: "item", target_id: item.id, actor });
      return item;
    },
    onSuccess: () => {
      invalidate();
      queryClient.invalidateQueries({ queryKey: ["incident", incidentId, "intel_items"] });
    },
  });
}
