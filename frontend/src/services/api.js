/**
 * Centralized API client for the Restaurant Management System.
 * Respects VITE_API_BASE_URL if set, or falls back to relative paths for Vite proxy.
 */

const RAW_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  import.meta.env.VITE_API_URL ||
  '';
export const API_BASE_URL = RAW_BASE_URL.replace(/\/+$/, '');

const TOKEN_STORAGE_KEY = 'brew_access_token';
const CSRF_STORAGE_KEY = 'brew_csrf_token';

// Persistent token storage with in-memory fast access for cross-origin production deployments
let inMemoryToken = null;
let inMemoryCsrfToken = null;

try {
  if (typeof window !== 'undefined' && window.localStorage) {
    inMemoryToken = window.localStorage.getItem(TOKEN_STORAGE_KEY);
    inMemoryCsrfToken = window.localStorage.getItem(CSRF_STORAGE_KEY);
  }
} catch {
  // Graceful degradation when localStorage is restricted
}

export function setAuthToken(token) {
  inMemoryToken = token;
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      if (token) {
        window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
      } else {
        window.localStorage.removeItem(TOKEN_STORAGE_KEY);
      }
    }
  } catch {
    // Graceful degradation
  }
}

export function getAuthToken() {
  if (inMemoryToken) return inMemoryToken;
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      inMemoryToken = window.localStorage.getItem(TOKEN_STORAGE_KEY);
    }
  } catch {
    // Graceful degradation
  }
  return inMemoryToken;
}

export function setCsrfToken(token) {
  inMemoryCsrfToken = token;
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      if (token) {
        window.localStorage.setItem(CSRF_STORAGE_KEY, token);
      } else {
        window.localStorage.removeItem(CSRF_STORAGE_KEY);
      }
    }
  } catch {
    // Graceful degradation
  }
}

export function getCsrfToken() {
  if (inMemoryCsrfToken) return inMemoryCsrfToken;
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      inMemoryCsrfToken = window.localStorage.getItem(CSRF_STORAGE_KEY);
      if (inMemoryCsrfToken) return inMemoryCsrfToken;
    }
  } catch {
    // Graceful degradation
  }
  if (typeof document !== 'undefined') {
    const match = document.cookie.match(/(?:^|;\s*)restaurant_csrf_token=([^;]+)/);
    if (match) return decodeURIComponent(match[1]);
  }
  return null;
}

/**
 * Universal request helper with error handling for FastAPI responses.
 */
