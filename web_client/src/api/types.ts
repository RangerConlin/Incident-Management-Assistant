export interface PublicUser {
  user_id: string;
  username: string;
  display_name: string;
  person_record: number | null;
}

export interface PersonnelSummary {
  person_record: number | null;
  person_id: string;
  first_name?: string;
  last_name?: string;
  name: string;
  primary_role?: string | null;
}

export interface LoginResponse {
  token: string;
  session_id: string;
  user_id: string;
  person_record: number | null;
  user: PublicUser;
  personnel: PersonnelSummary | null;
}

export interface Incident {
  id: string;
  incident_id?: string;
  number: string;
  name: string;
  status?: string;
  type?: string;
}

export interface CheckinRecord {
  person_record: number;
  status: string;
  checked_in: boolean;
  checkin_status: string;
  location?: string | null;
  notes?: string | null;
  team_id?: string | null;
  role_on_team?: string | null;
  arrival_time?: string | null;
}

export interface TeamOption {
  team_id: string;
  team_name: string;
}

export interface RosterRow {
  person_record: number;
  person_id: string;
  name: string;
  role: string | null;
  team: string;
  team_id: string | null;
  status: string;
  checked_in: boolean;
}

export interface ChatChannel {
  id: string;
  type: "group" | "dm";
  name: string | null;
  participant_ids: string[];
  created_by: string;
  created_at?: string;
}

export interface ChatMessage {
  id: string;
  channel_id: string;
  sender_id: string;
  sender_name?: string | null;
  text: string;
  created_at?: string;
}
