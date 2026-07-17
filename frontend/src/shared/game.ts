import { api } from "./api";
import type { NobleTitle } from "./types";

export interface SubjectRef {
  participant_id: string;
  pseudonym: string;
  noble_title: NobleTitle | null;
}

export interface Photo {
  photo_id: string;
  mysterious_title: string;
  image_url: string | null;
  published_at: string | null;
  comment_count: number;
  correct_guess_count: number;
  subject_revealed: boolean;
  subject: SubjectRef | null;
}

export interface Comment {
  comment_id: string;
  author_participant_id: string | null;
  author_pseudonym: string | null;
  author_noble_title: NobleTitle | null;
  body: string;
  created_at: string;
}

export interface GuessResult {
  is_correct: boolean;
  guess_rank: number | null;
  points_awarded: number;
  attempts_left: number;
}

export interface RosterEntry {
  participant_id: string;
  pseudonym: string;
  noble_title: NobleTitle | null;
  score: number;
  is_photographable: boolean;
  motto: string | null;
  avatar_seed: string;
  accent_color: string | null;
  reveal_stage: string;
}

export interface MyProfile {
  participant_id: string;
  secret_text: string | null;
  motto: string | null;
  avatar_seed: string;
  accent_color: string | null;
  reveal_stage: string;
  is_complete: boolean;
}

export interface DiscoveryState {
  total_guess_count: number;
  correct_guess_count: number;
  solved_at: string | null;
  reveal_state: string;
}

export const game = {
  feed: () => api.get<{ items: Photo[] }>("/api/v1/photos").then((r) => r.items),
  photo: (id: string) => api.get<Photo>(`/api/v1/photos/${id}`),
  mine: () => api.get<{ items: Photo[] }>("/api/v1/photos/mine").then((r) => r.items),
  ofMe: () => api.get<{ items: Photo[] }>("/api/v1/photos/of-me").then((r) => r.items),

  createDraft: (subjectId: string, title: string, contentType: string) =>
    api.post<{ photo_id: string; upload_url: string; content_type: string }>("/api/v1/photos", {
      subject_participant_id: subjectId,
      mysterious_title: title,
      content_type: contentType,
    }),
  upload: async (url: string, file: File) => {
    const res = await fetch(url, {
      method: "PUT",
      body: file,
      headers: { "Content-Type": file.type },
    });
    if (!res.ok) throw new Error(`Upload fallito (${res.status})`);
  },
  publish: (id: string) => api.post<Photo>(`/api/v1/photos/${id}/publish`),
  reveal: (id: string) => api.post<Photo>(`/api/v1/photos/${id}/reveal`),

  comments: (id: string) =>
    api.get<{ items: Comment[] }>(`/api/v1/photos/${id}/comments`).then((r) => r.items),
  addComment: (id: string, body: string) =>
    api.post<{ comment_id: string }>(`/api/v1/photos/${id}/comments`, { body }),

  guess: (id: string, candidateId: string) =>
    api.post<GuessResult>(`/api/v1/photos/${id}/guesses`, {
      guessed_subject_participant_id: candidateId,
    }),
  myGuesses: (id: string) =>
    api
      .get<{ items: { guessed_subject_participant_id: string; is_correct: boolean }[] }>(
        `/api/v1/photos/${id}/guesses/me`,
      )
      .then((r) => r.items),
  discovery: (id: string) => api.get<DiscoveryState>(`/api/v1/photos/${id}/discovery`),

  roster: () => api.get<{ items: RosterEntry[] }>("/api/v1/profiles").then((r) => r.items),
  myProfile: () => api.get<MyProfile>("/api/v1/profiles/me"),
  updateProfile: (body: Partial<Pick<MyProfile, "secret_text" | "motto" | "accent_color">>) =>
    api.put<MyProfile>("/api/v1/profiles/me", body),
};
