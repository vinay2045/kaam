/* ═══════════════════════════════════════════════
   KAAM — analytics.js
   Chart.js initialization, period switching
═══════════════════════════════════════════════ */

let weeklyOrdersChart = null;
let weeklyRevenueChart = null;

const CHART_COLORS = {
  saffron: '#E0A11B',
  saffronSoft: 'rgba(224,161,27,0.18)',
  ink: '#16110F',
  paper: '#F6F0E6',
  stone: '#D7C9B6',
  leaf: '#5C6F42',
  leafSoft: 'rgba(92,111,66,0.2)',
  clay: '#B85C38',
};

const CHART_DEFAULTS = {
  font: { family: "'IBM Plex Mono', monospace" },
  color: '#7A6857',
};

// ─── PERIODIC TREND CHARTS (Line Area) ───
function initWeeklyCharts() {
  const ordersCanvas = document.getElementById('weeklyOrdersChart');
  const revenueCanvas = document.getElementById('weeklyRevenueChart');
  if (!ordersCanvas || !revenueCanvas) return;

  const labels = window.DAILY_ORDERS?.map(d => d.day) || [];
  const orderCounts = window.DAILY_ORDERS?.map(d => d.count) || [];
  const revAmounts = window.DAILY_REVENUE?.map(d => d.amount) || [];

  const commonOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'index',
      intersect: false,
    },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: CHART_COLORS.ink,
        titleFont: { family: "'Instrument Sans', sans-serif", size: 12, weight: 600 },
        bodyFont: { family: "'IBM Plex Mono', monospace", size: 12 },
        padding: 12,
        cornerRadius: 8,
        displayColors: false,
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { 
          font: { family: "'IBM Plex Mono', monospace", size: 10 }, 
          color: '#7A6857',
          maxRotation: 0,
          maxTicksLimit: 6,
          autoSkip: true
        },
        border: { display: false },
      },
      y: {
        grid: { color: 'rgba(215,201,182,0.3)', drawBorder: false, borderDash: [4, 4] },
        ticks: { 
          font: { family: "'IBM Plex Mono', monospace", size: 10 }, 
          color: '#7A6857', 
          maxTicksLimit: 5,
          padding: 8
        },
        border: { display: false },
        beginAtZero: true,
      }
    }
  };

  // Create Gradients
  const ctxOrders = ordersCanvas.getContext('2d');
  const gradientOrders = ctxOrders.createLinearGradient(0, 0, 0, 200);
  gradientOrders.addColorStop(0, 'rgba(224,161,27,0.3)');
  gradientOrders.addColorStop(1, 'rgba(224,161,27,0.0)');

  const ctxRev = revenueCanvas.getContext('2d');
  const gradientRev = ctxRev.createLinearGradient(0, 0, 0, 200);
  gradientRev.addColorStop(0, 'rgba(92,111,66,0.3)');
  gradientRev.addColorStop(1, 'rgba(92,111,66,0.0)');

  weeklyOrdersChart = new Chart(ordersCanvas, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        data: orderCounts,
        borderColor: CHART_COLORS.saffron,
        backgroundColor: gradientOrders,
        borderWidth: 2.5,
        fill: true,
        tension: 0.4,
        pointRadius: 0,
        pointHoverRadius: 6,
        pointBackgroundColor: CHART_COLORS.saffron,
      }]
    },
    options: {
      ...commonOptions,
      plugins: {
        ...commonOptions.plugins,
        tooltip: { ...commonOptions.plugins.tooltip, callbacks: { label: ctx => ` ${ctx.raw} orders` } }
      }
    }
  });

  weeklyRevenueChart = new Chart(revenueCanvas, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        data: revAmounts,
        borderColor: CHART_COLORS.leaf,
        backgroundColor: gradientRev,
        borderWidth: 2.5,
        fill: true,
        tension: 0.4,
        pointRadius: 0,
        pointHoverRadius: 6,
        pointBackgroundColor: CHART_COLORS.leaf,
      }]
    },
    options: {
      ...commonOptions,
      plugins: {
        ...commonOptions.plugins,
        tooltip: {
          ...commonOptions.plugins.tooltip,
          callbacks: {
            label: ctx => ` ₹${formatIndian(ctx.raw)}`
          }
        }
      }
    }
  });
}

