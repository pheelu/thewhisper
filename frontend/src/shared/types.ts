export const NOBLE_TITLES = [
  "duca",
  "duchessa",
  "conte",
  "contessa",
  "barone",
  "baronessa",
  "visconte",
  "viscontessa",
  "marchese",
  "marchesa",
] as const;

export type NobleTitle = (typeof NOBLE_TITLES)[number];

export interface Participant {
  id: string;
  pseudonym: string;
  noble_title: NobleTitle | null;
  role: "guest" | "host";
  score: number;
  is_photographable: boolean;
}

export interface EventInfo {
  id: string;
  name: string;
  venue_name: string | null;
  status: "draft" | "open" | "closed" | "archived";
  starts_at: string;
  ends_at: string;
  timezone: string;
  join_code?: string;
}

export interface Me {
  participant: Participant;
  event: EventInfo;
}

export interface LeaderboardEntry {
  rank: number;
  participant_id: string;
  pseudonym: string;
  noble_title: NobleTitle | null;
  score: number;
}
