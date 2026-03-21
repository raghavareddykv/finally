"use client";

import { useEffect, useRef } from "react";
import { useMarket } from "@/lib/market-context";
import type { PriceUpdate } from "@/lib/types";

export function useSSE() {
  const { handlePriceUpdate, setConnectionStatus } = useMarket();
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    function connect() {
      setConnectionStatus("reconnecting");

      const es = new EventSource("/api/stream/prices");
      eventSourceRef.current = es;

      es.onopen = () => {
        setConnectionStatus("connected");
      };

      es.addEventListener("price_update", (event) => {
        try {
          const data: PriceUpdate = JSON.parse((event as MessageEvent).data);
          handlePriceUpdate(data);
        } catch {
          // ignore malformed messages
        }
      });

      es.onerror = () => {
        setConnectionStatus("reconnecting");
        // EventSource auto-reconnects, but if it closes we reconnect manually
        if (es.readyState === EventSource.CLOSED) {
          setConnectionStatus("disconnected");
          es.close();
          // Retry after 3 seconds
          setTimeout(connect, 3000);
        }
      };
    }

    connect();

    return () => {
      eventSourceRef.current?.close();
      eventSourceRef.current = null;
    };
  }, [handlePriceUpdate, setConnectionStatus]);
}
