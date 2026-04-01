/* ═══════════════════════════════════════════════
   KAAM — utils.js
   Toast, getCookie, animateCounter, copy
═══════════════════════════════════════════════ */

function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

function showToast(message, type = 'info') {
  // Toast message feature removed
}

function animateCounter(el, targetValue, prefix = '', isCurrency = false) {
  if (!el) return;
  const startValue = parseFloat(el.dataset.current || 0) || 0;
  const duration = 700;
  const startTime = performance.now();

  function update(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    const current = Math.round(startValue + (targetValue - startValue) * eased);

    if (isCurrency) {
      el.textContent = prefix + formatIndian(current);
    } else {
      el.textContent = prefix + current;
    }
    if (progress < 1) requestAnimationFrame(update);
    else el.dataset.current = targetValue;
  }
  requestAnimationFrame(update);
}

function formatIndian(n) {
  n = Math.round(n);
  const isNeg = n < 0;
  let s = Math.abs(n).toString();
  if (s.length <= 3) return (isNeg ? '-' : '') + s;
  let result = s.slice(-3);
  s = s.slice(0, -3);
  while (s.length > 0) {
    result = s.slice(-2) + ',' + result;
    s = s.slice(0, -2);
  }
  return (isNeg ? '-' : '') + result;
}

function copyToClipboard(text, btn) {
  navigator.clipboard.writeText(text).then(() => {
    if (btn) {
      const orig = btn.textContent;
      btn.textContent = 'Copied!';
      btn.classList.add('copied');
      setTimeout(() => {
        btn.textContent = orig;
        btn.classList.remove('copied');
      }, 2000);
    }
  }).catch(() => {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    if (btn) {
      btn.textContent = 'Copied!';
      setTimeout(() => btn.textContent = 'Copy', 2000);
    }
  });
}

// Auto-dismiss Django success alerts after 2 seconds
document.addEventListener('DOMContentLoaded', () => {
  const alerts = document.querySelectorAll('.messages-list .alert-success, .messages-list .alert-info');
  alerts.forEach(alert => {
    setTimeout(() => {
      alert.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
      alert.style.opacity = '0';
      alert.style.transform = 'translateY(-10px)';
      setTimeout(() => alert.remove(), 400);
    }, 2000);
  });
});

/* ─── THEME TOGGLE ─── */
function syncThemeButtons() {
  const theme = document.documentElement.getAttribute('data-theme');
  const btns = document.querySelectorAll('.theme-toggle');
  btns.forEach(btn => {
    if (theme === 'dark') {
      btn.classList.add('theme-toggle--toggled');
    } else {
      btn.classList.remove('theme-toggle--toggled');
    }
  });
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
  syncThemeButtons();
}

document.addEventListener('DOMContentLoaded', syncThemeButtons);

/* ─── CUSTOM MODALS ─── */
function kaamAlert(title, message) {
  return new Promise((resolve) => {
    const overlay = document.getElementById('kaam-modal-overlay');
    const cardTitle = document.getElementById('kaam-modal-title');
    const cardBody = document.getElementById('kaam-modal-body');
    const footer = document.getElementById('kaam-modal-footer');

    if (!overlay || !footer) {
      alert(message);
      resolve();
      return;
    }

    cardTitle.textContent = title;
    cardBody.textContent = message;
    footer.innerHTML = `<button class="btn btn-primary btn-sm" id="kaam-modal-ok" style="min-width: 80px">OK</button>`;

    overlay.classList.add('active');

    document.getElementById('kaam-modal-ok').onclick = () => {
      overlay.classList.remove('active');
      resolve();
    };
  });
}

function kaamConfirm(title, message, confirmBtnText = 'Confirm', variant = 'danger') {
  return new Promise((resolve) => {
    const overlay = document.getElementById('kaam-modal-overlay');
    const cardTitle = document.getElementById('kaam-modal-title');
    const cardBody = document.getElementById('kaam-modal-body');
    const footer = document.getElementById('kaam-modal-footer');

    if (!overlay || !footer) {
      resolve(confirm(message));
      return;
    }

    cardTitle.textContent = title;
    cardBody.textContent = message;
    
    footer.innerHTML = `
      <button class="btn btn-ghost btn-sm" id="kaam-modal-cancel">Cancel</button>
      <button class="btn btn-${variant} btn-sm" id="kaam-modal-confirm" style="min-width: 100px">${confirmBtnText}</button>
    `;

    overlay.classList.add('active');

    document.getElementById('kaam-modal-cancel').onclick = () => {
      overlay.classList.remove('active');
      resolve(false);
    };

    document.getElementById('kaam-modal-confirm').onclick = () => {
      overlay.classList.remove('active');
      resolve(true);
    };
  });
}

function kaamPrompt(title, message, placeholder = '') {
  return new Promise((resolve) => {
    const overlay = document.getElementById('kaam-modal-overlay');
    const cardTitle = document.getElementById('kaam-modal-title');
    const cardBody = document.getElementById('kaam-modal-body');
    const footer = document.getElementById('kaam-modal-footer');

    if (!overlay || !footer) {
      resolve(prompt(message));
      return;
    }

    cardTitle.textContent = title;
    cardBody.innerHTML = `
      <p style="margin-bottom: 12px">${message}</p>
      <input type="text" id="kaam-modal-input" class="input-field" placeholder="${placeholder}" autocomplete="off">
    `;
    
    footer.innerHTML = `
      <button class="btn btn-ghost btn-sm" id="kaam-modal-cancel">Cancel</button>
      <button class="btn btn-primary btn-sm" id="kaam-modal-confirm" style="min-width: 90px">Submit</button>
    `;

    overlay.classList.add('active');
    const input = document.getElementById('kaam-modal-input');
    input.focus();

    document.getElementById('kaam-modal-cancel').onclick = () => {
      overlay.classList.remove('active');
      resolve(null);
    };

    document.getElementById('kaam-modal-confirm').onclick = () => {
      const val = input.value.trim();
      overlay.classList.remove('active');
      resolve(val);
    };

    input.onkeyup = (e) => {
      if (e.key === 'Enter') document.getElementById('kaam-modal-confirm').click();
    };
  });
}
/* ─── GENERIC MODAL UTILS ─── */
function openModal(id) {
  const m = document.getElementById(id);
  if (!m) return;
  m.style.display = 'flex';
}

function closeModal(id) {
  const m = document.getElementById(id);
  if (!m) return;
  m.style.display = 'none';
}
