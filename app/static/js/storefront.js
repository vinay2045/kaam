/* ═══════════════════════════════════════════════
   KAAM — storefront.js
   Multi-step buyer order form
═══════════════════════════════════════════════ */

let currentStep = 0;
let isSubmitting = false;
let orderData = {
  buyer_name: '', buyer_email: '', buyer_whatsapp: '', buyer_instagram: '',
  country: 'India', address_line1: '', address_line2: '', city: '', state: '', pincode: '',
  payment_method: '',
  utr_number: '',
  items: [],
};

const steps = document.querySelectorAll('.sf-step');
const progressFill = document.getElementById('sf-progress-fill');
const stepCounter = document.getElementById('sf-step-counter');
const PERSIST_KEY = 'kaam-buyer-profile-v1';

function showStep(n) {
  if (n < 0 || n >= steps.length) return;
  steps.forEach((s, i) => s.classList.toggle('active', i === n));
  currentStep = n;
  const totalSteps = steps.length - 1;
  const pct = (n / totalSteps) * 100;
  if (progressFill) progressFill.style.width = pct + '%';
  if (stepCounter) stepCounter.textContent = `Step ${n} of ${totalSteps}`;
  window.scrollTo({ top: 0, behavior: 'smooth' });
  updateSummaryStrip();
  saveSession();
}

function nextStep() {
  if (!validateStep(currentStep)) return;
  collectStepData(currentStep);
  showStep(currentStep + 1);
}

function prevStep() {
  showStep(currentStep - 1);
}

function validateStep(step) {
  clearErrors();
  const errors = [];

  const ALLOWED_EMAIL_DOMAINS = ['gmail.com', 'hotmail.com', 'yahoo.com', 'outlook.com', 'icloud.com'];
  const BLOCKED_KEYWORDS = ['dummy', 'test', 'fake', 'spam', 'none', 'nothing', 'demo', 'null', 'abcd', 'asdf', 'qwerty', '1234'];

  const containsSpam = (str) => {
    if (!str) return false;
    const cleaned = str.toLowerCase().replace(/[^a-z0-9]/g, '');
    return BLOCKED_KEYWORDS.some(k => cleaned.includes(k));
  };

  const isRepetitive = (str) => {
    return /(.)\1{4,}/.test(str); // 5+ repeating characters
  };

  if (step === 1) {
    const name  = document.getElementById('buyer-name')?.value.trim() || '';
    const email = document.getElementById('buyer-email')?.value.trim() || '';
    const wa    = document.getElementById('buyer-wa')?.value.trim() || '';
    
    // Name checks
    if (!name || name.length < 2) errors.push('Please enter your full name (at least 2 characters).');
    if (containsSpam(name)) errors.push('Please enter a real name, placeholder names are not allowed.');
    if (/^\d+$/.test(name.replace(/\s/g, ''))) errors.push('Name cannot be entirely numeric.');

    // Email checks
    const emailParts = email.toLowerCase().split('@');
    if (!email || emailParts.length !== 2) {
      errors.push('Please enter a valid email address.');
    } else {
      const domain = emailParts[1];
      if (!ALLOWED_EMAIL_DOMAINS.includes(domain)) {
        errors.push(`Please use a standard email: ${ALLOWED_EMAIL_DOMAINS.join(', ')}`);
      }
      if (containsSpam(emailParts[0])) {
        errors.push('This email looks like dummy data.');
      }
    }

    // Phone checks
    const digits = wa.replace(/\D/g,'');
    if (!wa || digits.length < 10) {
      errors.push('Please enter a valid WhatsApp number (at least 10 digits).');
    } else {
      if (new Set(digits).size === 1) errors.push('Invalid phone number (all digits are the same).');
      if (["12345678", "01234567", "87654321", "98765432"].some(seq => digits.includes(seq))) {
        errors.push('Invalid phone number (long sequential digits).');
      }
    }
  }

  if (step === 2) {
    const addr1 = document.getElementById('addr1')?.value.trim() || '';
    const city = document.getElementById('city')?.value.trim() || '';
    const state = document.getElementById('state')?.value.trim() || '';
    const pincode = document.getElementById('pincode')?.value.trim() || '';

    if (!addr1 || addr1.length < 5) errors.push('Address Line 1 is too short.');
    if (containsSpam(addr1 + city + state)) errors.push('Address contains placeholder/dummy keywords.');
    if (isRepetitive(addr1)) errors.push('Address contains repetitive characters (not allowed).');
    
    if (!city) errors.push('City is required.');
    if (!state) errors.push('State is required.');
    
    const cleanPin = pincode.replace(/[^a-z0-9]/gi, '');
    if (!cleanPin || cleanPin.length < 3) errors.push('Pincode/ZIP is too short.');
    if (new Set(cleanPin).size === 1 && cleanPin.length > 3) errors.push('Invalid Pincode/ZIP format.');
  }

  if (step === 3) {
    if (orderData.items.length === 0) errors.push('Please select at least one product.');
    orderData.items.forEach((item, i) => {
      if (!item.variant_label && !item.size_color) {
        const product = window.PRODUCTS_DATA?.[item.product_id] || {};
        if (product.variants && product.variants.length > 0) {
          errors.push(`Please choose a variant for "${item.title}" (item ${i + 1}).`);
        }
      }
      if (!item.qty || item.qty < 1) errors.push(`Quantity must be at least 1 for item ${i + 1}.`);
    });
  }

  if (step === 4) {
    if (!orderData.payment_method) errors.push('Please select a payment method.');
  }

  if (step === 5) {
    const utr = document.getElementById('utr-input')?.value.trim() || '';
    const hasScreenshot = document.getElementById('payment-screenshot-input')?.files?.[0];
    if (!utr && !hasScreenshot) {
      errors.push('Please enter a UTR number OR upload a payment screenshot.');
    } else if (utr) {
      if (utr.length < 8) errors.push('UTR/Transaction ID must be at least 8 characters.');
      if (containsSpam(utr)) errors.push('Transaction ID contains invalid keywords.');
    }
  }

  if (errors.length) showValidationErrors(errors);
  return errors.length === 0;
}

