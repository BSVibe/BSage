import { useChat } from "../../hooks/useChat";
import { Icon } from "../common/Icon";
import { ChatInput } from "./ChatInput";
import { MessageList } from "./MessageList";
import { MiniGraph } from "./MiniGraph";

export function ChatView() {
  const { messages, isLoading, send, clear } = useChat();

  return (
    <div className="flex h-full">
      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex items-center justify-between px-6 h-12 border-b border-white/5 shrink-0">
          <div className="flex gap-6">
            <span className="text-accent-light border-b-2 border-accent-light pb-1 text-sm font-medium tracking-tight">Chat</span>
            <a href="#/graph" className="text-gray-500 hover:text-gray-300 text-sm tracking-tight transition-colors">Graph</a>
          </div>
          {messages.length > 0 && (
            <button
              onClick={clear}
              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-red-400 transition-colors"
            >
              <Icon name="delete" size={16} />
              Clear
            </button>
          )}
        </div>
        <MessageList messages={messages} isLoading={isLoading} />
        <ChatInput onSend={send} disabled={isLoading} />
      </div>

      {/* Right sidebar: mini graph */}
      <div className="w-64 shrink-0 border-l border-white/5 bg-surface p-3 overflow-y-auto scrollbar-thin hidden lg:block">
        <MiniGraph />
      </div>
    </div>
  );
}
