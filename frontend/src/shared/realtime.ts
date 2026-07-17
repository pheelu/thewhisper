import { useEffect, useRef } from "react";
import { WS_BASE } from "./api";

export interface WhisperMessage {
  type: string;
  payload: Record<string, unknown>;
  event_id: string;
  message_id: string;
  ts: string;
}

/** Apre un WebSocket alla serata e invoca `onMessage` per ogni busta ricevuta. */
export function useWhisperSocket(onMessage: (msg: WhisperMessage) => void): void {
  const handler = useRef(onMessage);
  handler.current = onMessage;

  useEffect(() => {
    const ws = new WebSocket(`${WS_BASE}/api/v1/ws`);
    ws.onmessage = (evt) => {
      try {
        handler.current(JSON.parse(evt.data) as WhisperMessage);
      } catch {
        /* frame non-JSON: ignora */
      }
    };
    const ping = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "ping", payload: {} }));
    }, 25000);
    return () => {
      clearInterval(ping);
      ws.close();
    };
  }, []);
}
