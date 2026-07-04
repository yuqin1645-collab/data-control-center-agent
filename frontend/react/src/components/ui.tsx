import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { ButtonHTMLAttributes, InputHTMLAttributes, TextareaHTMLAttributes, ReactNode } from "react";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// Button
type ButtonVariant = "default" | "secondary" | "outline" | "ghost" | "success" | "danger";
const buttonVariants: Record<ButtonVariant, string> = {
  default: "bg-primary text-primary-foreground hover:bg-primary/90",
  secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
  outline: "border border-border bg-transparent hover:bg-secondary/50",
  ghost: "hover:bg-secondary/50",
  success: "bg-success text-white hover:bg-success/90",
  danger: "bg-danger text-white hover:bg-danger/90",
};

export function Button({
  className,
  variant = "default",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50",
        buttonVariants[variant],
        className
      )}
      {...props}
    />
  );
}

// Card
export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cn("rounded-xl border border-border bg-card text-card-foreground", className)}>
      {children}
    </div>
  );
}
export function CardHeader({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("p-4 border-b border-border", className)}>{children}</div>;
}
export function CardContent({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("p-4", className)}>{children}</div>;
}
export function CardTitle({ className, children }: { className?: string; children: ReactNode }) {
  return <h3 className={cn("font-semibold text-lg", className)}>{children}</h3>;
}

// Input
export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "w-full rounded-lg border border-border bg-secondary/50 px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring",
        className
      )}
      {...props}
    />
  );
}

// Textarea
export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        "w-full rounded-lg border border-border bg-secondary/50 px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring resize-none",
        className
      )}
      {...props}
    />
  );
}

// Badge
type BadgeVariant = "default" | "success" | "warning" | "danger" | "muted" | "primary";
const badgeVariants: Record<BadgeVariant, string> = {
  default: "bg-secondary text-secondary-foreground border-border",
  success: "bg-success/20 text-success border-success/30",
  warning: "bg-warning/20 text-warning border-warning/30",
  danger: "bg-danger/20 text-danger border-danger/30",
  muted: "bg-secondary/50 text-muted-foreground border-border",
  primary: "bg-primary/20 text-primary border-primary/30",
};
export function Badge({
  className,
  variant = "default",
  children,
}: {
  className?: string;
  variant?: BadgeVariant;
  children: ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium",
        badgeVariants[variant],
        className
      )}
    >
      {children}
    </span>
  );
}

// Table
export function Table({ children }: { children: ReactNode }) {
  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <table className="w-full text-sm">{children}</table>
    </div>
  );
}
export function Th({ children, className }: { children?: ReactNode; className?: string }) {
  return <th className={cn("px-3 py-2 text-left font-medium bg-secondary/50", className)}>{children}</th>;
}
export function Td({ children, className }: { children?: ReactNode; className?: string }) {
  return <td className={cn("px-3 py-2", className)}>{children}</td>;
}
export function Tr({ children, className }: { children: ReactNode; className?: string }) {
  return <tr className={cn("border-t border-border", className)}>{children}</tr>;
}

// Skeleton
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-lg bg-secondary/50", className)} />;
}

// Avatar
export function Avatar({ initials, className }: { initials: string; className?: string }) {
  return (
    <div
      className={cn(
        "flex items-center justify-center rounded-full bg-gradient-to-br from-purple-500 to-cyan-500 text-xs font-bold",
        className
      )}
    >
      {initials}
    </div>
  );
}
