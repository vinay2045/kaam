/* ═══════════════════════════════════════════════
   KAAM — dashboard.js
   Polling, order management, notifications
═══════════════════════════════════════════════ */

const POLL_INTERVAL = 30000;
let lastNewOrdersCount = parseInt(document.getElementById('cached-new-orders')?.value || '0');
let pollTimer = null;
let isFirstPoll = true;

// ─── REAL-TIME POLLING ───
function pollAnalytics() {
  fetch('/api/analytics/realtime/', {
    headers: { 'X-Requested-With': 'XMLHttpRequest' }
  })
    .then(r => r.json())
    .then(data => {
      // Update stat cards
      const revenueEl = document.getElementById('monthly-revenue');
      const ordersEl  = document.getElementById('monthly-orders');
      if (revenueEl) animateCounter(revenueEl, data.monthly_revenue, '₹', true);
      if (ordersEl)  animateCounter(ordersEl,  data.monthly_orders);

      // Update delivery strip
      updateDeliveryStrip(data);

      // Alert for new orders
      if (!isFirstPoll && data.new_orders_count > lastNewOrdersCount) {
        showToast('🔔 New order received!', 'success');
        // Optional: you can add an audio beep here
      }

      // Update all order tab counts dynamically
      if (data.tabs) {
        document.getElementById('tab-count-new') && (document.getElementById('tab-count-new').textContent = data.tabs.new);
        document.getElementById('tab-count-pending') && (document.getElementById('tab-count-pending').textContent = data.tabs.pending);
        document.getElementById('tab-count-completed') && (document.getElementById('tab-count-completed').textContent = data.tabs.completed);
        document.getElementById('tab-count-returns') && (document.getElementById('tab-count-returns').textContent = data.tabs.returns);
        document.getElementById('tab-count-all') && (document.getElementById('tab-count-all').textContent = data.tabs.all);
      } else {
        // Fallback for just new orders
        const newTabCount = document.getElementById('tab-count-new');
        if (newTabCount) newTabCount.textContent = data.new_orders_count;
      }

      // Update notifications dynamically
      if (data.notifications !== undefined) {
        updateNotifications(data.notifications, data.unread_count);
      }

      lastNewOrdersCount = data.new_orders_count;
      isFirstPoll = false;

      // last updated
      const lu = document.getElementById('last-updated');
      if (lu) lu.textContent = 'Updated just now';
    })
    .catch(() => {});
}

function updateNotifications(notifs, unreadCount) {
  // Update bell badge
  const bell = document.getElementById('notif-bell-btn');
  let badge = document.getElementById('notif-badge');
  if (unreadCount > 0) {
    if (!badge && bell) {
      badge = document.createElement('span');
      badge.className = 'notif-count';
      badge.id = 'notif-badge';
      bell.appendChild(badge);
    }
    if (badge) {
      badge.textContent = unreadCount;
      badge.style.display = 'flex';
    }
  } else if (badge) {
    badge.style.display = 'none';
  }

  // Update dropdown DOM
  const notifDrop = document.getElementById('notif-dropdown');
  if (notifDrop) {
    let html = `<div class="notif-dropdown-header">
      <span>Notifications</span>
      <button onclick="toggleNotifDropdown()" style="background:none;border:none;cursor:pointer;font-size:12px;color:var(--kaam-stone-dark)">Close</button>
    </div>`;

    if (notifs.length > 0) {
      notifs.forEach(n => {
        html += `<div class="notif-item unread">
          ${n.message}
          <div class="notif-item-time" style="font-size:10px;margin-top:4px">Just now</div>
        </div>`;
      });
    } else {
      html += `<div class="notif-empty">No new notifications</div>`;
    }
    notifDrop.innerHTML = html;
  }
}

