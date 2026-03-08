import { Github } from 'lucide-react';
import { config } from '../config';

export function Footer() {
  const year = new Date().getFullYear();

  return (
    <footer className="border-t border-gray-800 mt-16">
      <div className="max-w-6xl mx-auto px-6 py-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-gray-600">
        <div className="flex items-center gap-4">
          <a
            href={config.personal.github}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 hover:text-gray-400 transition-colors"
          >
            <Github size={14} />
            Alzxcvb
          </a>
          <span>·</span>
          <span>{year}</span>
        </div>

        <div className="flex items-center gap-1.5">
          <span>Powered by</span>
          <span className="text-blue-500 font-medium">Claude Code</span>
          <span>· Built at Network School</span>
        </div>
      </div>
    </footer>
  );
}
