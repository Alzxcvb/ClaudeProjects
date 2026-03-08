import express from 'express';
import multer from 'multer';
import path from 'path';
import { v4 as uuidv4 } from 'uuid';
import { scorePhoto } from './scorer';
import { generateSuggestions, generateTypeInsights } from './ai/suggestions';
import * as store from './store';

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(express.json());
app.use(express.static(path.join(__dirname, '..', 'public')));

// Multer config for photo uploads
const storage = multer.diskStorage({
  destination: path.join(__dirname, '..', 'uploads'),
  filename: (_req, file, cb) => {
    const ext = path.extname(file.originalname);
    cb(null, `${uuidv4()}${ext}`);
  },
});
const upload = multer({
  storage,
  limits: { fileSize: 10 * 1024 * 1024 }, // 10MB
  fileFilter: (_req, file, cb) => {
    const allowed = /\.(jpg|jpeg|png|webp)$/i;
    if (allowed.test(path.extname(file.originalname))) {
      cb(null, true);
    } else {
      cb(new Error('Only image files (jpg, png, webp) are allowed'));
    }
  },
});

// Create or get user session (simple: store userId in response)
app.post('/api/profile', (req, res) => {
  const { userId, ...profileData } = req.body;
  if (userId) {
    const updated = store.updateProfile(userId, profileData);
    if (updated) return res.json(updated);
  }
  const profile = store.createProfile(profileData);
  res.json(profile);
});

// Upload and score photos
app.post('/api/score', upload.array('photos', 3), async (req, res) => {
  const files = req.files as Express.Multer.File[];
  if (!files || files.length === 0) {
    return res.status(400).json({ error: 'No photos uploaded' });
  }

  const userId = req.body.userId || uuidv4();

  // Ensure user exists
  if (!store.getUser(userId)) {
    store.createProfile({ id: userId } as any);
  }

  const results = [];
  for (const file of files) {
    console.log(`Scoring photo: ${file.filename}`);
    const result = await scorePhoto(file.path);
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
    store.createProfile({ id: userId } as any);
  }

  store.addScore(userId, photoLabel || 'manual-entry', score);
  const averageScore = store.getAverageScore(userId);
  const percentile = averageScore ? store.getPercentile(averageScore) : null;

  res.json({ userId, averageScore, percentile });
});

// Get full results
app.get('/api/results/:id', (req, res) => {
  const user = store.getUser(req.params.id);
  if (!user) return res.status(404).json({ error: 'User not found' });

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
  if (!userId) return res.status(400).json({ error: 'userId is required' });

  const user = store.getUser(userId);
  if (!user) return res.status(404).json({ error: 'User not found' });

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
      generateSuggestions(input),
      generateTypeInsights(input),
    ]);

    store.addAnalysis(userId, suggestions);

    res.json({
      suggestions,
      typeInsights,
      averageScore,
      percentile,
    });
  } catch (err: any) {
    console.error('AI analysis error:', err);
    res.status(500).json({ error: `Analysis failed: ${err.message}` });
  }
});

app.listen(PORT, () => {
  console.log(`Desirability Dashboard running at http://localhost:${PORT}`);
});
