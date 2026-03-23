// ReUse Market - Main JS
const API = {
  async request(url, opts = {}) {
    try {
      const res = await fetch(url, {
        headers: { 'Content-Type': 'application/json', ...opts.headers },
        credentials: 'include',
        ...opts
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Request failed');
      return data;
    } catch (e) {
      throw e;
    }
  },
  get: (url) => API.request(url),
  post: (url, body) => API.request(url, { method: 'POST', body: JSON.stringify(body) }),
  put: (url, body) => API.request(url, { method: 'PUT', body: JSON.stringify(body) }),
  delete: (url) => API.request(url, { method: 'DELETE' }),
};

// Toast notifications
const Toast = {
  container: null,
  init() {
    this.container = document.createElement('div');
    this.container.className = 'toast-container';
    document.body.appendChild(this.container);
  },
  show(msg, type = 'default', duration = 3000) {
    const t = document.createElement('div');
    const icons = { success: '✓', error: '✗', default: 'ℹ' };
    t.className = `toast ${type}`;
    t.innerHTML = `<span>${icons[type] || icons.default}</span><span>${msg}</span>`;
    this.container.appendChild(t);
    setTimeout(() => { t.style.opacity = '0'; t.style.transform = 'translateX(20px)'; t.style.transition = '0.3s'; setTimeout(() => t.remove(), 300); }, duration);
  },
  success: (msg) => Toast.show(msg, 'success'),
  error: (msg) => Toast.show(msg, 'error'),
};

// App state
const App = {
  user: null,
  async init() {
    Toast.init();
    await this.loadUser();
    this.updateNav();
    this.updateUnreadBadge();
  },
  async loadUser() {
    try {
      const data = await API.get('/api/me');
      this.user = data.user;
    } catch (e) {
      this.user = null;
    }
  },
  updateNav() {
    const authBtns = document.getElementById('nav-auth-btns');
    const userMenu = document.getElementById('nav-user-menu');
    const postBtn = document.getElementById('nav-post-btn');
    if (!authBtns && !userMenu) return;
    if (this.user) {
      authBtns && (authBtns.style.display = 'none');
      userMenu && (userMenu.style.display = 'flex');
      postBtn && (postBtn.style.display = 'flex');
      const avatarEl = document.getElementById('nav-avatar');
      if (avatarEl) avatarEl.textContent = this.user.name.charAt(0).toUpperCase();
    } else {
      authBtns && (authBtns.style.display = 'flex');
      userMenu && (userMenu.style.display = 'none');
      postBtn && (postBtn.style.display = 'none');
    }
  },
  async updateUnreadBadge() {
    if (!this.user) return;
    try {
      const data = await API.get('/api/unread-count');
      const badge = document.getElementById('unread-badge');
      if (badge) {
        badge.textContent = data.count;
        badge.style.display = data.count > 0 ? 'flex' : 'none';
      }
    } catch (e) {}
  },
  requireAuth() {
    if (!this.user) {
      window.location.href = '/login.html?redirect=' + encodeURIComponent(window.location.pathname);
      return false;
    }
    return true;
  }
};

// Utility functions
const Utils = {
  formatPrice: (p) => '₹' + Number(p).toLocaleString('en-IN'),
  formatDate: (d) => {
    const date = new Date(d);
    const now = new Date();
    const diff = Math.floor((now - date) / 1000);
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff/60) + 'm ago';
    if (diff < 86400) return Math.floor(diff/3600) + 'h ago';
    if (diff < 604800) return Math.floor(diff/86400) + 'd ago';
    return date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
  },
  categoryIcon: {
    'Electronics': '📱', 'Furniture': '🪑', 'Clothing': '👕', 'Books': '📚',
    'Vehicles': '🚗', 'Sports': '⚽', 'Home & Garden': '🏡', 'Toys': '🧸',
    'Music': '🎵', 'Other': '📦'
  },
  conditionClass: { 'Excellent': 'cond-excellent', 'Good': 'cond-good', 'Fair': 'cond-fair', 'Poor': 'cond-poor' },
  truncate: (str, n) => str.length > n ? str.slice(0, n) + '...' : str,
  getParam: (key) => new URLSearchParams(window.location.search).get(key),
  escapeHtml: (str) => {
    const d = document.createElement('div');
    d.appendChild(document.createTextNode(str));
    return d.innerHTML;
  }
};

// Product card renderer
function renderProductCard(product, wishlisted = false) {
  const img = product.primary_image || product.images?.[0] || 'placeholder.jpg';
  const imgSrc = img.startsWith('http') ? img : `/uploads/${img}`;
  const badge = !product.is_available ? '<span class="product-badge sold">Sold</span>' : '';
  const wClass = wishlisted ? 'active' : '';
  return `
    <div class="product-card" onclick="location.href='/product.html?id=${product.id}'">
      <div class="product-img-wrap">
        <img src="${imgSrc}" alt="${Utils.escapeHtml(product.title)}" loading="lazy" onerror="this.src='/static/images/placeholder.jpg'">
        ${badge}
        <button class="wishlist-btn ${wClass}" data-id="${product.id}" onclick="event.stopPropagation(); toggleWishlist(this, ${product.id})">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="${wClass ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2">
            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
          </svg>
        </button>
      </div>
      <div class="product-info">
        <h3>${Utils.escapeHtml(product.title)}</h3>
        <div class="product-price">${Utils.formatPrice(product.price)}</div>
        <div class="product-meta">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
          ${Utils.escapeHtml(product.location)}
          <span>•</span>
          ${Utils.formatDate(product.created_at)}
        </div>
      </div>
    </div>`;
}

async function toggleWishlist(btn, productId) {
  if (!App.requireAuth()) return;
  try {
    const data = await API.post(`/api/wishlist/${productId}`);
    const isActive = data.in_wishlist;
    btn.classList.toggle('active', isActive);
    btn.querySelector('svg').setAttribute('fill', isActive ? 'currentColor' : 'none');
    Toast.success(data.message);
  } catch (e) {
    Toast.error(e.message);
  }
}

// Logout handler
async function logout() {
  try {
    await API.post('/api/logout');
    App.user = null;
    Toast.success('Logged out');
    setTimeout(() => window.location.href = '/', 800);
  } catch (e) {
    Toast.error('Logout failed');
  }
}

window.addEventListener('DOMContentLoaded', () => App.init());
