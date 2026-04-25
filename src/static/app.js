/* Personal Finance Tracker — frontend */

const PAGE_SIZE = 20;
let txnOffset = 0;
let txnTotal = 0;
let categoryChart = null;
let monthlyChart = null;

const CATEGORY_COLORS = [
  '#3b82f6','#ef4444','#22c55e','#a855f7','#f97316',
  '#06b6d4','#eab308','#ec4899','#14b8a6','#8b5cf6',
];

// ── Boot ────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('accounts-list')) {
    loadAll();
  }
});

function loadAll() {
  loadAccounts();
  loadTransactions();
  loadSpendingSummary();
}

// ── Toast ────────────────────────────────────────────────────────────────────

function showToast(message, type = 'success') {
  const container = document.getElementById('toast-container');
  const id = 'toast-' + Date.now();
  const icons = { success: 'bi-check-circle-fill', danger: 'bi-exclamation-circle-fill', info: 'bi-info-circle-fill' };
  container.insertAdjacentHTML('beforeend', `
    <div id="${id}" class="toast align-items-center text-bg-${type} border-0 show" role="alert">
      <div class="d-flex">
        <div class="toast-body"><i class="bi ${icons[type] || icons.info} me-2"></i>${message}</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
      </div>
    </div>`);
  setTimeout(() => document.getElementById(id)?.remove(), 4000);
}

// ── Plaid Link ───────────────────────────────────────────────────────────────

async function connectBank() {
  try {
    const res = await fetch('/api/create-link-token', { method: 'POST' });
    const data = await res.json();
    if (!res.ok) { showToast(data.error || 'Failed to start Plaid Link', 'danger'); return; }

    const handler = Plaid.create({
      token: data.link_token,
      onSuccess: async (publicToken, metadata) => {
        showToast('Linking account…', 'info');
        const resp = await fetch('/api/exchange-token', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ public_token: publicToken, metadata }),
        });
        const result = await resp.json();
        if (!resp.ok) {
          showToast(result.error || 'Failed to link account', 'danger');
          return;
        }
        showToast(`${result.institution} connected — ${result.transactions_added} transactions imported`);
        setTimeout(() => location.reload(), 1500);
      },
      onExit: (err) => {
        if (err) showToast(err.display_message || 'Plaid Link exited with an error', 'danger');
      },
    });
    handler.open();
  } catch (e) {
    showToast('Could not open Plaid Link: ' + e.message, 'danger');
  }
}

// ── Sync ─────────────────────────────────────────────────────────────────────

async function syncTransactions() {
  const btn = document.getElementById('sync-btn');
  const icon = btn?.querySelector('i');
  if (icon) icon.classList.add('spin');
  btn?.setAttribute('disabled', true);

  try {
    const res = await fetch('/api/sync', { method: 'POST' });
    const data = await res.json();
    if (!res.ok) { showToast(data.error || 'Sync failed', 'danger'); return; }

    const msg = data.added > 0
      ? `Sync complete — ${data.added} new transaction${data.added !== 1 ? 's' : ''}`
      : 'Already up to date';
    showToast(msg);

    document.getElementById('last-synced').textContent =
      'Synced ' + new Date().toLocaleTimeString();

    loadAll();
  } catch (e) {
    showToast('Sync error: ' + e.message, 'danger');
  } finally {
    if (icon) icon.classList.remove('spin');
    btn?.removeAttribute('disabled');
  }
}

// ── Accounts ─────────────────────────────────────────────────────────────────

async function loadAccounts() {
  const list = document.getElementById('accounts-list');
  if (!list) return;

  const res = await fetch('/api/accounts');
  const accounts = await res.json();

  if (!accounts.length) {
    list.innerHTML = '<div class="list-group-item text-muted small">No accounts.</div>';
    return;
  }

  const totalBalance = accounts.reduce((s, a) => s + (a.current_balance || 0), 0);
  document.getElementById('total-balance').textContent = fmt(totalBalance);
  document.getElementById('accounts-count').textContent =
    `${accounts.length} account${accounts.length !== 1 ? 's' : ''}`;

  const institutions = [...new Set(accounts.map(a => a.institution))];
  document.getElementById('institutions-count').textContent = institutions.length;

  list.innerHTML = accounts.map(a => `
    <div class="list-group-item list-group-item-action account-item px-3 py-2">
      <div class="d-flex justify-content-between align-items-start">
        <div>
          <div class="fw-semibold">${esc(a.name)}</div>
          <div class="text-muted" style="font-size:0.75rem">${esc(a.institution)}</div>
        </div>
        <div class="text-end">
          <div class="account-balance">${fmt(a.current_balance)} <span style="font-size:0.7rem;font-weight:400">${a.currency}</span></div>
          <span class="account-type-badge">${esc(a.subtype || a.type || '')}</span>
        </div>
      </div>
    </div>`).join('');

  // Populate remove modal
  const removeList = document.getElementById('remove-institutions-list');
  if (removeList) {
    const itemMap = {};
    accounts.forEach(a => { itemMap[a.item_id] = a.institution; });
    removeList.innerHTML = Object.entries(itemMap).map(([id, name]) => `
      <button class="list-group-item list-group-item-action list-group-item-danger"
              onclick="removeInstitution(${id}, '${esc(name)}')">
        <i class="bi bi-trash3 me-2"></i>${esc(name)}
      </button>`).join('');
    document.getElementById('remove-account-btn').style.display = '';
  }
}

