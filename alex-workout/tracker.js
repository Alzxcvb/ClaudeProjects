// Alex Workout — Progress Tracker (localStorage)
const STORAGE_KEY = 'alex-workout-log';

const EXERCISES = {
  push: [
    'Barbell Overhead Press', 'Barbell Bench Press', 'Incline Dumbbell Press',
    'Dumbbell Lateral Raises', 'Cable Tricep Pushdown', 'Overhead Tricep Extension'
  ],
  pull: [
    'Pull-ups / Lat Pulldown', 'Barbell Row', 'Face Pulls',
    'Dumbbell Bicep Curl', 'Hammer Curl'
  ],
  legs: [
    'Barbell Back Squat', 'Romanian Deadlift', 'Leg Press',
    'Leg Curl', 'Calf Raises'
  ],
  abs: [
    'Dead Bug', 'Reverse Crunch', 'Bicycle Crunch',
    'Plank Shoulder Taps', 'Side Plank Hip Dips', 'Russian Twist',
    'Hollow Body Hold', 'Lying Leg Raises'
  ]
};

function getLog() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
  } catch { return []; }
}

function saveLog(log) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(log));
}

function addEntry(entry) {
  const log = getLog();
  const prevBest = log
    .filter(e => e.exercise === entry.exercise)
    .reduce((max, e) => Math.max(max, e.weight), 0);
  const newEntry = { ...entry, id: Date.now(), timestamp: new Date().toISOString() };
  if (entry.weight > prevBest) newEntry.is_pr = true;
  log.push(newEntry);
  saveLog(log);
}

function deleteEntry(id) {
  const log = getLog().filter(e => e.id !== id);
  saveLog(log);
}

function getExerciseHistory(exercise) {
  return getLog()
    .filter(e => e.exercise === exercise)
    .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
}

function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function renderWeeklyVolume() {
  const el = document.getElementById('weekly-volume');
  if (!el) return;
  const cutoff = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
  const log = getLog().filter(e => new Date(e.timestamp) >= cutoff);
  const sessions = ['push', 'pull', 'legs', 'abs'];
  const stats = {};
  sessions.forEach(s => { stats[s] = { volume: 0, entries: 0 }; });
  log.forEach(e => {
    if (stats[e.session]) {
      stats[e.session].volume += e.weight * e.reps * e.sets;
      stats[e.session].entries += 1;
    }
  });
  const rows = sessions.map(s => {
    const { volume, entries } = stats[s];
    return `<tr><td>${s.charAt(0).toUpperCase() + s.slice(1)}</td><td>${volume.toFixed(0)}</td><td>${entries}</td></tr>`;
  }).join('');
  el.innerHTML = `<table><thead><tr><th>Session</th><th>Total Volume (kg)</th><th>Entries</th></tr></thead><tbody>${rows}</tbody></table>`;
}

// --- UI ---