function collectStepData(step) {
  if (step === 1) {
    orderData.buyer_name     = document.getElementById('buyer-name')?.value.trim() || '';
    orderData.buyer_email    = document.getElementById('buyer-email')?.value.trim() || '';
    orderData.buyer_whatsapp = document.getElementById('buyer-wa')?.value.trim() || '';
    orderData.buyer_instagram= document.getElementById('buyer-ig')?.value.trim() || '';
  }
  if (step === 2) {
    orderData.country      = document.getElementById('country')?.value.trim() || 'India';
    orderData.address_line1= document.getElementById('addr1')?.value.trim() || '';
    orderData.address_line2= document.getElementById('addr2')?.value.trim() || '';
    orderData.city         = document.getElementById('city')?.value.trim() || '';
    orderData.state        = document.getElementById('state')?.value.trim() || '';
    orderData.pincode      = document.getElementById('pincode')?.value.trim() || '';
  }
  if (step === 1 || step === 2 || step === 3) {
    savePersistentBuyerData();
  }
  if (step === 4) {
    const sel = document.querySelector('.payment-ticket.selected');
    orderData.payment_method = sel?.dataset.method || '';
  }
  if (step === 5) {
    orderData.utr_number = document.getElementById('utr-input')?.value.trim() || '';
  }
}

