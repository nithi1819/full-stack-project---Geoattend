// CampusHub — Frontend JavaScript Utilities

async function api(url, method = 'GET', body = null) {
  try {
    const opts = { method, headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin' };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(url, opts);
    if (res.status === 401) { window.location.href = '/login'; return null; }
    const ct = res.headers.get('content-type') || '';
    if (ct.includes('text/csv') || ct.includes('application/pdf') || ct.includes('application/vnd')) {
      return await res.blob();
    }
    const data = await res.json();
    if (!res.ok) return { error: data.error || data.message || 'Request failed' };
    return data;
  } catch (e) {
    console.error('API error:', e);
    return { error: 'Network error' };
  }
}

function showModal(id) {
  document.getElementById(id).classList.add('open');
}

function hideModal(id) {
  document.getElementById(id).classList.remove('open');
}

// Close modals on backdrop click
document.addEventListener('click', function(e) {
  if (e.target.classList.contains('modal')) {
    e.target.classList.remove('open');
  }
});

// Close sidebar on mobile when clicking outside
document.addEventListener('click', function(e) {
  const sidebar = document.getElementById('sidebar');
  if (sidebar && sidebar.classList.contains('open') && !sidebar.contains(e.target) && !e.target.classList.contains('menu-toggle')) {
    sidebar.classList.remove('open');
  }
});
