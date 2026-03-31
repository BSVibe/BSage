import type { ConnectionState } from "../../api/websocket";
import { Icon } from "../common/Icon";
import { StatusDot } from "../common/StatusDot";

interface HeaderProps {
  connectionState: ConnectionState;
  pendingApprovals: number;
}

export function Header({ connectionState, pendingApprovals }: HeaderProps) {
  return (
    <header className="flex items-center justify-between px-6 h-14 border-b border-white/5 bg-gray-800 shrink-0">
      <div />
      <div className="flex items-center gap-4">
        {pendingApprovals > 0 && (
          <div className="flex items-center gap-1.5 text-tertiary">
            <Icon name="shield" size={18} />
            <span className="text-xs font-medium font-mono">{pendingApprovals} pending</span>
          </div>
        )}
        <button className="text-gray-400 hover:bg-white/5 p-2 rounded-lg transition-colors active:scale-95">
          <Icon name="help" size={20} />
        </button>
        <StatusDot state={connectionState} />
      </div>
    </header>
  );
}
