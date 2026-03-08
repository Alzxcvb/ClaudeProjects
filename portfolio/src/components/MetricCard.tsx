import type { ReactNode } from 'react';

interface MetricCardProps {
  label: string;
  value: string | number;
  subtext?: string;
  icon: ReactNode;
  accent?: 'blue' | 'emerald' | 'amber' | 'purple' | 'gray';
  loading?: boolean;
}

const accentMap = {
  blue: {
    border: 'border-blue-500/30',
    iconBg: 'bg-blue-500/10',
    iconText: 'text-blue-400',
    valueText: 'text-blue-300',
  },
  emerald: {
    border: 'border-emerald-500/30',
    iconBg: 'bg-emerald-500/10',
    iconText: 'text-emerald-400',
    valueText: 'text-emerald-300',
  },
  amber: {
    border: 'border-amber-500/30',
    iconBg: 'bg-amber-500/10',
    iconText: 'text-amber-400',
    valueText: 'text-amber-300',
  },
  purple: {
    border: 'border-purple-500/30',
    iconBg: 'bg-purple-500/10',
    iconText: 'text-purple-400',
    valueText: 'text-purple-300',
  },
  gray: {
    border: 'border-gray-700',
    iconBg: 'bg-gray-800',
    iconText: 'text-gray-400',
    valueText: 'text-gray-300',
  },
};

export function MetricCard({ label, value, subtext, icon, accent = 'blue', loading }: MetricCardProps) {
  const colors = accentMap[accent];

  return (
    <div className={`bg-gray-900 border ${colors.border} rounded-xl p-5 hover:border-opacity-60 transition-all duration-200`}>
      <div className="flex items-start justify-between gap-3">
        <div className={`${colors.iconBg} ${colors.iconText} p-2 rounded-lg`}>
          {icon}
        </div>
        {loading && (
          <div className="w-4 h-4 border-2 border-gray-700 border-t-blue-500 rounded-full animate-spin" />
        )}
      </div>

      <div className="mt-4">
        {loading ? (
          <div className="h-8 w-20 bg-gray-800 rounded animate-pulse mb-1" />
        ) : (
          <div className={`text-2xl font-bold ${colors.valueText}`}>{value}</div>
        )}
        <div className="text-gray-500 text-sm mt-1">{label}</div>
        {subtext && <div className="text-gray-600 text-xs mt-0.5">{subtext}</div>}
      </div>
    </div>
  );
}
