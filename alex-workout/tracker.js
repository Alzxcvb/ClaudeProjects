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
  log.push({ ...entry, id: Date.now(), timestamp: new Date().toISOString() });
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
  });

  // Clear all data
  clearBtn.addEventListener('click', () => {
    if (confirm('Delete ALL workout data? This cannot be undone.')) {
      localStorage.removeItem(STORAGE_KEY);
      updateHistory();
      updateChart();
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
      };
      reader.readAsText(file);
    });
  }

  // Initial render
  updateHistory();
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

  const weights = entries.map(e => e.weight);
  const minW = Math.min(...weights) - 2;
  const maxW = Math.max(...weights) + 2;
  const rangeW = maxW - minW || 1;

  const padL = 50, padR = 20, padT = 20, padB = 40;
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

    const val = (maxW - (rangeW * i / 4)).toFixed(1);
    ctx.fillStyle = '#888';
    ctx.font = '10px monospace';
    ctx.textAlign = 'right';
    ctx.fillText(val + 'kg', padL - 5, y + 4);
  }

  // Plot line
  ctx.strokeStyle = '#c9a227';
  ctx.lineWidth = 2;
  ctx.beginPath();
  entries.forEach((e, i) => {
    const x = padL + (i / (entries.length - 1)) * plotW;
    const y = padT + plotH - ((e.weight - minW) / rangeW) * plotH;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Plot dots
  entries.forEach((e, i) => {
    const x = padL + (i / (entries.length - 1)) * plotW;
    const y = padT + plotH - ((e.weight - minW) / rangeW) * plotH;
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

document.addEventListener('DOMContentLoaded', initTracker);
