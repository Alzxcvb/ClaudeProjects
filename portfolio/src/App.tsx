import { GitCommit, DollarSign, Layers, BarChart2, Briefcase } from 'lucide-react';
import { Header } from './components/Header';
import { MetricCard } from './components/MetricCard';
import { CommitChart } from './components/CommitChart';
import { ProjectGrid } from './components/ProjectGrid';
import { ReferralCTA } from './components/ReferralCTA';
import { Footer } from './components/Footer';
import { useGitHubCommits } from './hooks/useGitHubCommits';
import { config } from './config';

export default function App() {
  const { data, totalCommits, loading, error } = useGitHubCommits(
    config.github.username,
    config.github.claudeStartDate
  );

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <Header />

      <main className="max-w-6xl mx-auto px-6 py-12 space-y-12">
        {/* Metric Cards */}
        <section>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
            <MetricCard
              label="Commits (90d)"
              value={loading ? '—' : totalCommits}
              subtext="Last 90 days"
              icon={<GitCommit size={18} />}
              accent="blue"
              loading={loading}
            />
            <MetricCard
              label="MRR"
              value={config.metrics.mrr === 0 ? '$0' : `$${(config.metrics.mrr as number).toLocaleString()}`}
              subtext="Growing"
              icon={<DollarSign size={18} />}
              accent="emerald"
            />
            <MetricCard
              label="Projects"
              value={config.metrics.projectsCompleted}
              subtext="Active & shipped"
              icon={<Layers size={18} />}
              accent="purple"
            />
            <MetricCard
              label="Social Posts"
              value={config.metrics.socialPosts}
              subtext="Impressions tracking"
              icon={<BarChart2 size={18} />}
              accent="amber"
            />
            <MetricCard
              label="Gov Salary 😅"
              value="$0"
              subtext="Not my path"
              icon={<Briefcase size={18} />}
              accent="gray"
            />
          </div>
        </section>

        {/* Commit Chart */}
        <CommitChart data={data} loading={loading} error={error} />

        {/* Projects */}
        <ProjectGrid />

        {/* NS Referral CTA */}
        <ReferralCTA />
      </main>

      <Footer />
    </div>
  );
}
