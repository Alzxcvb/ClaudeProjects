"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = __importDefault(require("express"));
const multer_1 = __importDefault(require("multer"));
const path_1 = __importDefault(require("path"));
const uuid_1 = require("uuid");
const scorer_1 = require("./scorer");
const suggestions_1 = require("./ai/suggestions");
const store = __importStar(require("./store"));
const app = (0, express_1.default)();
const PORT = process.env.PORT || 3000;
// Middleware
app.use(express_1.default.json());
app.use(express_1.default.static(path_1.default.join(__dirname, '..', 'public')));
// Multer config for photo uploads
const storage = multer_1.default.diskStorage({
    destination: path_1.default.join(__dirname, '..', 'uploads'),
    filename: (_req, file, cb) => {
        const ext = path_1.default.extname(file.originalname);
        cb(null, `${(0, uuid_1.v4)()}${ext}`);
    },
});
const upload = (0, multer_1.default)({
    storage,
    limits: { fileSize: 10 * 1024 * 1024 }, // 10MB
    fileFilter: (_req, file, cb) => {
        const allowed = /\.(jpg|jpeg|png|webp)$/i;
        if (allowed.test(path_1.default.extname(file.originalname))) {
            cb(null, true);
        }
        else {
            cb(new Error('Only image files (jpg, png, webp) are allowed'));
        }
    },
});
// Create or get user session (simple: store userId in response)
app.post('/api/profile', (req, res) => {
    const { userId, ...profileData } = req.body;
    if (userId) {
        const updated = store.updateProfile(userId, profileData);
        if (updated)
            return res.json(updated);
    }
    const profile = store.createProfile(profileData);
    res.json(profile);
});
// Upload and score photos
app.post('/api/score', upload.array('photos', 3), async (req, res) => {
    const files = req.files;
    if (!files || files.length === 0) {
        return res.status(400).json({ error: 'No photos uploaded' });
    }
    const userId = req.body.userId || (0, uuid_1.v4)();
    // Ensure user exists
    if (!store.getUser(userId)) {
        store.createProfile({ id: userId });
    }
    const results = [];
    for (const file of files) {
        console.log(`Scoring photo: ${file.filename}`);
        const result = await (0, scorer_1.scorePhoto)(file.path);
        if (result.score > 0) {
            store.addScore(userId, file.filename, result.score);
        }
        results.push({
            filename: file.filename,
            ...result,
        });
    }
    const averageScore = store.getAverageScore(userId);
    const percentile = averageScore ? store.getPercentile(averageScore) : null;
    res.json({
        userId,
        scores: results,
        averageScore,
        percentile,
    });
});
// Manual score entry (fallback if Puppeteer fails)
app.post('/api/score/manual', (req, res) => {
    const { userId, score, photoLabel } = req.body;
    if (!userId || score === undefined) {
        return res.status(400).json({ error: 'userId and score are required' });
    }
    if (score < 1 || score > 10) {
        return res.status(400).json({ error: 'Score must be between 1 and 10' });
    }
    if (!store.getUser(userId)) {
        store.createProfile({ id: userId });
    }
    store.addScore(userId, photoLabel || 'manual-entry', score);
    const averageScore = store.getAverageScore(userId);
    const percentile = averageScore ? store.getPercentile(averageScore) : null;
    res.json({ userId, averageScore, percentile });
});
// Get full results
app.get('/api/results/:id', (req, res) => {
    const user = store.getUser(req.params.id);
    if (!user)
        return res.status(404).json({ error: 'User not found' });
    const averageScore = store.getAverageScore(req.params.id);
    const percentile = averageScore ? store.getPercentile(averageScore) : null;
    res.json({
        profile: user.profile,
        scores: user.scores,
        averageScore,
        percentile,
        analyses: user.analyses,
    });
});
// Generate AI analysis
app.post('/api/analyze', async (req, res) => {
    const { userId } = req.body;
    if (!userId)
        return res.status(400).json({ error: 'userId is required' });
    const user = store.getUser(userId);
    if (!user)
        return res.status(404).json({ error: 'User not found' });
    const averageScore = store.getAverageScore(userId);
    if (!averageScore) {
        return res.status(400).json({ error: 'No scores yet. Upload photos first.' });
    }
    const percentile = store.getPercentile(averageScore);
    const input = {
        scores: user.scores.map(s => ({ photoFile: s.photoFile, score: s.score })),
        averageScore,
        percentile,
        profile: user.profile,
    };
    try {
        const [suggestions, typeInsights] = await Promise.all([
            (0, suggestions_1.generateSuggestions)(input),
            (0, suggestions_1.generateTypeInsights)(input),
        ]);
        store.addAnalysis(userId, suggestions);
        res.json({
            suggestions,
            typeInsights,
            averageScore,
            percentile,
        });
    }
    catch (err) {
        console.error('AI analysis error:', err);
        res.status(500).json({ error: `Analysis failed: ${err.message}` });
    }
});
app.listen(PORT, () => {
    console.log(`Desirability Dashboard running at http://localhost:${PORT}`);
});
