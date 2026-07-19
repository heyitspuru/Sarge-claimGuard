// Minimal shadcn-style class combiner (no clsx/tailwind-merge dependency needed here).
export function cn(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}