async function removeInstitution(itemId, name) {
  if (!confirm(`Remove ${name} and all its data?`)) return;
  const res = await fetch(`/api/items/${itemId}`, { method: 'DELETE' });
  if (res.ok) {
    showToast(`${name} removed`);
    setTimeout(() => location.reload(), 1000);
  } else {
    showToast('Failed to remove institution', 'danger');
  }
}

function showRemoveModal() {
  new bootstrap.Modal(document.getElementById('removeModal')).show();
}

// ── Transactions ─────────────────────────────────────────────────────────────

async function loadTransactions() {
  const body = document.getElementById('txn-body');
  if (!body) return;

  const days = document.getElementById('txn-days-filter')?.value;
  const params = new URLSearchParams({ limit: PAGE_SIZE, offset: txnOffset });
  if (days) params.set('days', days);

  const res = await fetch('/api/transactions?' + params);
  const data = await res.json();
  txnTotal = data.total;

  document.getElementById('txn-count').textContent = data.total;

  if (!data.transactions.length) {
    body.innerHTML = '<tr><td colspan="5" class="text-center py-4 text-muted">No transactions found.</td></tr>';
    updatePager();
    return;
  }

  body.innerHTML = data.transactions.map(t => {
    const isDebit = t.amount > 0;
    const amtClass = isDebit ? 'amount-debit' : 'amount-credit';
    const amtPrefix = isDebit ? '' : '+';
    const pending = t.pending ? '<span class="pending-badge ms-1">pending</span>' : '';
    const cat = t.category ? `<span class="category-pill">${esc(t.category)}</span>` : '—';
    return `<tr>
      <td class="text-nowrap">${t.date}</td>
      <td>${esc(t.merchant_name || t.name)}${pending}</td>
      <td>${cat}</td>
      <td class="text-end text-nowrap ${amtClass}">${amtPrefix}${fmt(Math.abs(t.amount))}</td>
      <td class="text-muted text-nowrap" style="font-size:0.78rem">${esc(t.account_name)}</td>
    </tr>`;
  }).join('');

  updatePager();
}

function updatePager() {
  const start = txnOffset + 1;
  const end = Math.min(txnOffset + PAGE_SIZE, txnTotal);
  const showing = document.getElementById('txn-showing');
  if (showing) showing.textContent = txnTotal ? `${start}–${end} of ${txnTotal}` : '';

  const prev = document.getElementById('txn-prev');
  const next = document.getElementById('txn-next');
  if (prev) prev.disabled = txnOffset === 0;
  if (next) next.disabled = txnOffset + PAGE_SIZE >= txnTotal;
}

function changeTxnPage(dir) {
  txnOffset = Math.max(0, txnOffset + dir * PAGE_SIZE);
  loadTransactions();
}

// ── Spending summary ──────────────────────────────────────────────────────────

async function loadSpendingSummary() {
  const days = document.getElementById('category-days')?.value || 30;
  const res = await fetch(`/api/spending-summary?days=${days}`);
  const data = await res.json();

  document.getElementById('monthly-spending').textContent =
    fmt(data.categories.reduce((s, c) => s + c.total, 0));

  renderCategoryChart(data.categories);
  renderMonthlyChart(data.monthly);
}

function renderCategoryChart(categories) {
  const canvas = document.getElementById('categoryChart');
  const empty = document.getElementById('category-empty');
  if (!canvas) return;

  if (!categories.length) {
    canvas.style.display = 'none';
    empty?.classList.remove('d-none');
    return;
  }

  canvas.style.display = '';
  empty?.classList.add('d-none');

  const top = categories.slice(0, 10);
  if (categoryChart) categoryChart.destroy();
  categoryChart = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels: top.map(c => c.category),
      datasets: [{
        data: top.map(c => c.total),
        backgroundColor: CATEGORY_COLORS.slice(0, top.length),
        borderWidth: 2,
        borderColor: '#fff',
      }],
    },
    options: {
      plugins: {
        legend: { position: 'right', labels: { boxWidth: 12, font: { size: 11 } } },
        tooltip: {
          callbacks: {
            label: ctx => ` ${fmt(ctx.parsed)}`,
          },
        },
      },
      cutout: '62%',
      responsive: true,
      maintainAspectRatio: true,
    },
  });
}

function renderMonthlyChart(monthly) {
  const canvas = document.getElementById('monthlyChart');
  const empty = document.getElementById('monthly-empty');
  if (!canvas) return;

  if (!monthly.length) {
    canvas.style.display = 'none';
    empty?.classList.remove('d-none');
    return;
  }

  canvas.style.display = '';
  empty?.classList.add('d-none');

  const labels = monthly.map(m => {
    const [y, mo] = m.month.split('-');
    return new Date(y, mo - 1).toLocaleString('default', { month: 'short', year: '2-digit' });
  });

  if (monthlyChart) monthlyChart.destroy();
  monthlyChart = new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Spending',
        data: monthly.map(m => m.total),
        backgroundColor: '#3b82f6cc',
        borderColor: '#3b82f6',
        borderWidth: 1,
        borderRadius: 4,
      }],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        y: {
          beginAtZero: true,
          ticks: { callback: v => '$' + v.toLocaleString() },
          grid: { color: '#f3f4f6' },
        },
        x: { grid: { display: false } },
      },
      responsive: true,
      maintainAspectRatio: true,
    },
  });
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(value) {
  if (value == null) return '—';
  return '$' + Math.abs(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function esc(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
