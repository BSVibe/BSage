import type { ConnectionState } from "../../api/websocket";

const COLORS: Record<ConnectionState, string> = {
  connected: "bg-accent",
  disconnected: "bg-gray-500",
  reconnecting: "bg-amber-400 animate-pulse",
};

const LABELS: Record<ConnectionState, string> = {
  connected: "Connected",
  disconnected: "Offline",
  reconnecting: "Reconnecting...",
};

interface StatusDotProps {
  state: ConnectionState;
}

export function StatusDot({ state }: StatusDotProps) {
  return (
    <div className="flex items-center gap-1.5">
      <div className={`w-2 h-2 rounded-full ${COLORS[state]}`} />
      <span className="text-xs text-gray-500">{LABELS[state]}</span>
    </div>
  );
}
