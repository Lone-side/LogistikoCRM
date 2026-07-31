import type { CSSProperties, ElementType, ReactNode } from 'react';

interface StatCardProps {
  icon: ElementType;
  label: string;
  value: ReactNode;
  /** Χρώμα accent (hex) για το εικονίδιο και τη ράβδο. */
  color?: string;
  hint?: ReactNode;
  onClick?: () => void;
  className?: string;
  style?: CSSProperties;
}

/** Ενιαία στατιστική κάρτα (γενίκευση του τοπικού StatCard του FileManager). */
export function StatCard({ icon: Icon, label, value, color = '#2b6fe3', hint, onClick, className = '', style }: StatCardProps) {
  const Tag = onClick ? 'button' : 'div';
  return (
    <Tag
      onClick={onClick}
      style={style}
      className={`relative overflow-hidden bg-white rounded-xl border border-slate-200 shadow-sm p-4 text-left w-full ${
        onClick ? 'cursor-pointer card-lift focus-visible:shadow-md' : ''
      } ${className}`}
    >
      <span className="absolute inset-y-0 left-0 w-1 rounded-r" style={{ backgroundColor: color }} aria-hidden="true" />
      <div className="flex items-center gap-3 pl-1.5">
        <div className="p-2 rounded-lg shrink-0" style={{ backgroundColor: `${color}15` }}>
          <Icon size={20} style={{ color }} aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <p className="text-2xl font-bold text-slate-900 leading-tight">{value}</p>
          <p className="text-sm text-slate-500 truncate">{label}</p>
          {hint && <p className="text-xs text-slate-400 mt-0.5">{hint}</p>}
        </div>
      </div>
    </Tag>
  );
}

export default StatCard;
