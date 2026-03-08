import { useState, useEffect } from 'react';

export interface DailyCommits {
  date: string;      // YYYY-MM-DD
  count: number;
  isAfterClaude: boolean;
}

interface GitHubEvent {
  type: string;
  created_at: string;
  payload: {
    commits?: { sha: string }[];
    size?: number;
  };
}

function groupByDay(events: GitHubEvent[], claudeStartDate: string): DailyCommits[] {
  const map = new Map<string, number>();
  const claudeDate = new Date(claudeStartDate);

  for (const event of events) {
    if (event.type !== 'PushEvent') continue;
    const count = event.payload.commits?.length ?? event.payload.size ?? 0;
    if (count === 0) continue;
    const date = event.created_at.slice(0, 10); // YYYY-MM-DD
    map.set(date, (map.get(date) ?? 0) + count);
  }

  // Build sorted array covering last 90 days
  const result: DailyCommits[] = [];
  const today = new Date();
  for (let i = 89; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    const dateStr = d.toISOString().slice(0, 10);
    result.push({
      date: dateStr,
      count: map.get(dateStr) ?? 0,
      isAfterClaude: d >= claudeDate,
    });
  }
  return result;
}

export function useGitHubCommits(username: string, claudeStartDate: string) {
  const [data, setData] = useState<DailyCommits[]>([]);
  const [totalCommits, setTotalCommits] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchEvents() {
      try {
        // Fetch up to 3 pages (300 events) to cover ~90 days
        const pages = await Promise.all([
          fetch(`https://api.github.com/users/${username}/events?per_page=100&page=1`),
          fetch(`https://api.github.com/users/${username}/events?per_page=100&page=2`),
          fetch(`https://api.github.com/users/${username}/events?per_page=100&page=3`),
        ]);

        const jsons = await Promise.all(
          pages.map((r) => (r.ok ? r.json() : Promise.resolve([])))
        );
        const allEvents: GitHubEvent[] = jsons.flat();

        const dailyData = groupByDay(allEvents, claudeStartDate);
        setData(dailyData);
        setTotalCommits(dailyData.reduce((sum, d) => sum + d.count, 0));
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch');
      } finally {
        setLoading(false);
      }
    }

    fetchEvents();
  }, [username, claudeStartDate]);

  return { data, totalCommits, loading, error };
}
