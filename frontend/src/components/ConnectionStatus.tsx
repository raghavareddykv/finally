"use client";

type Status = "connected" | "reconnecting" | "disconnected";

const statusConfig: Record<Status, { color: string; label: string }> = {
  connected: { color: "bg-trade-green", label: "Connected" },
  reconnecting: { color: "bg-accent-yellow", label: "Reconnecting" },
  disconnected: { color: "bg-trade-red", label: "Disconnected" },
};

export function ConnectionStatus({ status }: { status: Status }) {
  const config = statusConfig[status];

  return (
    <div className="flex items-center gap-1.5 text-xs text-text-muted">
      <div className={`w-2 h-2 rounded-full ${config.color}`} />
      {config.label}
    </div>
  );
}
