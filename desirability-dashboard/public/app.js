// State
let userId = localStorage.getItem('dd_userId') || null;
let hasScore = false;
let hasProfile = false;

// DOM refs
const photoInput = document.getElementById('photoInput');
const uploadArea = document.getElementById('uploadArea');
const uploadPrompt = document.getElementById('uploadPrompt');
const photoPreview = document.getElementById('photoPreview');
const btnScore = document.getElementById('btnScore');
const scoreStatus = document.getElementById('scoreStatus');
const scoreResults = document.getElementById('scoreResults');
const avgScoreEl = document.getElementById('avgScore');
const percentileFill = document.getElementById('percentileFill');
const percentileMarker = document.getElementById('percentileMarker');
const percentileText = document.getElementById('percentileText');
const individualScores = document.getElementById('individualScores');
const profileForm = document.getElementById('profileForm');
const profileStatus = document.getElementById('profileStatus');
const btnAnalyze = document.getElementById('btnAnalyze');
const analyzeStatus = document.getElementById('analyzeStatus');
const analysisResults = document.getElementById('analysisResults');
const manualScoreInput = document.getElementById('manualScore');
const btnManualScore = document.getElementById('btnManualScore');

// Photo upload handling
uploadArea.addEventListener('click', () => photoInput.click());

photoInput.addEventListener('change', () => {
  const files = photoInput.files;
  photoPreview.innerHTML = '';
  if (files.length > 0) {
    uploadPrompt.style.display = 'none';
    for (const file of files) {
      const img = document.createElement('img');
      img.src = URL.createObjectURL(file);
      photoPreview.appendChild(img);
    }
    btnScore.disabled = false;
  } else {
    uploadPrompt.style.display = '';
    btnScore.disabled = true;
  }
});

// Score photos
btnScore.addEventListener('click', async () => {
  const files = photoInput.files;
  if (!files || files.length === 0) return;

  const formData = new FormData();
  for (const file of files) {
    formData.append('photos', file);
  }
  if (userId) formData.append('userId', userId);

  setStatus(scoreStatus, 'Uploading and analyzing photos... This may take up to 60 seconds per photo.', 'loading');
  btnScore.disabled = true;

  try {
    const res = await fetch('/api/score', { method: 'POST', body: formData });
    const data = await res.json();

    if (!res.ok) throw new Error(data.error);

    userId = data.userId;
    localStorage.setItem('dd_userId', userId);

    // Check if any scores failed
    const failed = data.scores.filter(s => s.error);
    if (failed.length > 0 && data.scores.length === failed.length) {
      setStatus(scoreStatus,
        'Auto-scoring failed. Please use manual score entry below. Error: ' + failed[0].error,
        'error'
      );
      btnScore.disabled = false;
      return;
    }

    if (failed.length > 0) {
      setStatus(scoreStatus,
        `${data.scores.length - failed.length}/${data.scores.length} photos scored. Some failed: ${failed[0].error}`,
        'error'
      );
    } else {
      setStatus(scoreStatus, 'Photos scored successfully!', 'success');
    }

    displayScores(data);
  } catch (err) {
    setStatus(scoreStatus, 'Error: ' + err.message + '. Try manual score entry below.', 'error');
    btnScore.disabled = false;
  }
});

// Manual score entry
btnManualScore.addEventListener('click', async () => {
  const score = parseFloat(manualScoreInput.value);
  if (!score || score < 1 || score > 10) {
    setStatus(scoreStatus, 'Enter a valid score between 1 and 10', 'error');
    return;
  }

  if (!userId) {
    // Create a user first
    const profileRes = await fetch('/api/profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    const profileData = await profileRes.json();
    userId = profileData.id;
    localStorage.setItem('dd_userId', userId);
  }

  try {
    const res = await fetch('/api/score/manual', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ userId, score }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);

    setStatus(scoreStatus, 'Score saved!', 'success');
    displayScores({
      scores: [{ score, filename: 'manual' }],
      averageScore: data.averageScore,
      percentile: data.percentile,
    });
  } catch (err) {
    setStatus(scoreStatus, 'Error: ' + err.message, 'error');
  }
});