async function request(path, options = {}) {
  const url = `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
  
  const headers = {
    Accept: 'application/json',
    ...options.headers,
  };

  // Attach persistent/in-memory bearer token if present
  const token = getAuthToken();
  if (token && !headers.Authorization) {
    headers.Authorization = `Bearer ${token}`;
  }

  // Attach CSRF token on state-changing requests (POST, PUT, DELETE, PATCH)
  const method = (options.method || 'GET').toUpperCase();
  if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
    const csrf = getCsrfToken();
    if (csrf && !headers['X-CSRF-Token']) {
      headers['X-CSRF-Token'] = csrf;
    }
  }

  if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(options.body);
  }

  try {
    // credentials: 'include' ensures HttpOnly session cookies are transmitted
    const response = await fetch(url, {
      credentials: 'include',
      ...options,
      headers,
    });
    
    // 204 No Content
    if (response.status === 204) {
      return null;
    }

    const contentType = response.headers.get('content-type') || '';
    const isJson = contentType.includes('application/json');
    const data = isJson ? await response.json() : await response.text();

    // Guard against SPA catch-all rewrites returning HTML index instead of JSON API response
    if (
      !isJson &&
      typeof data === 'string' &&
      (data.trim().startsWith('<!doctype html') || data.trim().startsWith('<html'))
    ) {
      const htmlError = new Error(
        `Received HTML instead of JSON from '${path}'. Please verify the backend API URL is configured correctly.`
      );
      htmlError.status = response.status === 200 ? 502 : response.status;
      htmlError.data = data;
      throw htmlError;
    }

    if (!response.ok) {
      const errorMsg =
        (data && typeof data === 'object' && data.detail) ||
        `Request failed with status ${response.status} (${response.statusText})`;
      const error = new Error(errorMsg);
      error.status = response.status;
      error.data = data;
      throw error;
    }

    return data;
  } catch (err) {
    if (err.name === 'TypeError' && err.message.includes('fetch')) {
      const networkError = new Error('Cannot reach server. Please ensure the backend is running.');
      networkError.status = 0;
      throw networkError;
    }
    throw err;
  }
}

/**
 * Health check endpoints
 */
export async function getHealth() {
  return request('/health');
}

export async function getDbHealth() {
  return request('/health/db');
}

/**
 * Public Menu API endpoint (Unauthenticated customer storefront)
 * @param {Object} [params] - Optional query parameters
 * @param {number} [params.categoryId] - Filter by category ID
 * @param {string} [params.search] - Search by item name or description
 */
export async function getPublicMenu({ categoryId, search } = {}) {
  const searchParams = new URLSearchParams();
  if (categoryId !== undefined && categoryId !== null && categoryId !== '') {
    searchParams.append('category_id', categoryId);
  }
  if (search && search.trim()) {
    searchParams.append('search', search.trim());
  }
  const queryString = searchParams.toString();
  return request(`/api/public/menu${queryString ? `?${queryString}` : ''}`);
}

/**
 * Category API endpoints
 */
export async function getCategories() {
  return request('/api/categories');
}

/**
 * Menu Item API endpoints
 * @param {Object} [params] - Optional query parameters
 * @param {number} [params.categoryId] - Filter by category ID
 * @param {boolean} [params.isAvailable] - Filter by availability
 */
export async function getMenuItems({ categoryId, isAvailable } = {}) {
  const searchParams = new URLSearchParams();
  if (categoryId !== undefined && categoryId !== null && categoryId !== '') {
    searchParams.append('category_id', categoryId);
  }
  if (isAvailable !== undefined && isAvailable !== null && isAvailable !== '') {
    searchParams.append('is_available', isAvailable);
  }

  const queryString = searchParams.toString();
  const endpoint = `/api/menu-items${queryString ? `?${queryString}` : ''}`;
  return request(endpoint);
}

/**
 * Restaurant Tables endpoints
 * @param {string} [status] - Optional table status filter: 'available', 'occupied', 'reserved'
 */
export async function getTables(status) {
  const query = status && status !== 'all' ? `?status=${encodeURIComponent(status)}` : '';
  return request(`/api/tables${query}`);
}

/**
 * Order endpoints
 */

/**
 * Retrieve a single order by ID.
 * @param {number} orderId - Primary key ID of the order
 */
export async function getOrder(orderId) {
  return request(`/api/orders/${orderId}`);
}

/**
 * Create a new order with items.
 * @param {Object} orderData
 * @param {number|null} [orderData.table_id]
 * @param {Array<{menu_item_id: number, quantity: number, special_instructions?: string}>} orderData.items
 * @param {number|string} [orderData.discount]
 */
export async function createOrder(orderData) {
  return request('/api/orders', {
    method: 'POST',
    body: orderData,
  });
}

/**
 * List orders with optional filters.
 * @param {Object} [params]
 * @param {string} [params.status]
 * @param {number} [params.tableId]
 */
export async function getOrders({ status, tableId } = {}) {
  const searchParams = new URLSearchParams();
  if (status && status !== 'all') {
    searchParams.append('status', status);
  }
  if (tableId !== undefined && tableId !== null && tableId !== '') {
    searchParams.append('table_id', tableId);
  }
  const queryString = searchParams.toString();
  return request(`/api/orders${queryString ? `?${queryString}` : ''}`);
}

/**
 * Update an existing order (status transition, table reassignment, or discount).
 * @param {number} orderId - Primary key ID of the order to update
 * @param {Object} updateData - Partial update payload
 * @param {string} [updateData.status] - New order status (e.g. 'in_progress', 'served', 'completed', 'cancelled')
 * @param {number|null} [updateData.table_id] - New table ID or null for takeaway
 * @param {number|string} [updateData.discount] - Updated discount
 */
export async function updateOrder(orderId, updateData) {
  return request(`/api/orders/${orderId}`, {
    method: 'PUT',
    body: updateData,
  });
}

/**
 * Authentication endpoints
 */

/**
 * Log in with username/email and password.
 * Backend sets an HttpOnly cookie and returns signed token with user profile.
 *
 * @param {Object} credentials
 * @param {string} credentials.username
 * @param {string} credentials.password
 */
export async function loginUser({ username, password }) {
  const result = await request('/api/auth/login', {
    method: 'POST',
    body: { username, password },
  });
  if (result && result.access_token) {
    setAuthToken(result.access_token);
  }
  if (result && result.csrf_token) {
    setCsrfToken(result.csrf_token);
  }
  return result;
}

/**
 * Retrieve current authenticated user profile.
 */
export async function getCurrentUser() {
  try {
    return await request('/api/auth/me');
  } catch (err) {
    if (err.status === 401) {
      setAuthToken(null);
      setCsrfToken(null);
    }
    throw err;
  }
}

/**
 * Log out and clear session cookie on server.
 */
export async function logoutUser() {
  try {
    await request('/api/auth/logout', { method: 'POST' });
  } finally {
    setAuthToken(null);
    setCsrfToken(null);
  }
}

/**
 * User Management endpoints (Admin only)
 */

export async function getUsers() {
  return request('/api/users');
}

export async function createUser(userData) {
  return request('/api/users', {
    method: 'POST',
    body: userData,
  });
}

export async function updateUser(userId, userData) {
  return request(`/api/users/${userId}`, {
    method: 'PUT',
    body: userData,
  });
}

export async function deleteUser(userId) {
  return request(`/api/users/${userId}`, {
    method: 'DELETE',
  });
}

/**
 * Inventory Management Endpoints (Phase 20)
 */

export async function getInventorySummary() {
  return request('/api/inventory/dashboard-summary');
}

export async function getIngredients(params = {}) {
  const query = new URLSearchParams();
  if (params.search) query.set('search', params.search);
  if (params.stock_status) query.set('stock_status', params.stock_status);
  if (params.is_active !== undefined) query.set('is_active', params.is_active);
  const qs = query.toString();
  return request(`/api/inventory/ingredients${qs ? `?${qs}` : ''}`);
}

export async function getIngredient(id) {
  return request(`/api/inventory/ingredients/${id}`);
}

export async function createIngredient(data) {
  return request('/api/inventory/ingredients', {
    method: 'POST',
    body: data,
  });
}

export async function updateIngredient(id, data) {
  return request(`/api/inventory/ingredients/${id}`, {
    method: 'PUT',
    body: data,
  });
}

export async function deleteIngredient(id) {
  return request(`/api/inventory/ingredients/${id}`, {
    method: 'DELETE',
  });
}

export async function adjustIngredientStock(id, data) {
  return request(`/api/inventory/ingredients/${id}/adjust`, {
    method: 'POST',
    body: data,
  });
}

export async function getStockMovements(params = {}) {
  const query = new URLSearchParams();
  if (params.ingredient_id) query.set('ingredient_id', params.ingredient_id);
  if (params.movement_type) query.set('movement_type', params.movement_type);
  if (params.limit) query.set('limit', params.limit);
  if (params.offset) query.set('offset', params.offset);
  const qs = query.toString();
  return request(`/api/inventory/movements${qs ? `?${qs}` : ''}`);
}

export async function getRecipes(params = {}) {
  const query = new URLSearchParams();
  if (params.category_id) query.set('category_id', params.category_id);
  const qs = query.toString();
  return request(`/api/inventory/recipes${qs ? `?${qs}` : ''}`);
}

export async function getMenuItemRecipe(menuItemId) {
  return request(`/api/inventory/recipes/menu-item/${menuItemId}`);
}

export async function createRecipeItem(data) {
  return request('/api/inventory/recipes', {
    method: 'POST',
    body: data,
  });
}

export async function deleteRecipeItem(id) {
  return request(`/api/inventory/recipes/${id}`, {
    method: 'DELETE',
  });
}

/**
 * QR Table Ordering — Public Endpoints (No Authentication Required)
 */

/**
 * Validate a table QR token and retrieve table info.
 * @param {string} qrToken - The QR ordering token from the scanned URL
 */
export async function getQRTableInfo(qrToken) {
  return request(`/api/public/table/${encodeURIComponent(qrToken)}`);
}

/**
 * Create a dine-in order via QR code (no auth, no CSRF).
 * @param {Object} orderData
 * @param {string} orderData.qr_token
 * @param {Array<{menu_item_id: number, quantity: number, special_instructions?: string}>} orderData.items
 * @param {string} orderData.idempotency_key - Client-generated UUID
 * @param {string} [orderData.customer_name]
 */
export async function createQROrder(orderData) {
  return request('/api/public/orders', {
    method: 'POST',
    body: orderData,
  });
}

/**
 * Check real-time status of a QR table order.
 * @param {string} orderNumber - Order ticket number (e.g. ORD-20261029-AB12CD)
 * @param {string} qrToken - Active table QR token for ownership verification
 */
export async function getQROrderStatus(orderNumber, qrToken) {
  return request(`/api/public/orders/${encodeURIComponent(orderNumber)}?qr_token=${encodeURIComponent(qrToken)}`);
}

/**
 * QR Table Management — Staff Endpoints (Authentication Required)
 */

/**
 * Generate or rotate a QR ordering token for a table.
 * @param {number} tableId - Primary key ID of the table
 */
export async function generateQRToken(tableId) {
  return request(`/api/tables/${tableId}/qr-token`, {
    method: 'POST',
  });
}

/**
 * Retrieve the currently active QR token for a table.
 * @param {number} tableId
 */
export async function getQRToken(tableId) {
  return request(`/api/tables/${tableId}/qr-token`);
}

/**
 * Revoke (deactivate) the QR ordering token for a table.
 * @param {number} tableId
 */
export async function revokeQRToken(tableId) {
  return request(`/api/tables/${tableId}/qr-token`, {
    method: 'DELETE',
  });
}

// ── Razorpay Payment Gateway Endpoints ─────────────────────────────────────

/**
 * Retrieve public Razorpay configuration (key ID, currency).
 */
export async function getPublicPaymentConfig() {
  return request('/api/public/payments/config');
}

/**
 * Create a Razorpay payment order for a guest order.
 * @param {Object} payload - { order_number, qr_token, idempotency_key }
 */
export async function createGuestPaymentOrder(payload) {
  return request('/api/public/payments/create-order', {
    method: 'POST',
    body: payload,
  });
}

/**
 * Verify payment signature returned from Razorpay modal.
 * @param {Object} payload - { order_number, qr_token, razorpay_order_id, razorpay_payment_id, razorpay_signature }
 */
export async function verifyGuestPayment(payload) {
  return request('/api/public/payments/verify', {
    method: 'POST',
    body: payload,
  });
}

/**
 * Get guest payment status for an order.
 * @param {string} orderNumber
 * @param {string} qrToken
 */
export async function getGuestPaymentStatus(orderNumber, qrToken) {
  const query = qrToken ? `?qr_token=${encodeURIComponent(qrToken)}` : '';
  return request(`/api/public/orders/${encodeURIComponent(orderNumber)}/payment${query}`);
}

/**
 * Get payment audit history for an order (staff authorized).
 * @param {number} orderId
 */
export async function getOrderPaymentsStaff(orderId) {
  return request(`/api/orders/${orderId}/payments`);
}

/**
 * Settle an order with cash at the counter (staff authorized).
 * @param {number} orderId
 */
export async function settleOrderCashStaff(orderId) {
  return request(`/api/orders/${orderId}/settle-cash`, {
    method: 'POST',
  });
}

