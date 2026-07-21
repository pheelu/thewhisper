import { api } from "./api";

export interface CounterpartView {
  display_name: string;
  noble_title: string | null;
  is_masked: boolean;
}

export interface ConversationSummary {
  conversation_id: string;
  i_am_initiator: boolean;
  counterpart: CounterpartView;
  initiator_revealed: boolean;
  my_contact_consent: boolean;
  their_contact_consent: boolean;
  contact_exchanged: boolean;
  last_message_at: string | null;
  last_body: string | null;
  unread_count: number;
  status: string;
}

export interface ChatMessage {
  message_id: string;
  mine: boolean;
  kind: "text" | "system";
  sender_display: string | null;
  body: string;
  created_at: string;
}

export interface ExchangedContact {
  participant_id: string;
  contact_type: string;
  contact_value: string;
  mine: boolean;
}

export interface ConversationDetail {
  conversation_id: string;
  i_am_initiator: boolean;
  my_alias: string | null;
  i_am_revealed: boolean;
  counterpart_display: string;
  counterpart_masked: boolean;
  initiator_revealed: boolean;
  my_contact_consent: boolean;
  their_contact_consent: boolean;
  contact_exchanged: boolean;
  contacts: ExchangedContact[] | null;
  status: string;
  messages: ChatMessage[];
}

export const dialogue = {
  sendMissive: (recipientId: string, body: string) =>
    api.post<{ conversation_id: string; your_alias: string }>("/api/v1/missives", {
      recipient_participant_id: recipientId,
      body,
    }),
  conversations: () =>
    api.get<{ items: ConversationSummary[] }>("/api/v1/conversations").then((r) => r.items),
  conversation: (id: string) => api.get<ConversationDetail>(`/api/v1/conversations/${id}`),
  sendMessage: (id: string, body: string) =>
    api.post<{ message_id: string }>(`/api/v1/conversations/${id}/messages`, { body }),
  markRead: (id: string) => api.post(`/api/v1/conversations/${id}/read`),
  reveal: (id: string) => api.post<{ revealed: boolean }>(`/api/v1/conversations/${id}/reveal`),
  setContact: (id: string, value: string) =>
    api.post<{ contact_exchanged: boolean }>(`/api/v1/conversations/${id}/contact`, {
      contact_type: "instagram",
      contact_value: value,
    }),
};
