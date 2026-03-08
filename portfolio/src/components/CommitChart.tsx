import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
} from 'recharts';
import type { DailyCommits } from '../hooks/useGitHubCommits';
import { config } from '../config';

interface CommitChartProps {
  data: DailyCommits[];
  loading: boolean;
  error: string | null;
}

function formatDate(dateStr: string) {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// Show only every Nth label to avoid crowding
function tickFormatter(value: string, index: number) {
  if (index % 10 !== 0) return '';
  return formatDate(value);
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm shadow-xl">
      <p className="text-gray-400">{formatDate(label)}</p>
      <p className="text-blue-400 font-semibold">{payload[0].value} commits</p>
    </div>
  );
}

export function CommitChart({ data, loading, error }: CommitChartProps) {
  const claudeDate = config.github.claudeStartDate;

  if (loading) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <div className="h-5 w-64 bg-gray-800 rounded animate-pulse mb-2" />
        <div className="h-4 w-48 bg-gray-800 rounded animate-pulse mb-6" />
        <div className="h-48 bg-gray-800/50 rounded animate-pulse" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <p className="text-gray-500 text-sm">Could not load commit data: {error}</p>
      </div>
    );
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-6">
        <div>
          <h2 className="text-white font-semibold text-lg">Commits / day</h2>
          <p className="text-gray-500 text-sm">Before &amp; after adopting Claude Code — last 90 days</p>
        </div>
        <div className="flex items-center gap-4 text-xs">
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-sm bg-gray-700" />
            <span className="text-gray-500">Before Claude</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-sm bg-blue-500" />
            <span className="text-gray-400">After Claude</span>
          </span>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} barCategoryGap="20%">
          <XAxis
            dataKey="date"
            tickFormatter={tickFormatter}
            tick={{ fill: '#6b7280', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: '#6b7280', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            allowDecimals={false}
            width={24}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
          <ReferenceLine
            x={claudeDate}
            stroke="#f59e0b"
            strokeDasharray="4 3"
            label={{
              value: '⚡ Claude',
              position: 'insideTopRight',
              fill: '#f59e0b',
              fontSize: 11,
              fontWeight: 600,
            }}
          />
          <Bar dataKey="count" radius={[2, 2, 0, 0]}>
            {data.map((entry) => (
              <Cell
                key={entry.date}
                fill={entry.isAfterClaude ? '#3b82f6' : '#374151'}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
