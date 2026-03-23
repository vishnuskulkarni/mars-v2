import { useEffect, useRef, useCallback } from 'react';

export function useSSE(sessionId, onEvent) {
  const eventSourceRef = useRef(null);

  const connect = useCallback(() => {
    if (!sessionId) return;

    // Close existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const es = new EventSource(`/api/status/${sessionId}`);
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onEvent(data);
      } catch {
        // Ignore parse errors (e.g. keepalive pings)
      }
    };

    es.onerror = () => {
      es.close();
      // Auto-reconnect after 2 seconds
      setTimeout(() => connect(), 2000);
    };
  }, [sessionId, onEvent]);

  useEffect(() => {
    connect();
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, [connect]);
}
