import { Skeleton } from './Skeleton';

interface StatsCardSkeletonProps {
  /** Additional CSS classes */
  className?: string;
}

/**
 * Single stats card skeleton (matches Dashboard stat cards)
 */
export function StatsCardSkeleton({ className = '' }: StatsCardSkeletonProps) {
  return (
    <div className={`bg-white rounded-lg border border-gray-200 p-6 animate-pulse ${className}`}>
      <div className="flex items-center gap-3">
        {/* Icon placeholder */}
        <div className="p-3 rounded-lg bg-gray-200">
          <div className="w-6 h-6" />
        </div>
        {/* Text content */}
        <div className="space-y-2">
          <div className="h-3 bg-gray-200 rounded w-16" />
          <div className="h-6 bg-gray-200 rounded w-12" />
        </div>
      </div>
    </div>
  );
}

/**
 * Grid of stats cards skeletons (4 cards like Dashboard)
 */
export function StatsGridSkeleton({
  count = 4,
  className = '',
}: {
  count?: number;
  className?: string;
}) {
  return (
    <div className={`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 ${className}`}>
      {Array.from({ length: count }).map((_, i) => (
        <StatsCardSkeleton key={i} />
      ))}
    </div>
  );
}

/**
 * Chart skeleton (for pie charts, bar charts, etc.)
 */
export function ChartSkeleton({
  height = 256,
  className = '',
}: {
  height?: number;
  className?: string;
}) {
  return (
    <div className={`bg-white rounded-lg border border-gray-200 p-6 ${className}`}>
      {/* Title */}
      <Skeleton height={20} width={160} className="mb-4" />
      {/* Chart area */}
      <div
        className="flex items-center justify-center animate-pulse"
        style={{ height }}
      >
        <div className="w-32 h-32 bg-gray-200 rounded-full" />
      </div>
      {/* Legend */}
      <div className="flex justify-center gap-4 mt-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="flex items-center gap-2 animate-pulse">
            <div className="w-3 h-3 bg-gray-200 rounded-full" />
            <div className="h-3 bg-gray-200 rounded w-12" />
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Bar chart skeleton
 */
export function BarChartSkeleton({
  bars = 6,
  height = 256,
  className = '',
}: {
  bars?: number;
  height?: number;
  className?: string;
}) {
  return (
    <div className={`bg-white rounded-lg border border-gray-200 p-6 ${className}`}>
      {/* Title */}
      <Skeleton height={20} width={160} className="mb-4" />
      {/* Chart area */}
      <div
        className="flex items-end justify-around gap-2 animate-pulse"
        style={{ height }}
      >
        {Array.from({ length: bars }).map((_, i) => (
          <div
            key={i}
            className="bg-gray-200 rounded-t flex-1"
            style={{ height: `${30 + ((i * 37) % 70)}%` }}
          />
        ))}
      </div>
    </div>
  );
}

/**
 * Deadline list skeleton (matches upcoming deadlines section)
 */
export function DeadlineListSkeleton({
  count = 5,
  className = '',
}: {
  count?: number;
  className?: string;
}) {
  return (
    <div className={`space-y-3 ${className}`}>
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="flex items-center justify-between p-3 bg-gray-50 rounded-lg animate-pulse"
        >
          <div className="space-y-2">
            <div className="h-4 bg-gray-200 rounded w-32" />
            <div className="h-3 bg-gray-200 rounded w-24" />
          </div>
          <div className="text-right space-y-2">
            <div className="h-3 bg-gray-200 rounded w-20" />
            <div className="h-3 bg-gray-200 rounded w-16" />
          </div>
        </div>
      ))}
    </div>
  );
}

export default StatsCardSkeleton;
