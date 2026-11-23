import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

// shadcn/ui class helper: join conditional classes, later Tailwind classes win.
export function cn(...inputs) {
  return twMerge(clsx(inputs));
}
