import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { listWorkspaceRecords, saveWorkspaceRecord, deleteWorkspaceRecord } from "../../api/endpoints";
import type { Dataset, RecordData } from "./config";

export function datasetKey(dataset: Dataset, incidentId: string) {
  return dataset.master ? ["master", dataset.collection] : ["incident", incidentId, dataset.collection];
}
export function useDataset(dataset: Dataset, incidentId: string) {
  return useQuery({ queryKey: [...datasetKey(dataset, incidentId), dataset.endpoint], queryFn: () => listWorkspaceRecords(dataset, incidentId), refetchInterval: 20_000 });
}
export function useRecordActions(dataset: Dataset, incidentId: string) {
  const client = useQueryClient();
  const invalidate = () => client.invalidateQueries({ queryKey: datasetKey(dataset, incidentId) });
  const save = useMutation({ mutationFn: ({ id, body }: { id: string | null; body: RecordData }) => saveWorkspaceRecord(dataset, incidentId, id, body), onSuccess: invalidate });
  const remove = useMutation({ mutationFn: (id: string) => deleteWorkspaceRecord(dataset, incidentId, id), onSuccess: invalidate });
  return { save, remove };
}
