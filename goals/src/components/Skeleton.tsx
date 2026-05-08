interface SkeletonProps {
  lines?: number;
  className?: string;
}

export default function Skeleton({ lines = 3, className }: SkeletonProps) {
  return (
    <div className={className}>
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="animate-pulse bg-gray-200 dark:bg-gray-700 rounded h-4 mb-2"
        />
      ))}
    </div>
  );
}
