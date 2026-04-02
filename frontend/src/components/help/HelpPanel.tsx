interface HelpSection {
  title: string;
  description: string;
  docLink?: string;
}

const HELP_CONTENT: Record<string, HelpSection> = {
  "#chat": {
    title: "Chat",
    description: "AI 비서와 대화하며 지식을 수집합니다",
    docLink: "https://bsvibe.dev/bsage/getting-started",
  },
  "#graph": {
    title: "Knowledge Graph",
    description: "Knowledge Graph에서 지식 관계를 탐색합니다",
  },
  "#plugins": {
    title: "Plugins",
    description: "플러그인을 활성화하고 설정합니다",
    docLink: "https://bsvibe.dev/bsage/features/plugins",
  },
  "#vault": {
    title: "Vault",
    description: "Vault 파일을 탐색합니다",
  },
  "#dashboard": {
    title: "Dashboard",
    description: "BSage 전체 상태를 확인합니다",
  },
};

const DEFAULT_HELP: HelpSection = {
  title: "BSage",
  description: "BSage는 온톨로지 기반 지식 관리 AI 비서입니다",
};

interface HelpPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export function HelpPanel({ isOpen, onClose }: HelpPanelProps) {
  const hash = window.location.hash || "";
  const section = HELP_CONTENT[hash] ?? DEFAULT_HELP;

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-40"
          onClick={onClose}
        />
      )}
      <div
        className={`fixed top-0 right-0 h-full w-80 bg-gray-900 border-l border-gray-700 text-gray-50 z-50 shadow-xl transform transition-transform duration-200 ease-in-out ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <h2 className="text-lg font-semibold text-emerald-400">도움말</h2>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-gray-800 text-gray-400 hover:text-gray-50 transition-colors"
            aria-label="Close help panel"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-5 w-5"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        </div>

        <div className="p-4 space-y-4">
          <div>
            <h3 className="text-base font-medium text-emerald-400 mb-1">
              {section.title}
            </h3>
            <p className="text-sm text-gray-300 leading-relaxed">
              {section.description}
            </p>
          </div>

          {section.docLink && (
            <a
              href={section.docLink}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-sm text-emerald-400 hover:text-emerald-300 transition-colors"
            >
              <span>문서 보기</span>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-4 w-4"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path d="M11 3a1 1 0 100 2h2.586l-6.293 6.293a1 1 0 101.414 1.414L15 6.414V9a1 1 0 102 0V4a1 1 0 00-1-1h-5z" />
                <path d="M5 5a2 2 0 00-2 2v8a2 2 0 002 2h8a2 2 0 002-2v-3a1 1 0 10-2 0v3H5V7h3a1 1 0 000-2H5z" />
              </svg>
            </a>
          )}
        </div>
      </div>
    </>
  );
}
