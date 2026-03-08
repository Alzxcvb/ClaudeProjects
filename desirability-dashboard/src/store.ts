import fs from 'fs';
import path from 'path';
import { v4 as uuidv4 } from 'uuid';

const DATA_DIR = path.join(__dirname, '..', 'data');

interface Profile {
  id: string;
  age?: number;
  gender?: string;
  location?: string;
  height?: string;
  bodyType?: string;
  lookingForAgeMin?: number;
  lookingForAgeMax?: number;
  lookingForGender?: string;
  interests?: string;
  bio?: string;
  createdAt: string;
  updatedAt: string;
}

interface ScoreEntry {
  photoFile: string;
  score: number;
  scoredAt: string;
}

interface UserRecord {
  profile: Profile;
  scores: ScoreEntry[];
  analyses: Array<{ analyzedAt: string; suggestions: string }>;
}

function ensureDataDir() {
  if (!fs.existsSync(DATA_DIR)) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
  }
}

function getStorePath(): string {
  return path.join(DATA_DIR, 'store.json');
}

function readStore(): Record<string, UserRecord> {
  ensureDataDir();
  const storePath = getStorePath();
  if (!fs.existsSync(storePath)) return {};
  return JSON.parse(fs.readFileSync(storePath, 'utf-8'));
}

function writeStore(data: Record<string, UserRecord>) {
  ensureDataDir();
  fs.writeFileSync(getStorePath(), JSON.stringify(data, null, 2));
}

export function createProfile(profileData: Partial<Profile>): Profile {
  const store = readStore();
  const id = uuidv4();
  const now = new Date().toISOString();
  const profile: Profile = {
    id,
    ...profileData,
    createdAt: now,
    updatedAt: now,
  };
  store[id] = { profile, scores: [], analyses: [] };
  writeStore(store);
  return profile;
}

export function updateProfile(id: string, profileData: Partial<Profile>): Profile | null {
  const store = readStore();
  if (!store[id]) return null;
  store[id].profile = {
    ...store[id].profile,
    ...profileData,
    updatedAt: new Date().toISOString(),
  };
  writeStore(store);
  return store[id].profile;
}

export function getUser(id: string): UserRecord | null {
  const store = readStore();
  return store[id] || null;
}

export function addScore(userId: string, photoFile: string, score: number): ScoreEntry {
  const store = readStore();
  if (!store[userId]) {
    const now = new Date().toISOString();
    store[userId] = {
      profile: { id: userId, createdAt: now, updatedAt: now },
      scores: [],
      analyses: [],
    };
  }
  const entry: ScoreEntry = { photoFile, score, scoredAt: new Date().toISOString() };
  store[userId].scores.push(entry);
  writeStore(store);
  return entry;
}

export function addAnalysis(userId: string, suggestions: string) {
  const store = readStore();
  if (!store[userId]) return;
  store[userId].analyses.push({
    analyzedAt: new Date().toISOString(),
    suggestions,
  });
  writeStore(store);
}

export function getAverageScore(userId: string): number | null {
  const store = readStore();
  const user = store[userId];
  if (!user || user.scores.length === 0) return null;
  const sum = user.scores.reduce((acc, s) => acc + s.score, 0);
  return Math.round((sum / user.scores.length) * 10) / 10;
}

// Percentile based on roughly normal distribution (mean=5.5, sd=1.5)
export function getPercentile(score: number): number {
  // Using a simplified CDF approximation for normal distribution
  const mean = 5.5;
  const sd = 1.5;
  const z = (score - mean) / sd;
  // Approximation of normal CDF
  const t = 1 / (1 + 0.2316419 * Math.abs(z));
  const d = 0.3989422804 * Math.exp(-z * z / 2);
  const p = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
  const cdf = z > 0 ? 1 - p : p;
  return Math.round(cdf * 100);
}
