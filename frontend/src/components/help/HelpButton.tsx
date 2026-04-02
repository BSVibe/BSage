import { useState } from "react";
import { HelpPanel } from "./HelpPanel";

export function HelpButton() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <button
        onClick={() => setIsOpen((prev) => !prev)}
        className="fixed bottom-6 right-6 z-50 w-10 h-10 rounded-full bg-emerald-600 hover:bg-emerald-500 text-gray-50 font-semibold text-lg shadow-lg transition-colors flex items-center justify-center"
        aria-label="Toggle help panel"
      >
        ?
      </button>
      <HelpPanel isOpen={isOpen} onClose={() => setIsOpen(false)} />
    </>
  );
}
