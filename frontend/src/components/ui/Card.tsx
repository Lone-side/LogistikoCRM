import { type HTMLAttributes, forwardRef } from 'react';

function cx(...c: Array<string | undefined | false>): string {
  return c.filter(Boolean).join(' ');
}

/**
 * Refined surface primitive — consistent border/radius/shadow across the app.
 * Replaces the ad-hoc `bg-white rounded-lg border border-gray-200` repeated
 * everywhere, so cards feel intentionally designed.
 */
export const Card = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cx(
        'bg-white border border-gray-200 rounded-xl shadow-sm',
        className,
      )}
      {...props}
    />
  ),
);
Card.displayName = 'Card';

export function CardHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cx('px-5 py-4 border-b border-gray-100', className)} {...props} />;
}

export function CardTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cx('text-base font-semibold text-gray-900', className)} {...props} />;
}

export function CardContent({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cx('p-5', className)} {...props} />;
}