function initTracker() {
  const sessionSelect = document.getElementById('session-select');
  const exerciseSelect = document.getElementById('exercise-select');
  const logForm = document.getElementById('log-form');
  const historyDiv = document.getElementById('history');
  const chartCanvas = document.getElementById('progress-chart');
  const clearBtn = document.getElementById('clear-data');
  const exportBtn = document.getElementById('export-data');
  const importBtn = document.getElementById('import-data');
  const importFileInput = document.getElementById('import-file-input');

  if (!sessionSelect) return;

  // Populate exercises when session changes
  sessionSelect.addEventListener('change', () => {
    const session = sessionSelect.value;
    exerciseSelect.innerHTML = '<option value="">-- Select Exercise --</option>';
    if (EXERCISES[session]) {
      EXERCISES[session].forEach(ex => {
        const opt = document.createElement('option');
        opt.value = ex;
        opt.textContent = ex;
        exerciseSelect.appendChild(opt);
      });
    }
    updateHistory();
    updateChart();
  });

  exerciseSelect.addEventListener('change', () => {
    updateHistory();
    updateChart();
  });

  // Log form submit
  logForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const exercise = exerciseSelect.value;
    const weight = parseFloat(document.getElementById('weight-input').value);
    const reps = parseInt(document.getElementById('reps-input').value);
    const sets = parseInt(document.getElementById('sets-input').value);
    const notes = document.getElementById('notes-input').value.trim();

    if (!exercise) return alert('Select an exercise');
    if (isNaN(weight) || isNaN(reps) || isNaN(sets)) return alert('Fill in weight, reps, and sets');

    addEntry({
      session: sessionSelect.value,
      exercise, weight, reps, sets, notes
    });

    document.getElementById('weight-input').value = '';
    document.getElementById('reps-input').value = '';
    document.getElementById('sets-input').value = '';
    document.getElementById('notes-input').value = '';

    updateHistory();
    updateChart();
    renderWeeklyVolume();
  });

  // Clear all data
  clearBtn.addEventListener('click', () => {
    if (confirm('Delete ALL workout data? This cannot be undone.')) {
      localStorage.removeItem(STORAGE_KEY);
      updateHistory();
      updateChart();
      renderWeeklyVolume();
    }
  });

  // Export data
  exportBtn.addEventListener('click', () => {
    const log = getLog();
    if (!log.length) return alert('No data to export');
    const csv = 'Date,Session,Exercise,Weight(kg),Reps,Sets,Notes\n' +
      log.map(e =>
        `${e.timestamp},${e.session},${e.exercise},${e.weight},${e.reps},${e.sets},"${e.notes || ''}"`
      ).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `workout-log-${new Date().toISOString().slice(0,10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  });

  // Import JSON
  if (importBtn && importFileInput) {
    importBtn.addEventListener('click', () => importFileInput.click());

    importFileInput.addEventListener('change', () => {
      const file = importFileInput.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev) => {
        let imported;
        try {
          imported = JSON.parse(ev.target.result);
        } catch {
          alert('Invalid JSON file.');
          return;
        }
        const required = ['id', 'timestamp', 'session', 'exercise', 'weight', 'reps', 'sets'];
        if (!Array.isArray(imported) || !imported.every(e => required.every(k => k in e))) {
          alert('File must be a JSON array where every entry has: ' + required.join(', ') + '.');
          return;
        }
        if (!confirm('Import ' + imported.length + ' entries from file?')) return;
        const log = getLog();
        const existingIds = new Set(log.map(e => e.id));
        const newEntries = imported.filter(e => !existingIds.has(e.id));
        saveLog(log.concat(newEntries));
        importFileInput.value = '';
        updateHistory();
        updateChart();
        renderWeeklyVolume();
      };
      reader.readAsText(file);
    });
  }

  // Chart mode toggle
  const chartModeBtns = document.querySelectorAll('.chart-mode-btn');
  if (chartModeBtns.length) {
    const savedMode = localStorage.getItem('chart-mode') || 'weight';
    chartModeBtns.forEach(btn => {
      const mode = btn.id.replace('chart-mode-', '');
      if (mode === savedMode) btn.classList.add('active');
      btn.addEventListener('click', () => {
        chartModeBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        localStorage.setItem('chart-mode', mode);
        updateChart();
      });
    });
  }

  // Initial render
  updateHistory();
  updateChart();
  renderWeeklyVolume();
}

function updateHistory() {
  const historyDiv = document.getElementById('history');
  const exercise = document.getElementById('exercise-select').value;

  if (!exercise) {
    // Show recent entries across all exercises
    const log = getLog().sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp)).slice(0, 20);
    if (!log.length) {
      historyDiv.innerHTML = '<p style="color:var(--text-dim)">No entries yet. Log your first workout above.</p>';
      return;
    }
    historyDiv.innerHTML = log.map(e => `
      <div class="history-entry">
        <div>
          <span class="history-date">${formatDate(e.timestamp)}</span>
          <span style="color:var(--text); margin-left:0.5rem">${e.exercise}</span>
        </div>
        <div>
          <span class="history-weight">${e.weight}kg</span>
          <span class="history-reps">&times; ${e.reps} &times; ${e.sets}sets</span>
          <button class="secondary" onclick="deleteEntry(${e.id}); updateHistory(); updateChart();" style="margin-left:0.5rem; padding:0.2rem 0.5rem; font-size:0.7rem;">&times;</button>
        </div>
      </div>
    `).join('');
    return;
  }

  const entries = getExerciseHistory(exercise);
  if (!entries.length) {
    historyDiv.innerHTML = '<p style="color:var(--text-dim)">No entries for this exercise yet.</p>';
    return;
  }

  historyDiv.innerHTML = entries.map(e => `
    <div class="history-entry">
      <div>
        <span class="history-date">${formatDate(e.timestamp)}</span>
      </div>
      <div>
        <span class="history-weight">${e.weight}kg</span>
        <span class="history-reps">&times; ${e.reps} &times; ${e.sets}sets</span>
        ${e.notes ? `<span style="color:var(--text-dim); margin-left:0.5rem; font-size:0.75rem">${e.notes}</span>` : ''}
        <button class="secondary" onclick="deleteEntry(${e.id}); updateHistory(); updateChart();" style="margin-left:0.5rem; padding:0.2rem 0.5rem; font-size:0.7rem;">&times;</button>
      </div>
    </div>
  `).join('');
}

function updateChart() {
  const canvas = document.getElementById('progress-chart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const exercise = document.getElementById('exercise-select').value;

  // Set actual canvas size
  const rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = rect.width - 32;
  canvas.height = rect.height - 32;

  const W = canvas.width;
  const H = canvas.height;

  ctx.clearRect(0, 0, W, H);

  if (!exercise) {
    ctx.fillStyle = '#888';
    ctx.font = '14px monospace';
    ctx.textAlign = 'center';
    ctx.fillText('Select an exercise to see progress chart', W / 2, H / 2);
    return;
  }

  const entries = getExerciseHistory(exercise);
  if (entries.length < 2) {
    ctx.fillStyle = '#888';
    ctx.font = '14px monospace';
    ctx.textAlign = 'center';
    ctx.fillText('Need 2+ entries to show chart', W / 2, H / 2);
    return;
  }

  const mode = localStorage.getItem('chart-mode') || 'weight';
  const values = entries.map(e => {
    if (mode === 'volume') return e.weight * e.reps * e.sets;
    if (mode === '1rm') return e.weight * (1 + e.reps / 30);
    return e.weight;
  });
  const yUnit = mode === 'volume' ? 'kg·reps' : 'kg';
  const yDecimals = mode === 'volume' ? 0 : 1;

  const minW = Math.min(...values) - (mode === 'volume' ? 10 : 2);
  const maxW = Math.max(...values) + (mode === 'volume' ? 10 : 2);
  const rangeW = maxW - minW || 1;

  const padL = mode === 'volume' ? 70 : 50;
  const padR = 20, padT = 20, padB = 40;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;

  // Grid lines
  ctx.strokeStyle = '#2a2a2a';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = padT + (plotH * i / 4);
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(W - padR, y);
    ctx.stroke();

    const val = (maxW - (rangeW * i / 4)).toFixed(yDecimals);
    ctx.fillStyle = '#888';
    ctx.font = '10px monospace';
    ctx.textAlign = 'right';
    ctx.fillText(val + yUnit, padL - 5, y + 4);
  }

  // Plot line
  ctx.strokeStyle = '#c9a227';
  ctx.lineWidth = 2;
  ctx.beginPath();
  entries.forEach((e, i) => {
    const x = padL + (i / (entries.length - 1)) * plotW;
    const y = padT + plotH - ((values[i] - minW) / rangeW) * plotH;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Plot dots
  entries.forEach((e, i) => {
    const x = padL + (i / (entries.length - 1)) * plotW;
    const y = padT + plotH - ((values[i] - minW) / rangeW) * plotH;
    ctx.fillStyle = '#c9a227';
    ctx.beginPath();
    ctx.arc(x, y, 4, 0, Math.PI * 2);
    ctx.fill();
  });

  // Date labels
  ctx.fillStyle = '#888';
  ctx.font = '10px monospace';
  ctx.textAlign = 'center';
  const labelCount = Math.min(entries.length, 6);
  for (let i = 0; i < labelCount; i++) {
    const idx = Math.round(i * (entries.length - 1) / (labelCount - 1));
    const x = padL + (idx / (entries.length - 1)) * plotW;
    ctx.fillText(formatDate(entries[idx].timestamp), x, H - 10);
  }
}

// Make functions globally available
window.deleteEntry = deleteEntry;
window.updateHistory = updateHistory;
window.updateChart = updateChart;
window.renderWeeklyVolume = renderWeeklyVolume;

document.addEventListener('DOMContentLoaded', initTracker);