// ─── CATEGORY BARS (CSS, not Chart.js) ───
function renderCategoryBars() {
  const container = document.getElementById('cat-bar-list');
  if (!container) return;
  const data = window.TOP_CATEGORIES || [];
  const max = data[0]?.count || 1;

  container.innerHTML = data.slice(0, 6).map(cat => {
    const pct = Math.round((cat.count / max) * 100);
    const label = cat.subcategory ? `${cat.category} / ${cat.subcategory}` : cat.category;
    return `
      <div class="cat-bar-row">
        <div class="cat-bar-label">
          <span>${label}</span>
          <span class="cat-bar-pct">${cat.count} orders (${cat.pct}%)</span>
        </div>
        <div class="cat-bar-track">
          <div class="cat-bar-fill" style="width:0%" data-target="${pct}"></div>
        </div>
        <div class="cat-bar-meta">₹${formatIndian(cat.revenue)} revenue</div>
      </div>
    `;
  }).join('');

  // Animate bars
  requestAnimationFrame(() => {
    setTimeout(() => {
      container.querySelectorAll('.cat-bar-fill').forEach(bar => {
        bar.style.transition = 'width 0.8s cubic-bezier(0.4,0,0.2,1)';
        bar.style.width = bar.dataset.target + '%';
      });
    }, 100);
  });
}

// ─── STAR BAR ANIMATION ───
function renderStarBars() {
  const bars = document.querySelectorAll('.star-row-fill[data-pct]');
  setTimeout(() => {
    bars.forEach(bar => {
      bar.style.transition = 'width 0.6s cubic-bezier(0.4,0,0.2,1)';
      bar.style.width = (bar.dataset.pct || '0') + '%';
    });
  }, 200);
}

// ─── PAYMENT BAR ANIMATION ───
function renderPaymentBars() {
  const bars = document.querySelectorAll('.payment-bar-fill[data-pct]');
  setTimeout(() => {
    bars.forEach(bar => {
      bar.style.transition = 'width 0.6s cubic-bezier(0.4,0,0.2,1)';
      bar.style.width = (bar.dataset.pct || '0') + '%';
    });
  }, 300);
}

// ─── PERIOD SWITCHER ───
function initPeriodSelector() {
  document.querySelectorAll('.period-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelector('.period-btn.active')?.classList.remove('active');
      btn.classList.add('active');
      const period = btn.dataset.period;
      window.location.href = `?period=${period}`;
    });
  });
}

// ─── REAL-TIME ANALYTICS POLLING ───
function pollAnalyticsPage() {
  fetch('/api/analytics/realtime/', {
    headers: { 'X-Requested-With': 'XMLHttpRequest' }
  })
    .then(r => r.json())
    .then(data => {
      const metricMap = {
        '#metric-packed': data.packed,
        '#metric-shipped': data.shipped,
        '#metric-out': data.out_for_delivery,
        '#metric-delivered': data.delivered,
      };
      Object.entries(metricMap).forEach(([sel, val]) => {
        const el = document.querySelector(sel);
        if (el) animateCounter(el, val);
      });
      const lu = document.getElementById('last-updated');
      if (lu) lu.textContent = 'Updated just now';
    }).catch(() => {});
}

// ─── INIT ───
document.addEventListener('DOMContentLoaded', () => {
  initWeeklyCharts();
  renderCategoryBars();
  renderStarBars();
  renderPaymentBars();
  initPeriodSelector();
  setInterval(pollAnalyticsPage, 30000);
});
