"use client";

import { useSSE } from "@/hooks/useSSE";

export function SSEConnector() {
  useSSE();
  return null;
}
