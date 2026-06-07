import { type HTMLAttributes } from 'react';

function cx(...c: Array<string | undefined | false>): string {
  return c.filter(Boolean).join(' ');
}

export type BadgeTone =
  | 'neutral'
  | 'brand'
  | 'success'
  | 'warning'
  | 'danger';

const toneStyles: Record<BadgeTone, string> = {
  neutral: 'bg-gray-100 text-gray-700',
  brand: 'bg-brand-100 text-brand-800',
  success: 'bg-emerald-100 text-emerald-800',
  warning: 'bg-amber-100 text-amber-800',
  danger: 'bg-red-100 text-red-700',
};

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
}

/** Consistent status/label pill — one shape, semantic tones. */
export function Badge({ tone = 'neutral', className, ...props }: BadgeProps) {
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full',
        toneStyles[tone],
        className,
      )}
      {...props}
    />
  );
}
