import { ExternalLink, Github, Zap } from 'lucide-react';
import { config } from '../config';

export function Header() {
  return (
    <header className="relative overflow-hidden bg-gray-950 border-b border-gray-800">
      {/* Subtle grid background */}
      <div
        className="absolute inset-0 opacity-10"
        style={{
          backgroundImage:
            'linear-gradient(rgba(59,130,246,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(59,130,246,0.3) 1px, transparent 1px)',
          backgroundSize: '40px 40px',
        }}
      />

      <div className="relative max-w-6xl mx-auto px-6 py-16 flex flex-col md:flex-row items-start md:items-center justify-between gap-8">
        <div>
          {/* Badge */}
          <div className="inline-flex items-center gap-2 bg-blue-500/10 border border-blue-500/30 text-blue-400 text-xs font-semibold px-3 py-1 rounded-full mb-4">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
            Network School · Batch 2026
          </div>

          <h1 className="text-4xl md:text-5xl font-bold text-white mb-3 tracking-tight">
            {config.personal.name}
          </h1>
          <p className="text-gray-400 text-lg max-w-md leading-relaxed">
            {config.personal.tagline}
          </p>

          <div className="flex items-center gap-4 mt-6">
            <a
              href={config.personal.github}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors text-sm"
            >
              <Github size={16} />
              GitHub
            </a>
          </div>
        </div>

        {/* CTA */}
        <div className="shrink-0">
          <a
            href={config.networkSchool.referralUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="group flex items-center gap-3 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white font-semibold px-6 py-4 rounded-xl transition-all duration-200 shadow-lg shadow-blue-500/20 hover:shadow-blue-500/40"
          >
            <Zap size={18} className="text-yellow-300" />
            <span>
              Join NS — get 1 week free
              <br />
              <span className="text-blue-200 font-normal text-sm">+ $500 Venmo from me</span>
            </span>
            <ExternalLink size={14} className="opacity-60 group-hover:opacity-100 transition-opacity" />
          </a>
        </div>
      </div>
    </header>
  );
}
