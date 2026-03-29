import { CATEGORY_COLORS } from "../../utils/constants";

interface BadgeProps {
  category: string;
}

export function Badge({ category }: BadgeProps) {
  const color = CATEGORY_COLORS[category] ?? "bg-gray-800 text-gray-400";
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${color}`}>
      {category}
    </span>
  );
}
