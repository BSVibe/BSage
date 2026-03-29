import { Shield } from "lucide-react";
import type { ConnectionState } from "../../api/websocket";
import { StatusDot } from "../common/StatusDot";

interface HeaderProps {
  connectionState: ConnectionState;
  pendingApprovals: number;
}

export function Header({ connectionState, pendingApprovals }: HeaderProps) {
  return (
    <header className="flex items-center justify-between px-4 py-2 border-b border-gray-800 bg-gray-900">
      <div />
      <div className="flex items-center gap-4">
        {pendingApprovals > 0 && (
          <div className="flex items-center gap-1.5 text-amber-400">
            <Shield className="w-4 h-4" />
            <span className="text-xs font-medium">{pendingApprovals} pending</span>
          </div>
        )}
        <StatusDot state={connectionState} />
      </div>
    </header>
  );
}
