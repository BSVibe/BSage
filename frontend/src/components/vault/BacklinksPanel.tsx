import { ArrowUpLeft, ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";
import type { VaultBacklink } from "../../api/types";

interface BacklinksPanelProps {
  backlinks: VaultBacklink[];
  onNavigate: (path: string) => void;
}

export function BacklinksPanel({ backlinks, onNavigate }: BacklinksPanelProps) {
  const [open, setOpen] = useState(backlinks.length > 0);

  if (backlinks.length === 0) return null;

  return (
    <div className="mt-6 border-t border-gray-200 dark:border-gray-700 pt-4">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 text-xs font-medium text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
      >
        {open ? (
          <ChevronDown className="w-3.5 h-3.5" />
        ) : (
          <ChevronRight className="w-3.5 h-3.5" />
        )}
        <ArrowUpLeft className="w-3.5 h-3.5" />
        <span>Backlinks ({backlinks.length})</span>
      </button>
      {open && (
        <ul className="mt-2 space-y-1">
          {backlinks.map((bl) => (
            <li key={bl.path}>
              <button
                onClick={() => onNavigate(bl.path)}
                className="w-full text-left text-xs px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700/50 transition-colors group"
              >
                <span className="text-violet-600 dark:text-violet-400 group-hover:underline">
                  {bl.title}
                </span>
                <span className="ml-2 text-gray-400 dark:text-gray-500 font-mono text-[10px]">
                  {bl.path}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
