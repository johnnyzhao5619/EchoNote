import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** shadcn/ui 标准 cn 工具函数 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
