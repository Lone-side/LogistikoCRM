import { type ReactNode } from 'react';

export type BadgeVariant =
  | 'neutral'
  | 'brand'
  | 'success'
  | 'warning'
  | 'danger'
  | 'info'
  | 'purple';

interface BadgeProps {
  variant?: BadgeVariant;
  icon?: ReactNode;
  children: ReactNode;
  className?: string;
}

const variantStyles: Record<BadgeVariant, string> = {
  neutral: 'bg-slate-100 text-slate-700 ring-slate-600/10',
  brand: 'bg-brand-50 text-brand-800 ring-brand-700/10',
  success: 'bg-success-100 text-success-700 ring-success-600/20',
  warning: 'bg-warning-100 text-warning-700 ring-warning-600/20',
  danger: 'bg-danger-100 text-danger-700 ring-danger-600/20',
  info: 'bg-sky-100 text-sky-700 ring-sky-600/20',
  purple: 'bg-purple-100 text-purple-700 ring-purple-600/20',
};

/** Ενιαίο status badge — αντικαθιστά τα ad-hoc getStatusBadge() ανά σελίδα. */
export function Badge({ variant = 'neutral', icon, children, className = '' }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full ring-1 ring-inset whitespace-nowrap ${variantStyles[variant]} ${className}`}
    >
      {icon}
      {children}
    </span>
  );
}

export default Badge;