function showValidationErrors(errors) {
  let errBox = document.getElementById('validation-errors');
  if (!errBox) {
    errBox = document.createElement('div');
    errBox.id = 'validation-errors';
    errBox.className = 'sf-validation-errors';
    const activeStep = document.querySelector('.sf-step.active');
    if (activeStep) activeStep.insertBefore(errBox, activeStep.firstChild);
  }
  errBox.innerHTML = `<ul>${errors.map(e => `<li>${e}</li>`).join('')}</ul>`;
  errBox.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function clearErrors() {
  const errBox = document.getElementById('validation-errors');
  if (errBox) errBox.remove();
}

function formatVariantLabel(label) {
  const raw = (label || '').trim();
  if (!raw) return '';
  if (raw.toLowerCase() === 'default') return 'Default';
  const keyMap = {
    'color / flavor': 'Color',
    'color/flavor': 'Color',
    'flavor': 'Flavor',
    'colour': 'Color',
    'size / weight': 'Size',
    'size/weight': 'Size',
    'weight': 'Weight',
    'model': 'Model',
  };
  const normalized = raw.replace(/[•|]/g, '·').replace(/\s+/g, ' ').trim();
  const kvPattern = /([A-Za-z0-9/ _-]+?)\s*:\s*([^:·,]+?)(?=(?:\s*·\s*|\s*,\s*|\s+[A-Za-z0-9/ _-]+?\s*:|$))/g;
  const pairs = [];
  let match;
  while ((match = kvPattern.exec(normalized)) !== null) {
    const key = (match[1] || '').trim();
    const value = (match[2] || '').trim();
    if (!key || !value) continue;
    pairs.push({ key, value });
  }
  if (pairs.length === 0) {
    const shortRaw = normalized.length > 40 ? normalized.slice(0, 40) + '…' : normalized;
    return shortRaw;
  }
  const mapped = pairs.map(({ key, value }) => {
    const normalizedKey = keyMap[key.toLowerCase()] || key;
    const shortValue = value.length > 16 ? value.slice(0, 16) + '…' : value;
    if (normalizedKey.toLowerCase() === shortValue.toLowerCase()) {
      return normalizedKey;
    }
    return `${normalizedKey}: ${shortValue}`;
  });
  return mapped.join(' · ');
}

function syncProductCardState(productId) {
  const card = document.querySelector(`[data-product-id="${productId}"]`);
  if (!card) return;
  const toggleText = card.querySelector('.toggle-text');
  const addMore = document.getElementById(`add-more-${productId}`);
  const isSelected = card.classList.contains('selected');
  if (toggleText) toggleText.textContent = isSelected ? '✓ Added' : '+ Add';
  if (addMore) addMore.style.display = isSelected ? 'inline-flex' : 'none';
}

// ─── PRODUCT SELECTION ───
function toggleProduct(productId) {
  const card = document.querySelector(`[data-product-id="${productId}"]`);
  if (!card) return;
  const isSelected = card.classList.contains('selected');
  if (!isSelected) {
    card.classList.add('selected');
    addProductInputRow(productId);
  } else {
    card.classList.remove('selected');
    removeProductInputRows(productId);
  }
  syncProductCardState(productId);
  collectItemsFromDOM();
  updateSummaryStrip();
}

// ─── VARIANT CARDS (buyer-facing) ───
function addProductInputRow(productId) {
  const container = document.getElementById(`inputs-${productId}`);
  if (!container) return;
  const product = window.PRODUCTS_DATA?.[productId] || {};
  const variants = product.variants || [];
  const rowId = `${productId}-${Date.now()}`;

  const row = document.createElement('div');
  row.className = 'product-input-row';
  row.dataset.rowId = rowId;
  row.dataset.productId = productId;

  let variantSection = '';

  if (variants.length > 0) {
    if (variants.length === 1 && (variants[0].is_default || variants[0].label === 'Default')) {
      const v = variants[0];
      if (v.stock === 0) {
        variantSection = `
          <div class="variant-cards-wrap" style="margin-bottom: 0;">
             <span style="font-size:13px;color:var(--kaam-danger);font-weight:600;">Out of stock</span>
          </div>`;
      } else {
        variantSection = `
          <input type="hidden" class="selected-variant-input" id="selected-variant-${rowId}" value="Default">
          <input type="hidden" id="selected-price-${rowId}" value="${parseFloat(v.price || product.price || 0)}">
          <input type="hidden" id="max-stock-${rowId}" value="${v.stock}">
          <div class="variant-cards-wrap" style="margin-bottom: 0;">
             <span style="font-size:12px;color:var(--kaam-success, #27ae60);font-weight:600;">${v.stock} in stock · ₹${formatIndian(parseFloat(v.price || product.price || 0))}</span>
          </div>`;
      }
    } else {
      // Build clickable variant cards — filter out 0-stock ones
      const availableVariants = variants.filter(v => v.stock > 0);
      const outOfStockVariants = variants.filter(v => v.stock === 0);

      if (availableVariants.length === 0) {
        // All out of stock
        variantSection = `
          <div class="variant-cards-wrap">
            <div class="variant-cards-label">Choose variant</div>
            <div class="variant-out-of-stock-msg">⚠ All variants currently out of stock</div>
          </div>`;
      } else {
        const chipsHtml = availableVariants.map(v => `
          <button type="button"
            class="variant-chip"
            data-label="${v.label}"
            data-stock="${v.stock}"
            data-price="${parseFloat(v.price || product.price || 0)}"
            data-row-id="${rowId}"
            title="${v.label}"
            onclick="selectVariant(this, '${rowId}', '${productId}')">
            <span class="variant-chip-text">${formatVariantLabel(v.label)} · ₹${formatIndian(parseFloat(v.price || product.price || 0))}</span>
          </button>`).join('') +
          outOfStockVariants.map(v => `
          <button type="button" class="variant-chip out-of-stock" disabled title="${v.label} · Out of stock">
            <span class="variant-chip-text">${formatVariantLabel(v.label)}</span>
          </button>`).join('');

        variantSection = `
          <div class="variant-cards-wrap">
            <div class="variant-cards-label">Choose variant <span class="required-star">*</span></div>
            <div class="variant-cards" id="variant-cards-${rowId}">${chipsHtml}</div>
            <input type="hidden" class="selected-variant-input" id="selected-variant-${rowId}" value="">
            <input type="hidden" id="selected-price-${rowId}" value="${parseFloat(product.price || 0)}">
            <input type="hidden" id="max-stock-${rowId}" value="0">
          </div>`;
      }
    }
  } else {
    // No variants defined — free text fallback
    variantSection = `
      <div class="input-group" style="flex:1">
        <label class="input-label">Size &amp; Color <span style="color:var(--kaam-stone-dark);font-weight:400">(optional)</span></label>
        <input type="text" class="input-field size-color-input" placeholder="e.g. M – Green"
               data-row-id="${rowId}" oninput="collectItemsFromDOM(); updateSummaryStrip()">
      </div>`;
  }

  row.innerHTML = `
    ${variantSection}
    <div class="qty-row">
      <label class="input-label">Qty</label>
      <div class="qty-control">
        <button type="button" class="qty-btn" onclick="changeQty('${rowId}', -1)">−</button>
        <span class="qty-display" id="qty-${rowId}">1</span>
        <button type="button" class="qty-btn" onclick="changeQty('${rowId}', 1)">+</button>
      </div>
    </div>
    <button type="button" class="remove-row-btn" onclick="removeRow('${rowId}', '${productId}')" title="Remove">✕</button>
  `;
  container.appendChild(row);
  const firstVariantBtn = row.querySelector('.variant-cards .variant-chip:not(.out-of-stock)');
  const hiddenVariant = row.querySelector('.selected-variant-input');
  if (firstVariantBtn && hiddenVariant && !hiddenVariant.value) {
    firstVariantBtn.click();
  }
}

function selectVariant(btn, rowId, productId) {
  // Deselect siblings
  const wrap = document.getElementById(`variant-cards-${rowId}`);
  if (wrap) {
    wrap.querySelectorAll('.variant-chip').forEach(c => c.classList.remove('selected'));
  }
  btn.classList.add('selected');
  const hiddenInput = document.getElementById(`selected-variant-${rowId}`);
  if (hiddenInput) hiddenInput.value = btn.dataset.label;
  const selectedPriceInput = document.getElementById(`selected-price-${rowId}`);
  if (selectedPriceInput) selectedPriceInput.value = String(parseFloat(btn.dataset.price || 0));
  
  const maxStockInput = document.getElementById(`max-stock-${rowId}`);
  if (maxStockInput) maxStockInput.value = btn.dataset.stock;
  
  // Also clamp currently typed qty if it's over the new max
  const qtyEl = document.getElementById(`qty-${rowId}`);
  if (qtyEl) {
    const maxStock = parseInt(btn.dataset.stock) || 1;
    let currentQty = parseInt(qtyEl.textContent) || 1;
    if (currentQty > maxStock) qtyEl.textContent = maxStock;
  }
  
  collectItemsFromDOM();
  updateSummaryStrip();
}

function removeRow(rowId, productId) {
  const row = document.querySelector(`[data-row-id="${rowId}"]`);
  if (row) row.remove();
  const container = document.getElementById(`inputs-${productId}`);
  if (container && container.children.length === 0) {
    const card = document.querySelector(`[data-product-id="${productId}"]`);
    if (card) card.classList.remove('selected');
  }
  syncProductCardState(productId);
  collectItemsFromDOM();
  updateSummaryStrip();
}

function removeProductInputRows(productId) {
  const container = document.getElementById(`inputs-${productId}`);
  if (container) container.innerHTML = '';
  syncProductCardState(productId);
  collectItemsFromDOM();
  updateSummaryStrip();
}

function addAnotherItem(productId) {
  const card = document.querySelector(`[data-product-id="${productId}"]`);
  if (!card) return;
  card.classList.add('selected');
  addProductInputRow(productId);
  syncProductCardState(productId);
  collectItemsFromDOM();
  updateSummaryStrip();
}

function changeQty(rowId, delta) {
  const display = document.getElementById(`qty-${rowId}`);
  if (!display) return;
  const current = parseInt(display.textContent) || 1;
  const maxStockEl = document.getElementById(`max-stock-${rowId}`);
  const maxAllowed = maxStockEl ? parseInt(maxStockEl.value) : Infinity;
  let newQty = current + delta;
  
  if (newQty < 1) newQty = 1;
  if (newQty > maxAllowed && maxAllowed > 0) newQty = maxAllowed;
  
  display.textContent = newQty;
  collectItemsFromDOM();
  updateSummaryStrip();
}

function collectItemsFromDOM() {
  const items = [];
  document.querySelectorAll('.product-input-row').forEach(row => {
    const productId = row.dataset.productId;
    const rowId = row.dataset.rowId;

    // Try variant card selection first
    const hiddenVariant = document.getElementById(`selected-variant-${rowId}`);
    let variantLabel = hiddenVariant ? hiddenVariant.value.trim() : '';
    if (!variantLabel) {
      const selectedChip = row.querySelector('.variant-chip.selected');
      if (selectedChip && selectedChip.dataset.label) {
        variantLabel = selectedChip.dataset.label.trim();
      } else {
        const firstAvailableChip = row.querySelector('.variant-chip:not(.out-of-stock)');
        if (firstAvailableChip && firstAvailableChip.dataset.label) {
          variantLabel = firstAvailableChip.dataset.label.trim();
          firstAvailableChip.classList.add('selected');
          if (hiddenVariant) hiddenVariant.value = variantLabel;
          const maxStockInput = document.getElementById(`max-stock-${rowId}`);
          if (maxStockInput && firstAvailableChip.dataset.stock) {
            maxStockInput.value = firstAvailableChip.dataset.stock;
          }
        }
      }
    }

    // Fallback: free text
    const freeText = row.querySelector('.size-color-input')?.value.trim() || '';

    const qtyEl = document.getElementById(`qty-${rowId}`);
    const qty = parseInt(qtyEl?.textContent) || 1;
    const product = window.PRODUCTS_DATA?.[productId] || {};
    if (productId) {
      const selectedPrice = parseFloat(document.getElementById(`selected-price-${rowId}`)?.value || product.price || 0);
      items.push({
        product_id: productId,
        variant_label: variantLabel,
        size_color: variantLabel ? formatVariantLabel(variantLabel) : freeText,
        qty: qty,
        title: product.title || '',
        price: selectedPrice,
      });
    }
  });
  orderData.items = items;
}

// ─── ORDER SUMMARY STRIP ───
function updateSummaryStrip() {
  const strip = document.getElementById('order-summary-strip');
  if (!strip) return;
  if (orderData.items.length === 0) {
    strip.classList.remove('visible');
    return;
  }
  strip.classList.add('visible');
  const itemsList = document.getElementById('summary-items');
  const subtotal = document.getElementById('summary-subtotal');
  const total = document.getElementById('summary-total');
  const countBadge = document.getElementById('summary-count-badge');
  if (itemsList) {
    itemsList.innerHTML = orderData.items.map(item => {
      const itemTotal = item.price * item.qty;
      const variantText = item.size_color ? formatVariantLabel(item.size_color) : 'Standard';
      const titleShort = item.title.length > 22 ? item.title.slice(0, 22) + '…' : item.title;
      return `<div class="sf-summary-line"><div><div class="sf-summary-name">${titleShort}</div><div class="sf-summary-meta">${variantText} · x${item.qty}</div></div><div class="sf-summary-amount">₹${formatIndian(itemTotal)}</div></div>`;
    }).join('');
  }
  const totalQty = orderData.items.reduce((sum, item) => sum + item.qty, 0);
  const sum = orderData.items.reduce((s, i) => s + (i.price * i.qty), 0);
  if (subtotal) subtotal.textContent = '₹' + formatIndian(sum);
  if (total) {
    total.textContent = '₹' + formatIndian(sum);
  }
  if (countBadge) countBadge.textContent = `${totalQty} item${totalQty === 1 ? '' : 's'}`;

  // Also update step 4 summary
  renderStep4Summary();
}

// ─── PAYMENT SELECTION ───
function selectPayment(method) {
  document.querySelectorAll('.payment-ticket').forEach(t => t.classList.remove('selected'));
  const ticket = document.querySelector(`.payment-ticket[data-method="${method}"]`);
  if (ticket) ticket.classList.add('selected');
  orderData.payment_method = method;

  const step5Nav = document.getElementById('step4-next-btn');
  if (step5Nav) {
    step5Nav.textContent = method === 'online' ? 'Proceed to Payment →' : 'Place Order →';
    step5Nav.dataset.action = method === 'online' ? 'next' : 'submit';
  }
}

function renderStep4Summary() {
  const container = document.getElementById('step4-order-items');
  if (!container) return;
  container.innerHTML = orderData.items.map(item => {
    const product = window.PRODUCTS_DATA?.[item.product_id] || {};
    const imgUrl = product.image_url || '';
    return `
      <div class="order-summary-item">
        <img src="${imgUrl}" alt="${item.title}" class="order-summary-img"
             onerror="this.style.display='none'">
        <div class="order-summary-item-info">
          <div class="order-summary-item-title">${item.title}</div>
          <div class="order-summary-item-meta">${item.size_color ? formatVariantLabel(item.size_color) : '—'} · Qty ${item.qty}</div>
        </div>
        <div class="order-summary-item-price">₹${formatIndian(item.price * item.qty)}</div>
      </div>
    `;
  }).join('');
  const total = orderData.items.reduce((s, i) => s + i.price * i.qty, 0);
  const totalEl = document.getElementById('step4-total');
  if (totalEl) totalEl.textContent = '₹' + formatIndian(total);

  const addrEl = document.getElementById('step4-address');
  if (addrEl) {
    addrEl.innerHTML = `
      <strong>${orderData.buyer_name}</strong><br>
      ${orderData.address_line1}${orderData.address_line2 ? ', ' + orderData.address_line2 : ''}<br>
      ${orderData.city}, ${orderData.state} – ${orderData.pincode}<br>
      <span style="color:var(--kaam-stone-dark)">WhatsApp: ${orderData.buyer_whatsapp}</span>
    `;
  }

  const amountEl = document.getElementById('upi-amount-display');
  if (amountEl) amountEl.textContent = '₹' + formatIndian(total);
}

// ─── STEP 4 NEXT ───
function step4Next() {
  if (!validateStep(4)) return;
  collectStepData(4);

  if (orderData.payment_method === 'online') {
    showStep(5);
  } else {
    submitOrder();
  }
}

// ─── PAYMENT SCREENSHOT UPLOAD ───
function initPaymentUpload() {
  const input = document.getElementById('payment-screenshot-input');
  const zone = document.getElementById('payment-upload-zone');
  const preview = document.getElementById('payment-preview');
  if (!input || !zone) return;

  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    if (e.dataTransfer.files[0]) previewPaymentFile(e.dataTransfer.files[0]);
  });

  input.addEventListener('change', () => {
    if (input.files[0]) previewPaymentFile(input.files[0]);
  });

  function previewPaymentFile(file) {
    if (!file.type.startsWith('image/')) { showToast('Upload an image file.', 'error'); return; }
    if (file.size > 5 * 1024 * 1024) { showToast('File must be under 5MB.', 'error'); return; }
    const reader = new FileReader();
    reader.onload = e => {
      if (preview) { preview.src = e.target.result; preview.style.display = 'block'; }
    };
    reader.readAsDataURL(file);
  }
}

