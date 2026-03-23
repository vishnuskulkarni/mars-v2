const API_BASE = '/api';

export async function submitResearch(question, literatureFiles, dataFiles) {
  const formData = new FormData();
  formData.append('research_question', question);
  literatureFiles.forEach(f => formData.append('literature_files', f));
  dataFiles.forEach(f => formData.append('data_files', f));

  const res = await fetch(`${API_BASE}/submit`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Submit failed');
  }
  return res.json();
}

export async function fetchReport(sessionId) {
  const res = await fetch(`${API_BASE}/report/${sessionId}`);
  if (!res.ok) throw new Error('Failed to fetch report');
  return res.json();
}

export async function fetchSessionState(sessionId) {
  const res = await fetch(`${API_BASE}/state/${sessionId}`);
  if (!res.ok) throw new Error('Failed to fetch session state');
  return res.json();
}

export async function fetchSessions() {
  const res = await fetch(`${API_BASE}/sessions`);
  if (!res.ok) throw new Error('Failed to fetch sessions');
  return res.json();
}

export function getExportUrl(sessionId) {
  return `${API_BASE}/report/${sessionId}/export`;
}