function displayScores(data) {
  hasScore = true;
  scoreResults.hidden = false;

  avgScoreEl.textContent = data.averageScore;
  avgScoreEl.style.color = getScoreColor(data.averageScore);

  const pct = data.percentile;
  percentileMarker.style.left = pct + '%';
  percentileText.textContent = `${pct}th percentile — Top ${100 - pct}%`;

  individualScores.innerHTML = '';
  const validScores = data.scores.filter(s => s.score > 0);
  if (validScores.length > 1) {
    for (const s of validScores) {
      const chip = document.createElement('span');
      chip.className = 'score-chip';
      chip.textContent = s.score + '/10';
      individualScores.appendChild(chip);
    }
  }

  updateAnalyzeButton();
}

function getScoreColor(score) {
  if (score >= 7.5) return '#22c55e';
  if (score >= 6) return '#3b82f6';
  if (score >= 4.5) return '#f59e0b';
  return '#ef4444';
}

// Profile form
profileForm.addEventListener('submit', async (e) => {
  e.preventDefault();

  const profileData = {
    userId,
    age: parseInt(document.getElementById('age').value) || undefined,
    gender: document.getElementById('gender').value || undefined,
    location: document.getElementById('location').value || undefined,
    height: document.getElementById('height').value || undefined,
    bodyType: document.getElementById('bodyType').value || undefined,
    lookingForGender: document.getElementById('lookingForGender').value || undefined,
    lookingForAgeMin: parseInt(document.getElementById('lookingForAgeMin').value) || undefined,
    lookingForAgeMax: parseInt(document.getElementById('lookingForAgeMax').value) || undefined,
    interests: document.getElementById('interests').value || undefined,
    bio: document.getElementById('bio').value || undefined,
  };

  try {
    const res = await fetch('/api/profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(profileData),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);

    userId = data.id;
    localStorage.setItem('dd_userId', userId);
    hasProfile = true;

    setStatus(profileStatus, 'Profile saved!', 'success');
    updateAnalyzeButton();
  } catch (err) {
    setStatus(profileStatus, 'Error: ' + err.message, 'error');
  }
});

// Analysis
btnAnalyze.addEventListener('click', async () => {
  if (!userId) return;

  setStatus(analyzeStatus, 'Generating AI analysis... This may take 15-30 seconds.', 'loading');
  btnAnalyze.disabled = true;

  try {
    const res = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ userId }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);

    setStatus(analyzeStatus, '', '');
    analysisResults.hidden = false;

    document.getElementById('suggestionsContent').innerHTML =
      '<h2>Improvement Suggestions</h2>' + markdownToHtml(data.suggestions);
    document.getElementById('typeInsightsContent').innerHTML =
      '<h2>What Your Type Wants</h2>' + markdownToHtml(data.typeInsights);
  } catch (err) {
    setStatus(analyzeStatus, 'Error: ' + err.message, 'error');
    btnAnalyze.disabled = false;
  }
});

function updateAnalyzeButton() {
  btnAnalyze.disabled = !hasScore;
}

function setStatus(el, message, type) {
  el.textContent = message;
  el.className = 'status ' + (type || '');
}

// Simple markdown to HTML
function markdownToHtml(md) {
  if (!md) return '';
  return md
    .replace(/## (.+)/g, '<h2>$1</h2>')
    .replace(/### (.+)/g, '<h3>$1</h3>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
    .replace(/\n{2,}/g, '</p><p>')
    .replace(/^(?!<[hul])/gm, function(match) { return match; })
    .replace(/\n/g, '<br>');
}

// Load existing data on page load
async function loadExisting() {
  if (!userId) return;
  try {
    const res = await fetch('/api/results/' + userId);
    if (!res.ok) return;
    const data = await res.json();

    if (data.scores && data.scores.length > 0) {
      displayScores({
        scores: data.scores,
        averageScore: data.averageScore,
        percentile: data.percentile,
      });
    }

    if (data.profile) {
      const p = data.profile;
      if (p.age) document.getElementById('age').value = p.age;
      if (p.gender) document.getElementById('gender').value = p.gender;
      if (p.location) document.getElementById('location').value = p.location;
      if (p.height) document.getElementById('height').value = p.height;
      if (p.bodyType) document.getElementById('bodyType').value = p.bodyType;
      if (p.lookingForGender) document.getElementById('lookingForGender').value = p.lookingForGender;
      if (p.lookingForAgeMin) document.getElementById('lookingForAgeMin').value = p.lookingForAgeMin;
      if (p.lookingForAgeMax) document.getElementById('lookingForAgeMax').value = p.lookingForAgeMax;
      if (p.interests) document.getElementById('interests').value = p.interests;
      if (p.bio) document.getElementById('bio').value = p.bio;
      hasProfile = true;
    }
  } catch (err) {
    // Ignore — fresh start
  }
}

loadExisting();
