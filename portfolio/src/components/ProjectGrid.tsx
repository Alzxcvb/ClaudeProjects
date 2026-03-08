import { ExternalLink, Circle } from 'lucide-react';
import { config, type ProjectStatus } from '../config';

const statusConfig: Record<ProjectStatus, { label: string; color: string; dot: string }> = {
  live: {
    label: 'Live',
    color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
    dot: 'bg-emerald-400',
  },
  building: {
    label: 'Building',
    color: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
    dot: 'bg-blue-400',
  },
  research: {
    label: 'Research',
    color: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
    dot: 'bg-amber-400',
  },
};

export function ProjectGrid() {
  return (
    <section>
      <div className="mb-6">
        <h2 className="text-white font-semibold text-lg">Projects</h2>
        <p className="text-gray-500 text-sm">What I'm shipping at Network School</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {config.projects.map((project) => {
          const status = statusConfig[project.status];
          return (
            <div
              key={project.name}
              className="bg-gray-900 border border-gray-800 rounded-xl p-5 flex flex-col hover:border-gray-700 transition-colors duration-200"
            >
              {/* Header */}
              <div className="flex items-start justify-between gap-2 mb-3">
                <h3 className="text-white font-semibold text-sm leading-tight">{project.name}</h3>
                <span
                  className={`shrink-0 flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded-full border ${status.color}`}
                >
                  <span className={`w-1.5 h-1.5 rounded-full ${status.dot} ${project.status === 'live' ? 'animate-pulse' : ''}`} />
                  {status.label}
                </span>
              </div>

              {/* Description */}
              <p className="text-gray-400 text-xs leading-relaxed flex-1 mb-4">
                {project.description}
              </p>

              {/* Tags */}
              <div className="flex flex-wrap gap-1.5 mb-4">
                {project.tags.map((tag) => (
                  <span
                    key={tag}
                    className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded"
                  >
                    {tag}
                  </span>
                ))}
              </div>

              {/* Link */}
              {project.repo ? (
                <a
                  href={project.repo}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-blue-400 transition-colors"
                >
                  <ExternalLink size={12} />
                  View on GitHub
                </a>
              ) : (
                <span className="flex items-center gap-1.5 text-xs text-gray-600">
                  <Circle size={12} />
                  Private / in progress
                </span>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