// ─── SUBMIT ORDER ───
async function submitOrder() {
  if (isSubmitting) return;
  if (orderData.payment_method === 'online' && !validateStep(5)) return;
  if (currentStep === 5) collectStepData(5);
  isSubmitting = true;
  const submitBtn = document.getElementById('submit-btn');
  const step4Btn = document.getElementById('step4-next-btn');
  if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'Placing Order…'; }
  if (step4Btn) { step4Btn.disabled = true; step4Btn.textContent = 'Placing Order…'; }

  collectItemsFromDOM();
  if (orderData.items.length === 0 || !orderData.payment_method) {
    showToast('Missing order data. Please go back and fill all fields.', 'error');
    if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'Place Order →'; }
    if (step4Btn) { step4Btn.disabled = false; step4Btn.textContent = 'Place Order →'; }
    isSubmitting = false;
    return;
  }

  const payload = {
    buyer: {
      name: orderData.buyer_name,
      email: orderData.buyer_email,
      whatsapp: orderData.buyer_whatsapp,
      instagram: orderData.buyer_instagram || '',
    },
    address: {
      country: orderData.country,
      line1: orderData.address_line1,
      line2: orderData.address_line2 || '',
      city: orderData.city,
      state: orderData.state,
      pincode: orderData.pincode,
    },
    items: orderData.items.map(item => ({
      product_id: item.product_id,
      size_color: item.size_color,
      variant_label: item.variant_label || item.size_color,
      qty: item.qty,
    })),
    payment_method: orderData.payment_method,
    utr_number: orderData.utr_number || '',
  };

  const formData = new FormData();
  formData.append('data', JSON.stringify(payload));
  if (orderData.payment_method === 'online') {
    const fileEl = document.getElementById('payment-screenshot-input');
    if (fileEl && fileEl.files[0]) {
      formData.append('payment_screenshot', fileEl.files[0]);
    }
  }

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 45000);
    const res = await fetch(`/${window.SELLER_USERNAME}/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCookie('csrftoken'),
      },
      body: formData,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    const data = await res.json();
    if (data.success) {
      sessionStorage.removeItem('kaam-order-session');
      window.location.href = `/${window.SELLER_USERNAME}/order-placed/${data.order_id}/`;
    } else {
      showToast(data.error || 'Something went wrong. Please try again.', 'error');
      if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'Place Order →'; }
      if (step4Btn) { step4Btn.disabled = false; step4Btn.textContent = 'Place Order →'; }
      isSubmitting = false;
    }
  } catch (e) {
    showToast('Request timed out or failed. Please retry once.', 'error');
    if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'Place Order →'; }
    if (step4Btn) { step4Btn.disabled = false; step4Btn.textContent = 'Place Order →'; }
    isSubmitting = false;
  }
}

// ─── SESSION STORAGE ───
function saveSession() {
  try {
    sessionStorage.setItem('kaam-order-session', JSON.stringify({ step: currentStep, orderData }));
  } catch (e) {}
}

function savePersistentBuyerData() {
  try {
    const profile = {
      buyer_name: orderData.buyer_name || '',
      buyer_email: orderData.buyer_email || '',
      buyer_whatsapp: orderData.buyer_whatsapp || '',
      buyer_instagram: orderData.buyer_instagram || '',
      country: orderData.country || 'India',
      address_line1: orderData.address_line1 || '',
      address_line2: orderData.address_line2 || '',
      city: orderData.city || '',
      state: orderData.state || '',
      pincode: orderData.pincode || '',
    };
    localStorage.setItem(PERSIST_KEY, JSON.stringify(profile));
  } catch (e) {}
}

function restorePersistentBuyerData() {
  try {
    const saved = JSON.parse(localStorage.getItem(PERSIST_KEY) || '{}');
    if (!saved || typeof saved !== 'object') return;
    Object.assign(orderData, saved);
  } catch (e) {}
}

function restoreSession() {
  try {
    const saved = JSON.parse(sessionStorage.getItem('kaam-order-session') || '{}');
    if (saved.orderData) {
      Object.assign(orderData, saved.orderData);
      if (saved.step > 0) fillRestoredFields();
    }
    if (saved.step > 0 && saved.step < steps.length) {
      showStep(saved.step);
    } else {
      showStep(0);
    }
  } catch (e) {
    showStep(0);
  }
}

function fillRestoredFields() {
  const fields = {
    'buyer-name': orderData.buyer_name,
    'buyer-email': orderData.buyer_email,
    'buyer-wa': orderData.buyer_whatsapp,
    'buyer-ig': orderData.buyer_instagram,
    'country': orderData.country,
    'addr1': orderData.address_line1,
    'addr2': orderData.address_line2,
    'city': orderData.city,
    'state': orderData.state,
    'pincode': orderData.pincode,
  };
  Object.entries(fields).forEach(([id, val]) => {
    const el = document.getElementById(id);
    if (el && val) el.value = val;
  });
}

function handleEnterNavigation(e) {
  if (e.key !== 'Enter' || e.shiftKey || e.altKey || e.ctrlKey || e.metaKey) return;
  const target = e.target;
  if (!target || !(target instanceof HTMLElement)) return;
  if (!target.matches('input, select, textarea')) return;

  const activeStepEl = document.querySelector(`.sf-step[data-step="${currentStep}"]`);
  if (!activeStepEl) return;

  const fields = Array.from(activeStepEl.querySelectorAll('input, select, textarea'))
    .filter(el => {
      if (!(el instanceof HTMLElement)) return false;
      if (el.hasAttribute('disabled')) return false;
      if (el.getAttribute('type') === 'hidden') return false;
      if (el.offsetParent === null) return false;
      return true;
    });

  if (fields.length === 0) return;
  const idx = fields.indexOf(target);
  if (idx === -1) return;

  e.preventDefault();

  const nextField = fields[idx + 1];
  if (nextField && nextField instanceof HTMLElement) {
    nextField.focus();
    if (nextField instanceof HTMLInputElement || nextField instanceof HTMLTextAreaElement) {
      const pos = nextField.value?.length || 0;
      nextField.setSelectionRange(pos, pos);
    }
    return;
  }

  if (currentStep === 0 || currentStep === 1 || currentStep === 2 || currentStep === 3) {
    nextStep();
    return;
  }
  if (currentStep === 4) {
    step4Next();
    return;
  }
  if (currentStep === 5) {
    submitOrder();
  }
}

// ─── BROWSER BACK BUTTON ───
window.addEventListener('popstate', e => {
  e.preventDefault();
  if (currentStep > 0) {
    showStep(currentStep - 1);
    history.pushState(null, '', location.pathname);
  }
});

// ─── INIT ───
document.addEventListener('DOMContentLoaded', () => {
  history.pushState(null, '', location.pathname);
  initPaymentUpload();
  document.addEventListener('keydown', handleEnterNavigation);
  restorePersistentBuyerData();
  restoreSession();
  fillRestoredFields();
  const canOnline = !!window.SELLER_SETTINGS?.allow_online_payment;
  const canCod = !!window.SELLER_SETTINGS?.allow_cod;
  if (canOnline && !canCod) selectPayment('online');
  if (!canOnline && canCod) selectPayment('cod');
  document.querySelectorAll('.product-slip').forEach(card => {
    const productId = card.dataset.productId;
    if (productId) syncProductCardState(productId);
  });
});
