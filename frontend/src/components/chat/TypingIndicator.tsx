export function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="bg-gray-850 border border-accent/20 rounded-2xl rounded-bl-sm px-4 py-3">
        <div className="flex gap-1">
          <span className="w-2 h-2 bg-accent/60 rounded-full animate-bounce [animation-delay:0ms]" />
          <span className="w-2 h-2 bg-accent/60 rounded-full animate-bounce [animation-delay:150ms]" />
          <span className="w-2 h-2 bg-accent/60 rounded-full animate-bounce [animation-delay:300ms]" />
        </div>
      </div>
    </div>
  );
}
