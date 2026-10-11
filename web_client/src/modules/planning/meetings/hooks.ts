import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../../../api/endpoints";

const POLL_FLOOR_MS = 20_000;
const COLLECTION = "meetings";

export function useMeetings(incidentId: string) {
  return useQuery({
    queryKey: ["incident", incidentId, COLLECTION],
    queryFn: () => api.listMeetings(incidentId),
    refetchInterval: POLL_FLOOR_MS,
  });
}

export function useMeetingDetail(incidentId: string, meetingId: number) {
  return useQuery({
    queryKey: ["incident", incidentId, COLLECTION, meetingId],
    queryFn: () => api.getMeeting(incidentId, meetingId),
    refetchInterval: POLL_FLOOR_MS,
  });
}

export function useMeetingTemplates() {
  return useQuery({
    queryKey: ["meeting-templates"],
    queryFn: () => api.listMeetingTemplates(),
    staleTime: 5 * 60_000,
  });
}

function useInvalidateMeetings(incidentId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["incident", incidentId, COLLECTION] });
}

export function useCreateMeeting(incidentId: string) {
  const invalidate = useInvalidateMeetings(incidentId);
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.createMeeting(incidentId, body),
    onSuccess: invalidate,
  });
}

export function useUpdateMeeting(incidentId: string) {
  const invalidate = useInvalidateMeetings(incidentId);
  return useMutation({
    mutationFn: ({ meetingId, body }: { meetingId: number; body: Record<string, unknown> }) =>
      api.updateMeeting(incidentId, meetingId, body),
    onSuccess: invalidate,
  });
}

export function useDeleteMeeting(incidentId: string) {
  const invalidate = useInvalidateMeetings(incidentId);
  return useMutation({
    mutationFn: (meetingId: number) => api.deleteMeeting(incidentId, meetingId),
    onSuccess: invalidate,
  });
}

export function useAddMeetingAttendee(incidentId: string, meetingId: number) {
  const invalidate = useInvalidateMeetings(incidentId);
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.addMeetingAttendee(incidentId, meetingId, body),
    onSuccess: invalidate,
  });
}

export function useUpdateMeetingAttendee(incidentId: string, meetingId: number) {
  const invalidate = useInvalidateMeetings(incidentId);
  return useMutation({
    mutationFn: ({ attendeeId, body }: { attendeeId: number; body: Record<string, unknown> }) =>
      api.updateMeetingAttendee(incidentId, meetingId, attendeeId, body),
    onSuccess: invalidate,
  });
}

export function useRemoveMeetingAttendee(incidentId: string, meetingId: number) {
  const invalidate = useInvalidateMeetings(incidentId);
  return useMutation({
    mutationFn: (attendeeId: number) => api.removeMeetingAttendee(incidentId, meetingId, attendeeId),
    onSuccess: invalidate,
  });
}

export function useAddMeetingChecklistItem(incidentId: string, meetingId: number) {
  const invalidate = useInvalidateMeetings(incidentId);
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.addMeetingChecklistItem(incidentId, meetingId, body),
    onSuccess: invalidate,
  });
}

export function useUpdateMeetingChecklistItem(incidentId: string, meetingId: number) {
  const invalidate = useInvalidateMeetings(incidentId);
  return useMutation({
    mutationFn: ({ itemId, body }: { itemId: number; body: Record<string, unknown> }) =>
      api.updateMeetingChecklistItem(incidentId, meetingId, itemId, body),
    onSuccess: invalidate,
  });
}

export function useAddMeetingNote(incidentId: string, meetingId: number) {
  const invalidate = useInvalidateMeetings(incidentId);
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.addMeetingNote(incidentId, meetingId, body),
    onSuccess: invalidate,
  });
}