function updateDeliveryStrip(data) {
  const map = {
    confirmed: data.confirmed,
    packed: data.packed,
    shipped: data.shipped,
    out_for_delivery: data.out_for_delivery
  };
  Object.entries(map).forEach(([status, count]) => {
    const countEl = document.querySelector(`.dispatch-chip[data-status="${status}"] .chip-count`);
    if (countEl) countEl.textContent = count;
  });
}

// ─── CONFIRM ORDER ───
function confirmOrder(orderId, btn) {
  btn.disabled = true;
  btn.textContent = 'Confirming…';

  fetch(`/dashboard/orders/${orderId}/confirm/`, {
    method: 'POST',
    headers: {
      'X-CSRFToken': getCookie('csrftoken'),
      'X-Requested-With': 'XMLHttpRequest',
    }
  })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showToast(`Order ${orderId} confirmed!`, 'success');
        const row = document.getElementById(`order-row-${orderId}`);
        const expandRow = document.getElementById(`expand-${orderId}`);
        const mobCard = document.getElementById(`mob-card-${orderId}`);
        
        [row, expandRow, mobCard].forEach(el => {
          if (el) {
            el.style.transition = 'opacity 0.3s, transform 0.3s';
            el.style.opacity = '0';
            setTimeout(() => {
              el.remove();
              syncSelectAllOrdersState();
            }, 300);
          }
        });
        // Update all tabs immediately by polling analytics right now
        pollAnalytics();
      } else {
        showToast('Failed to confirm order.', 'error');
        btn.disabled = false;
        btn.textContent = 'Confirm Order';
      }
    })
    .catch(() => {
      showToast('Network error. Try again.', 'error');
      btn.disabled = false;
      btn.textContent = 'Confirm Order';
    });
}

// ─── UPDATE ORDER STATUS ───
function updateOrderStatus(orderId, selectEl, updateBtn) {
  const newStatus = selectEl.value;
  updateBtn.disabled = true;
  if (updateBtn.tagName !== 'SELECT') {
    updateBtn.textContent = 'Updating…';
  }

  const fd = new FormData();
  fd.append('status', newStatus);
  fd.append('csrfmiddlewaretoken', getCookie('csrftoken'));

  fetch(`/dashboard/orders/${orderId}/status/`, {
    method: 'POST',
    body: fd,
    headers: { 'X-Requested-With': 'XMLHttpRequest' },
  })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showToast(`Order updated to ${data.status_label}.`, 'success');
        if (newStatus === 'delivered') {
          const row = document.getElementById(`order-row-${orderId}`);
          const expandRow = document.getElementById(`expand-${orderId}`);
          const mobCard = document.getElementById(`mob-card-${orderId}`);
          
          [row, expandRow, mobCard].forEach(el => {
            if (el) {
              el.style.transition = 'opacity 0.3s';
              el.style.opacity = '0';
              setTimeout(() => {
                el.remove();
                syncSelectAllOrdersState();
              }, 300);
            }
          });
        }
        // Update badge in row
        const badge = document.getElementById(`status-badge-${orderId}`);
        if (badge) {
          badge.textContent = data.status_label;
          badge.className = 'badge badge-' + newStatus.replace('_', '-');
        }
        
        // Update badge in mobile card
        const mobCardNode = document.getElementById(`mob-card-${orderId}`);
        if (mobCardNode) {
          const mobBadge = mobCardNode.querySelector('.badge');
          if (mobBadge) {
            mobBadge.textContent = data.status_label;
            mobBadge.className = 'badge badge-' + newStatus.replace('_', '-');
          }
        }
        // Instantly sync background tab counts
        pollAnalytics();
        
      } else {
        showToast('Failed to update status.', 'error');
      }
      updateBtn.disabled = false;
      if (updateBtn.tagName !== 'SELECT') {
        updateBtn.textContent = 'Update';
      }
    })
    .catch(() => {
      showToast('Network error.', 'error');
      updateBtn.disabled = false;
      if (updateBtn.tagName !== 'SELECT') {
        updateBtn.textContent = 'Update';
      }
    });
}

