import { api } from "./api";

export interface CandidatePool {
  participant_id: string;
  pseudonym: string;
  pool: number;
  stakes: number;
}

export interface MyStake {
  stake_id: string;
  candidate_participant_id: string;
  candidate_pseudonym: string;
  amount: number;
  status: string;
  payout: number;
}

export interface BetRound {
  round_id: string;
  title: string;
  prompt: string;
  status: "scheduled" | "open" | "locked" | "settled" | "void";
  opens_at: string;
  closes_at: string;
  measurement_end: string;
  min_stake: number;
  max_stake: number;
  total_pool: number;
  pools: CandidatePool[];
  my_stake: MyStake | null;
  winners: { participant_id: string; pseudonym: string }[] | null;
  void_reason: string | null;
}

export interface PastRound {
  round_id: string;
  title: string;
  status: string;
  total_pool: number;
  settled_at: string | null;
  winners: string[] | null;
  void_reason: string | null;
}

export const bets = {
  current: () => api.get<{ round: BetRound | null }>("/api/v1/bets/rounds/current"),
  history: () => api.get<{ items: PastRound[] }>("/api/v1/bets/rounds").then((r) => r.items),
  stake: (roundId: string, candidateId: string, amount: number) =>
    api.post<{ stake_id: string }>(`/api/v1/bets/rounds/${roundId}/stakes`, {
      candidate_participant_id: candidateId,
      amount,
    }),
  cancel: (stakeId: string) => api.del(`/api/v1/bets/stakes/${stakeId}`),
};
