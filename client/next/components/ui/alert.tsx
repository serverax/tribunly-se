import { cn } from "@/lib/utils";

export function Alert({
  className,
  variant = "default",
  ...props
}: React.HTMLAttributes<HTMLDivElement> & {
  variant?: "default" | "destructive" | "warning";
}) {
  return (
    <div
      role="alert"
      className={cn(
        "relative w-full rounded-lg border p-4 text-sm",
        variant === "destructive" && "border-destructive/50 text-destructive",
        variant === "warning" && "border-amber-500/50 text-amber-200",
        variant === "default" && "border-border",
        className,
      )}
      {...props}
    />
  );
}
