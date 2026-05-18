function loadRecommendation() {
  const loading = document.getElementById('rec-loading');
  const errorDiv = document.getElementById('rec-error');
  const content  = document.getElementById('rec-content');
  const btn      = document.getElementById('rec-refresh-btn');

  loading.style.display = 'flex';
  errorDiv.style.display = 'none';
  content.style.display  = 'none';
  if (btn) btn.disabled = true;

  fetch('/api/recommendation')
    .then(r => r.json())
    .then(data => {
      loading.style.display = 'none';
      if (btn) btn.disabled = false;

      if (data.success) {
        content.innerHTML = marked.parse(data.recommendation);
        content.style.display = 'block';
      } else {
        errorDiv.textContent = 'Error generating plan: ' + (data.error || 'Unknown error');
        errorDiv.style.display = 'block';
      }
    })
    .catch(err => {
      loading.style.display = 'none';
      if (btn) btn.disabled = false;
      errorDiv.textContent = 'Network error: ' + err.message;
      errorDiv.style.display = 'block';
    });
}

function saveNotes() {
  const text = document.getElementById('notes-textarea').value;
  const status = document.getElementById('notes-status');
  fetch('/api/notes', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({notes: text})
  })
  .then(r => r.json())
  .then(() => {
    status.textContent = 'Saved!';
    setTimeout(() => status.textContent = '', 3000);
  });
}

function loadNotes() {
  fetch('/api/notes')
    .then(r => r.json())
    .then(data => {
      document.getElementById('notes-textarea').value = data.notes || '';
    });
}

// Auto-load on page open
document.addEventListener('DOMContentLoaded', () => {
  loadRecommendation();
  loadNotes();
});
