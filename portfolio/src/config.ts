export const config = {
  personal: {
    name: 'Alexander Coffman',
    tagline: 'Building at Network School · Shipping AI tools daily',
    github: 'https://github.com/Alzxcvb',
  },
  github: {
    username: 'Alzxcvb',
    claudeStartDate: '2026-01-20', // when Claude Code adoption really kicked in
  },
  metrics: {
    mrr: 0,
    projectsCompleted: 5,
    socialPosts: 18,
    socialImpressions: 0,
  },
  networkSchool: {
    referralUrl: 'https://ns.com/acoffman/invite',
    personalKickback: 500,
    monthlyPrice: 1500,
    freeWeekValue: 375,
  },
  projects: [
    {
      name: 'OpenClaw Telegram Bot',
      description: 'AI-powered Telegram assistant using Gemini 2.0 Flash + Perplexity Sonar Pro for real-time web search. Deployed on Railway.',
      status: 'live' as const,
      tags: ['AI', 'Telegram', 'Railway', 'OpenRouter'],
      repo: 'https://github.com/Alzxcvb/openclaw-telegram-bot',
    },
    {
      name: 'AI Model Router',
      description: 'Intelligent routing layer that dispatches prompts to the optimal LLM based on task type, cost, and latency requirements.',
      status: 'building' as const,
      tags: ['AI', 'TypeScript', 'API'],
      repo: 'https://github.com/Alzxcvb/ai-model-router',
    },
    {
      name: 'Desirability Dashboard',
      description: 'Analytics dashboard for tracking product desirability signals — user sentiment, engagement, and market fit indicators.',
      status: 'building' as const,
      tags: ['React', 'Analytics', 'Dashboard'],
      repo: 'https://github.com/Alzxcvb/desirability-dashboard',
    },
    {
      name: 'Thoughtleader Bot',
      description: 'Automated content generation bot that produces high-signal LinkedIn posts from research and personal insights.',
      status: 'building' as const,
      tags: ['AI', 'Content', 'Automation'],
      repo: 'https://github.com/Alzxcvb/thoughtleader',
    },
    {
      name: 'Grad Thesis Tracker',
      description: 'Research tool tracking European graduate programs, deadlines, funding opportunities, and application requirements.',
      status: 'research' as const,
      tags: ['Research', 'Education', 'Data'],
      repo: null,
    },
  ],
} as const;

export type ProjectStatus = 'live' | 'building' | 'research';
