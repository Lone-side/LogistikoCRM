import type { ElementType, ReactNode } from 'react';

interface EmptyStateProps {
  icon?: ElementType;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ icon: Icon, title, description, action, className = '' }: EmptyStateProps) {
  return (
    <div className={`flex flex-col items-center justify-center text-center py-12 px-4 ${className}`}>
      {Icon && (
        <div className="p-3 rounded-full bg-slate-100 mb-3">
          <Icon size={28} className="text-slate-400" aria-hidden="true" />
        </div>
      )}
      <p className="text-sm font-medium text-slate-900">{title}</p>
      {description && <p className="mt-1 text-sm text-slate-500 max-w-sm">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export default EmptyState;
