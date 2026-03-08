"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.createProfile = createProfile;
exports.updateProfile = updateProfile;
exports.getUser = getUser;
exports.addScore = addScore;
exports.addAnalysis = addAnalysis;
exports.getAverageScore = getAverageScore;
exports.getPercentile = getPercentile;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const uuid_1 = require("uuid");
const DATA_DIR = path_1.default.join(__dirname, '..', 'data');
function ensureDataDir() {
    if (!fs_1.default.existsSync(DATA_DIR)) {
        fs_1.default.mkdirSync(DATA_DIR, { recursive: true });
    }
}
function getStorePath() {
    return path_1.default.join(DATA_DIR, 'store.json');
}
function readStore() {
    ensureDataDir();
    const storePath = getStorePath();
    if (!fs_1.default.existsSync(storePath))
        return {};
    return JSON.parse(fs_1.default.readFileSync(storePath, 'utf-8'));
}
function writeStore(data) {
    ensureDataDir();
    fs_1.default.writeFileSync(getStorePath(), JSON.stringify(data, null, 2));
}
function createProfile(profileData) {
    const store = readStore();
    const id = (0, uuid_1.v4)();
    const now = new Date().toISOString();
    const profile = {
        id,
        ...profileData,
        createdAt: now,
        updatedAt: now,
    };
    store[id] = { profile, scores: [], analyses: [] };
    writeStore(store);
    return profile;
}
function updateProfile(id, profileData) {
    const store = readStore();
    if (!store[id])
        return null;
    store[id].profile = {
        ...store[id].profile,
        ...profileData,
        updatedAt: new Date().toISOString(),
    };
    writeStore(store);
    return store[id].profile;
}
function getUser(id) {
    const store = readStore();
    return store[id] || null;
}
function addScore(userId, photoFile, score) {
    const store = readStore();
    if (!store[userId]) {
        const now = new Date().toISOString();
        store[userId] = {
            profile: { id: userId, createdAt: now, updatedAt: now },
            scores: [],
            analyses: [],
        };
    }
    const entry = { photoFile, score, scoredAt: new Date().toISOString() };
    store[userId].scores.push(entry);
    writeStore(store);
    return entry;
}
function addAnalysis(userId, suggestions) {
    const store = readStore();
    if (!store[userId])
        return;
    store[userId].analyses.push({
        analyzedAt: new Date().toISOString(),
        suggestions,
    });
    writeStore(store);
}
function getAverageScore(userId) {
    const store = readStore();
    const user = store[userId];
    if (!user || user.scores.length === 0)
        return null;
    const sum = user.scores.reduce((acc, s) => acc + s.score, 0);
    return Math.round((sum / user.scores.length) * 10) / 10;
}
// Percentile based on roughly normal distribution (mean=5.5, sd=1.5)
function getPercentile(score) {
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
