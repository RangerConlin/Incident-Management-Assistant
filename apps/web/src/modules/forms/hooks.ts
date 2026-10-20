import { useMutation, useQuery } from "@tanstack/react-query";
import * as api from "../../api/endpoints";
import type { FormExportRequest } from "../../api/types";
export function useFormExportCatalog(id: string) { return useQuery({ queryKey: ["incident",id,"form_export_catalog"],queryFn: () => api.listFormExports(id),refetchInterval: 20_000 }); }
export function useDownloadForm(id: string) { return useMutation({ mutationFn: (body: FormExportRequest) => api.downloadFormExport(id,body) }); }
export function useExportSources(id: string, source: string) {
  const collection = ({ work_assignment: "work_assignments",resource_request: "resource_requests",sitrep: "sitreps" } as Record<string,string>)[source] ?? "form_export_sources";
  return useQuery({ queryKey: ["incident",id,collection,"export-sources"],enabled: ["work_assignment","resource_request","sitrep"].includes(source),refetchInterval: 20_000,
    queryFn: async (): Promise<{ id: string; label: string }[]> => {
      if (source === "work_assignment") return (await api.listWorkAssignments(id)).map(r => ({ id: String(r.id),label: `${r.assignment_number} - ${r.assignment_name}` }));
      if (source === "resource_request") return (await api.listResourceRequests(id)).map(r => ({ id: r.id,label: r.title }));
      if (source === "sitrep") return (await api.listSitreps(id)).map(r => ({ id: r.id,label: `SITREP ${r.sitrep_number} - ${r.status}` }));
      return [];
    },
  });
}
