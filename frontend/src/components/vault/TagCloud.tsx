import { Hash } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../../api/client";

interface TagCloudProps {
  activeTag: string | null;
  onSelectTag: (tag: string | null) => void;
}

export function TagCloud({ activeTag, onSelectTag }: TagCloudProps) {
  const [tags, setTags] = useState<string[]>([]);

  useEffect(() => {
    api
      .vaultTags()
      .then((data) => {
        const sorted = Object.keys(data.tags).sort();
        setTags(sorted);
      })
      .catch(() => setTags([]));
  }, []);

  if (tags.length === 0) return null;

  return (
    <div className="mb-2 pb-2 border-b border-gray-200 dark:border-gray-700">
      <div className="flex items-center gap-1 mb-1.5">
        <Hash className="w-3 h-3 text-gray-400" />
        <span className="text-[10px] font-medium text-gray-400 uppercase tracking-wide">Tags</span>
      </div>
      <div className="flex flex-wrap gap-1">
        {tags.map((tag) => (
          <button
            key={tag}
            onClick={() => onSelectTag(activeTag === tag ? null : tag)}
            className={`text-[10px] px-1.5 py-0.5 rounded-full transition-colors ${
              activeTag === tag
                ? "bg-violet-100 text-violet-700 dark:bg-violet-900/50 dark:text-violet-300"
                : "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700"
            }`}
          >
            #{tag}
          </button>
        ))}
      </div>
    </div>
  );
}
