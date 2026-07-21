import { useEffect, useRef } from "react";
import { WS_BASE } from "./api";

export interface WhisperMessage {
  type: string;
  payload: Record<string, unknown>;
  event_id: string;
  message_id: string;
  ts: string;
}

interface SocketOptions {
  /** Invocata a ogni (ri)connessione riuscita: usala per risincronizzare lo stato via REST. */
  onConnect?: () => void;
}

/**
 * WebSocket della serata con RICONNESSIONE automatica.
 *
 * I telefoni chiudono il socket quando lo schermo si spegne o si cambia app:
 * qui riconnettiamo con backoff esponenziale (1s→15s) e, al ritorno in
 * foreground (`visibilitychange`), immediatamente. Dopo ogni riconnessione il
 * chiamante risincronizza via REST con `onConnect` (il WS non fa replay).
 */
export function useWhisperSocket(
  onMessage: (msg: WhisperMessage) => void,
  options: SocketOptions = {},
): void {
  const handler = useRef(onMessage);
  handler.current = onMessage;
  const onConnectRef = useRef(options.onConnect);
  onConnectRef.current = options.onConnect;

  useEffect(() => {
    let ws: WebSocket | null = null;
    let alive = true;
    let attempt = 0;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      if (!alive) return;
      ws = new WebSocket(`${WS_BASE}/api/v1/ws`);

      ws.onopen = () => {
        attempt = 0;
        onConnectRef.current?.();
      };
      ws.onmessage = (evt) => {
        try {
          handler.current(JSON.parse(evt.data) as WhisperMessage);
        } catch {
          /* frame non-JSON: ignora */
        }
      };
      ws.onclose = () => {
        if (!alive) return;
        const delay = Math.min(15000, 1000 * 2 ** attempt) + Math.random() * 500;
        attempt += 1;
        retryTimer = setTimeout(connect, delay);
      };
      ws.onerror = () => {
        ws?.close();
      };
    };

    const onVisible = () => {
      if (document.visibilityState !== "visible" || !alive) return;
      // al risveglio: se il socket è morto riconnetti subito, altrimenti risincronizza
      if (!ws || ws.readyState === WebSocket.CLOSED || ws.readyState === WebSocket.CLOSING) {
        if (retryTimer) clearTimeout(retryTimer);
        attempt = 0;
        connect();
      } else {
        onConnectRef.current?.();
      }
    };

    const ping = setInterval(() => {
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "ping", payload: {} }));
      }
    }, 25000);

    document.addEventListener("visibilitychange", onVisible);
    connect();

    return () => {
      alive = false;
      clearInterval(ping);
      if (retryTimer) clearTimeout(retryTimer);
      document.removeEventListener("visibilitychange", onVisible);
      ws?.close();
    };
  }, []);
}