// ─── PROCESS RETURN/EXCHANGE ───
async function processReturn(orderId, action) {
  let note = "";
  if (action === 'decline') {
    note = await kaamPrompt("Decline Return", "Reason for declining the return request:", "e.g., Damaged after delivery...");
    if (note === null) return; // User cancelled
  }

  fetch(`/dashboard/orders/${orderId}/return/update/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'X-CSRFToken': getCookie('csrftoken'),
      'X-Requested-With': 'XMLHttpRequest',
    },
    body: `action=${action}&note=${encodeURIComponent(note)}`
  })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showToast('Return status updated successfully.', 'success');
        setTimeout(() => window.location.reload(), 800);
      } else {
        showToast("Error updating return status: " + (data.error || "Unknown"), 'error');
      }
    })
    .catch(err => {
      console.error(err);
      showToast('Network error.', 'error');
    });
}

// ─── EXPAND ORDER ROW ───
let expandedRow = null;

function toggleExpand(orderId) {
  const expandRow = document.getElementById(`expand-${orderId}`);
  if (!expandRow) return;

  if (expandedRow && expandedRow !== orderId) {
    const prev = document.getElementById(`expand-${expandedRow}`);
    if (prev) prev.style.display = 'none';
    const prevMainRow = document.getElementById(`order-row-${expandedRow}`);
    if (prevMainRow) prevMainRow.classList.remove('expanded');
  }

  const isOpen = expandRow.style.display === 'table-row';
  expandRow.style.display = isOpen ? 'none' : 'table-row';

  const mainRow = document.getElementById(`order-row-${orderId}`);
  if (mainRow) mainRow.classList.toggle('expanded', !isOpen);

  expandedRow = isOpen ? null : orderId;
}

// ─── MOBILE ORDER CARD EXPAND ───
let expandedMobCard = null;

function toggleMobCard(orderId) {
  const detail = document.getElementById(`mob-detail-${orderId}`);
  const chev = document.getElementById(`chev-${orderId}`);
  if (!detail) return;

  // Close previously open card
  if (expandedMobCard && expandedMobCard !== orderId) {
    const prevDetail = document.getElementById(`mob-detail-${expandedMobCard}`);
    const prevChev = document.getElementById(`chev-${expandedMobCard}`);
    if (prevDetail) prevDetail.style.display = 'none';
    if (prevChev) prevChev.style.transform = 'rotate(0deg)';
  }

  const isOpen = detail.style.display !== 'none';
  detail.style.display = isOpen ? 'none' : 'block';
  if (chev) chev.style.transform = isOpen ? 'rotate(0deg)' : 'rotate(180deg)';
  expandedMobCard = isOpen ? null : orderId;
}

function viewOrderDetails(orderId) {
  const row = document.getElementById(`order-row-${orderId}`);
  const expand = document.getElementById(`expand-${orderId}`);
  const mobileCard = document.getElementById(`mob-card-${orderId}`);
  if (expand && row) {
    if (expand.style.display !== 'table-row') {
      toggleExpand(orderId);
    }
    row.scrollIntoView({ behavior: 'smooth', block: 'center' });
    return;
  }
  if (mobileCard) {
    const detail = document.getElementById(`mob-detail-${orderId}`);
    if (detail && detail.style.display === 'none') {
      toggleMobCard(orderId);
    }
    mobileCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

async function deleteOrder(orderId) {
  const confirmed = await kaamConfirm("Delete Order", `Are you sure you want to delete order ${orderId}? This cannot be undone.`, "Delete Order", "danger");
  if (!confirmed) return;
  fetch(`/dashboard/orders/${orderId}/delete/`, {
    method: 'POST',
    headers: {
      'X-CSRFToken': getCookie('csrftoken'),
      'X-Requested-With': 'XMLHttpRequest',
    }
  })
    .then(r => r.json())
    .then(data => {
      if (!data.success) {
        showToast(data.error || 'Failed to delete order.', 'error');
        return;
      }
      showToast(`Order ${orderId} deleted.`, 'success');
      const row = document.getElementById(`order-row-${orderId}`);
      const expandRow = document.getElementById(`expand-${orderId}`);
      const mobCard = document.getElementById(`mob-card-${orderId}`);
      [row, expandRow, mobCard].forEach(el => {
        if (el) {
          el.style.transition = 'opacity 0.25s, transform 0.25s';
          el.style.opacity = '0';
          el.style.transform = 'scale(0.98)';
          setTimeout(() => {
            el.remove();
            syncSelectAllOrdersState();
          }, 260);
        }
      });
      pollAnalytics();
    })
    .catch(() => showToast('Network error.', 'error'));
}

function getVisibleOrderCheckboxes() {
  return Array.from(document.querySelectorAll('.order-select-checkbox')).filter(el => el.offsetParent !== null);
}

function getSelectedOrderIds() {
  const ids = new Set();
  getVisibleOrderCheckboxes().forEach(el => {
    if (el.checked) ids.add(el.value);
  });
  return Array.from(ids);
}

function toggleSelectAllOrders(checked) {
  getVisibleOrderCheckboxes().forEach(el => { el.checked = checked; });
  syncSelectAllOrdersState();
}

function syncSelectAllOrdersState() {
  const toggle = document.getElementById('select-all-orders');
  if (!toggle) return;
  const boxes = getVisibleOrderCheckboxes();
  if (boxes.length === 0) {
    toggle.checked = false;
    toggle.indeterminate = false;
    return;
  }
  const selected = boxes.filter(el => el.checked).length;
  toggle.checked = selected === boxes.length;
  toggle.indeterminate = selected > 0 && selected < boxes.length;
}

async function deleteSelectedOrders() {
  const ids = getSelectedOrderIds();
  if (ids.length === 0) {
    showToast('Select at least one order.', 'error');
    return;
  }
  const confirmed = await kaamConfirm("Bulk Deletion", `Delete ${ids.length} selected order(s)? This cannot be undone.`, "Delete ALL", "danger");
  if (!confirmed) return;

  const payload = new URLSearchParams();
  ids.forEach(id => payload.append('order_ids', id));
  fetch('/dashboard/orders/bulk-delete/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'X-CSRFToken': getCookie('csrftoken'),
      'X-Requested-With': 'XMLHttpRequest',
    },
    body: payload.toString(),
  })
    .then(r => r.json())
    .then(data => {
      if (!data.success) {
        showToast(data.error || 'Failed to delete selected orders.', 'error');
        return;
      }
      ids.forEach(orderId => {
        const row = document.getElementById(`order-row-${orderId}`);
        const expandRow = document.getElementById(`expand-${orderId}`);
        const mobCard = document.getElementById(`mob-card-${orderId}`);
        [row, expandRow, mobCard].forEach(el => { if (el) el.remove(); });
      });
      syncSelectAllOrdersState();
      showToast(`${data.deleted_count || ids.length} order(s) deleted.`, 'success');
      pollAnalytics();
    })
    .catch(() => showToast('Network error.', 'error'));
}

async function deleteAllOrdersInTab() {
  const form = document.getElementById('orders-search-form');
  if (!form) return;
  const tab = form.querySelector('input[name="tab"]')?.value || 'all';
  const q = form.querySelector('input[name="q"]')?.value || '';
  const status = form.querySelector('input[name="status"]')?.value || '';
  
  const confirmed = await kaamConfirm("Clear Tab", `Delete ALL orders in "${tab}" tab for current filter? This cannot be undone.`, "Delete All", "danger");
  if (!confirmed) return;

  const payload = new URLSearchParams();
  payload.append('tab', tab);
  payload.append('q', q);
  payload.append('status', status);

  fetch('/dashboard/orders/bulk-delete/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'X-CSRFToken': getCookie('csrftoken'),
      'X-Requested-With': 'XMLHttpRequest',
    },
    body: payload.toString(),
  })
    .then(r => r.json())
    .then(data => {
      if (!data.success) {
        showToast(data.error || 'Failed to delete orders.', 'error');
        return;
      }
      showToast(`${data.deleted_count || 0} order(s) deleted.`, 'success');
      window.location.reload();
    })
    .catch(() => showToast('Network error.', 'error'));
}

// ─── DELETE PRODUCT ───
async function deleteProduct(pk, title) {
  const confirmed = await kaamConfirm("Delete Product", `Are you sure you want to delete "${title}"? This cannot be undone.`, "Delete", "danger");
  if (!confirmed) return;

  fetch(`/dashboard/products/${pk}/delete/`, {
    method: 'POST',
    headers: {
      'X-CSRFToken': getCookie('csrftoken'),
      'X-Requested-With': 'XMLHttpRequest',
    }
  })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showToast(`"${data.title}" deleted.`, 'success');
        const card = document.getElementById(`product-card-${pk}`);
        if (card) {
          card.style.transition = 'opacity 0.3s, transform 0.3s';
          card.style.opacity = '0';
          card.style.transform = 'scale(0.95)';
          setTimeout(() => card.remove(), 300);
        }
      } else {
        showToast('Failed to delete product.', 'error');
      }
    })
    .catch(() => showToast('Network error.', 'error'));
}

// ─── NOTIFICATION BELL ───
function toggleNotifDropdown() {
  const dropdown = document.getElementById('notif-dropdown');
  if (!dropdown) return;
  dropdown.classList.toggle('open');

  if (dropdown.classList.contains('open')) {
    // Mark as read via API
    fetch('/api/notifications/read/', {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') }
    }).then(() => {
      const badge = document.getElementById('notif-badge');
      if (badge) badge.style.display = 'none';
    });
  }
}

// Close notif on outside click
document.addEventListener('click', function(e) {
  const bell = document.getElementById('notif-bell-btn');
  const dropdown = document.getElementById('notif-dropdown');
  if (bell && dropdown && !bell.contains(e.target) && !dropdown.contains(e.target)) {
    dropdown.classList.remove('open');
  }
});

// ─── IMAGE PREVIEW IN PRODUCT FORM ───
function initImageUpload() {
  const zone = document.getElementById('upload-zone');
  const input = document.getElementById('id_image');
  const preview = document.getElementById('image-preview');
  const previewImg = document.getElementById('preview-img');
  const removeBtn = document.getElementById('remove-preview');

  if (!zone || !input) return;

  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(evt => {
    zone.addEventListener(evt, e => { e.preventDefault(); e.stopPropagation(); });
  });
  zone.addEventListener('dragenter', () => zone.classList.add('drag-over'));
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    zone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) showPreview(file);
  });

  input.addEventListener('change', () => {
    if (input.files[0]) showPreview(input.files[0]);
  });

  if (removeBtn) {
    removeBtn.addEventListener('click', () => {
      input.value = '';
      preview.style.display = 'none';
      zone.style.display = 'flex';
    });
  }

  function showPreview(file) {
    if (!file.type.startsWith('image/')) {
      showToast('Please upload an image file.', 'error');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      showToast('Image must be under 5MB.', 'error');
      return;
    }
    const reader = new FileReader();
    reader.onload = e => {
      if (previewImg) previewImg.src = e.target.result;
      if (preview) preview.style.display = 'inline-block';
      if (zone) zone.style.display = 'none';
    };
    reader.readAsDataURL(file);
  }
}

// ─── SIZE COLOR LIVE PREVIEW ───
function initSizeColorPreview() {
  const input = document.getElementById('id_size_color_raw');
  const preview = document.getElementById('size-pill-preview');
  if (!input || !preview) return;

  function parseSizeColor(raw) {
    const out = [];
    const parts = raw.split(',');
    let current = '';
    const tokens = [];
    // Simple parser for "s:(green,yellow), m:(white)"
    for (const part of parts) {
      current += (current ? ',' : '') + part.trim();
      if (!current.includes('(') || (current.indexOf('(') !== -1 && current.indexOf(')') !== -1)) {
        tokens.push(current.trim());
        current = '';
      }
    }
    if (current.trim()) tokens.push(current.trim());

    tokens.forEach(tok => {
      const m = tok.match(/^(\w+)\s*:\s*\(([^)]+)\)$/i) || tok.match(/^(\w+)\s*:\s*([^,]+)$/i);
      if (m) {
        out.push({ size: m[1].toUpperCase(), colors: m[2].split(',').map(c => c.trim()).filter(Boolean) });
      }
    });
    return out;
  }

  function render() {
    const val = input.value.trim();
    if (!val) { preview.innerHTML = ''; return; }
    const parsed = parseSizeColor(val);
    preview.innerHTML = parsed.map(p =>
      `<span class="size-pill">[${p.size}] <span class="size-pill-colors">${p.colors.join(' · ')}</span></span>`
    ).join('');
  }

  input.addEventListener('input', render);
  render();
}


// ─── BULK SELECTION MODE ───
function toggleSelectionMode() {
  const section = document.querySelector('.order-section');
  if (!section) return;

  const isModeActive = section.classList.toggle('selection-mode');
  
  // Adjust colspan for expand rows in desktop table
  const expandTds = document.querySelectorAll('td[id^="expand-td-"]');
  expandTds.forEach(td => {
    let currentColspan = parseInt(td.getAttribute('data-original-colspan') || td.getAttribute('colspan'));
    if (!td.hasAttribute('data-original-colspan')) {
      td.setAttribute('data-original-colspan', currentColspan);
    }
    
    // If selection mode is active, the column is visible, so use the full colspan (original + 1).
    // If not, the column is hidden, so use the original colspan.
    td.setAttribute('colspan', isModeActive ? currentColspan + 1 : currentColspan);
  });

  // Reset checkboxes if turning off
  if (!isModeActive) {
    const banner = document.getElementById('select-all-orders');
    if (banner) banner.checked = false;
    toggleSelectAllOrders(false);
  }
}

// ─── SIDEBAR TOGGLE ───
function initSidebar() {
  const toggleBtn = document.getElementById('sidebar-toggle-btn');
  if (!toggleBtn) return;

  toggleBtn.onclick = (e) => {
    const isCollapsed = document.documentElement.classList.toggle('sidebar-collapsed');
    localStorage.setItem('kaam-sidebar-collapsed', isCollapsed);
  };
}

// ─── PROFILE MENU ───
function toggleProfileMenu() {
  const m = document.getElementById('profile-menu');
  if (!m) return;
  m.classList.toggle('open');
}

// Global click handler to close dropdowns
document.addEventListener('click', function(e) {
  // Profile menu
  const avatarWrap = document.querySelector('.seller-avatar-wrap');
  const profMenu = document.getElementById('profile-menu');
  if (avatarWrap && profMenu && !avatarWrap.contains(e.target)) {
    profMenu.classList.remove('open');
  }

  // Notif menu
  const notifWrap = document.querySelector('.notif-bell')?.parentElement;
  const notifMenu = document.getElementById('notif-dropdown');
  if (notifWrap && notifMenu && !notifWrap.contains(e.target) && !e.target.closest('#notif-bell-btn')) {
    notifMenu.classList.remove('open');
  }
});

// ─── INIT ───
document.addEventListener('DOMContentLoaded', () => {
  initImageUpload();
  initSizeColorPreview();
  initSidebar();

  // Only poll on dashboard page
  if (document.getElementById('monthly-revenue')) {
    pollAnalytics();
    pollTimer = setInterval(pollAnalytics, POLL_INTERVAL);
  }
  syncSelectAllOrdersState();
});
