/**
 * API Constants
 * Centralized API endpoint paths matching the backend routes.
 *
 * NOTE: These are path fragments (relative URLs).
 * Use with apiFetch() which adds BASE_URL automatically.
 *
 * Last Updated: 2026-01-16
 * Backend Version: 1.2.0
 *
 * @module utils/apis/constants
 */

// ============================================================================
// Authentication Endpoints (/api/auth/*)
// ============================================================================
export const API_AUTH = {
  LOGIN: '/api/auth/login',
  LOGOUT: '/api/auth/logout',
  REFRESH: '/api/auth/refresh',
  TOKEN: '/api/auth/token',
  VALIDATE: '/api/auth/validate',
  SIGNUP: '/api/auth/signup',
  SIGNUP_USER: (accountKey) => `/api/auth/account/${accountKey}/signup`,
  ME: '/api/auth/me',
  PERMISSIONS: '/api/auth/permissions',
  SETTINGS: '/api/auth/settings',
  SUBSCRIPTIONS: '/api/auth/subscriptions',
  ACCOUNT_USERS: '/api/auth/account/users',
  COMPANY: (accountKey) => `/api/auth/account/${accountKey}/company`,
};

// ============================================================================
// User Endpoints (/api/user/*)
// ============================================================================
export const API_USER = {
  BASE: '/api/user',
  ME: '/api/user/me',
  LIST: '/api/user/list',
  PROFILE: '/api/user/profile',
  CREATE: '/api/user/',
  DETAIL: (userId) => `/api/user/${userId}`,
  UPDATE: (userId) => `/api/user/${userId}`,
  DELETE: (userId) => `/api/user/${userId}`,
  PASSWORD: '/api/user/password',
  LOGOUT: '/api/user/logout',
  SETTINGS: '/api/user/settings',
  SETTINGS_NOTIFICATIONS: '/api/user/settings/notifications',
  SETTINGS_HELP: '/api/user/settings/help_support',
};

// ============================================================================
// Task Endpoints (/api/task/*)
// ============================================================================
export const API_TASK = {
  BASE: '/api/task',
  LIST: '/api/task/',
  CREATE: '/api/task/',
  DETAIL: (taskId) => `/api/task/${taskId}`,
  UPDATE: (taskId) => `/api/task/${taskId}`,
  DELETE: (taskId) => `/api/task/${taskId}`,
  MOVE: (taskId) => `/api/task/${taskId}/move`,
  BY_POND: (pondId) => `/api/task/pond/${pondId}`,
  BY_USER: (userKey) => `/api/task/user/${userKey}`,
};

// ============================================================================
// Pond Endpoints (/api/pond/*)
// ============================================================================
export const API_POND = {
  BASE: '/api/pond',
  LIST: '/api/pond/',
  CREATE: '/api/pond/create',
  DETAIL: (pondId) => `/api/pond/${pondId}`,
  UPDATE: (pondId) => `/api/pond/${pondId}`,
  DELETE: (pondId) => `/api/pond/${pondId}`,
  DAILY_UPDATE: (pondId) => `/api/pond/${pondId}/daily`,
  STOCK: (pondId) => `/api/pond/${pondId}/stock`,
  HARVEST: (pondId) => `/api/pond/${pondId}/harvest`,
  TRANSFER: (pondId) => `/api/pond/${pondId}/transfer`,
  STATS: (pondId) => `/api/pond/${pondId}/stats`,
};

// ============================================================================
// Pond Event Endpoints (/api/pond_event/*)
// ============================================================================
export const API_POND_EVENT = {
  BASE: '/api/pond_event',
  LIST: '/api/pond_event/',
  CREATE: '/api/pond_event/',
  DETAIL: (eventId) => `/api/pond_event/${eventId}`,
  UPDATE: (eventId) => `/api/pond_event/${eventId}`,
  DELETE: (eventId) => `/api/pond_event/${eventId}`,
  BY_POND: (pondId) => `/api/pond_event/pond/${pondId}`,
};

// ============================================================================
// Fish Endpoints (/api/fish/*)
// ============================================================================
export const API_FISH = {
  BASE: '/api/fish',
  LIST: '/api/fish/',
  CREATE: '/api/fish/create',
  DETAIL: (fishId) => `/api/fish/${fishId}`,
  UPDATE: (fishId) => `/api/fish/${fishId}`,
  ANALYTICS: '/api/fish/analytics',
  ANALYTICS_BY_SPECIES: (speciesId) => `/api/fish/${speciesId}/analytics`,
  FIELDS: '/api/fish/fields',
  DISTINCT: (field) => `/api/fish/distinct/${field}`,
  STATS: (field) => `/api/fish/stats/${field}`,
};

// ============================================================================
// Sampling Endpoints (/api/sampling/*)
// ============================================================================
export const API_SAMPLING = {
  BASE: '/api/sampling',
  LIST: '/api/sampling/',
  CREATE: '/api/sampling/',
  DETAIL: (samplingId) => `/api/sampling/${samplingId}`,
  UPDATE: (samplingId) => `/api/sampling/${samplingId}`,
  DELETE: (samplingId) => `/api/sampling/${samplingId}`,
  BUY: '/api/sampling/buy',
  BY_POND: (pondId) => `/api/sampling/pond/${pondId}`,
};

// ============================================================================
// Feeding Endpoints (/api/feeding/*)
// ============================================================================
export const API_FEEDING = {
  BASE: '/api/feeding',
  LIST: '/api/feeding/',
  CREATE: '/api/feeding/',
  BY_POND: (pondId) => `/api/feeding/pond/${pondId}`,
};

// ============================================================================
// Company Endpoints (/api/company/*)
// ============================================================================
export const API_COMPANY = {
  BASE: '/api/company',
  REGISTER: '/api/company/register',
  DETAIL: (accountKey) => `/api/company/${accountKey}`,
  UPDATE: (accountKey) => `/api/company/${accountKey}`,
  PUBLIC: (accountKey) => `/api/company/public/${accountKey}`,
  USERS: (accountKey) => `/api/company/${accountKey}/users`,
  DELETE_USER: (accountKey, userKey) => `/api/company/${accountKey}/users/${userKey}`,
};

// ============================================================================
// Expense Endpoints (/api/expenses/*)
// ============================================================================
export const API_EXPENSE = {
  BASE: '/api/expenses',
  LIST: '/api/expenses/',
  CREATE: '/api/expenses/',
  DETAIL: (expenseId) => `/api/expenses/${expenseId}`,
  UPDATE: (expenseId) => `/api/expenses/${expenseId}`,
  DELETE: (expenseId) => `/api/expenses/${expenseId}`,
  PAY: (expenseId) => `/api/expenses/${expenseId}/pay`,
  APPROVE: (expenseId) => `/api/expenses/${expenseId}/approve`,
  REJECT: (expenseId) => `/api/expenses/${expenseId}/reject`,
  CANCEL: (expenseId) => `/api/expenses/${expenseId}/cancel`,
  CATEGORIES: '/api/expenses/categories',
  CATEGORIES_TOP: '/api/expenses/categories/top',
  CATEGORIES_OPTIONS: '/api/expenses/categories/options',
  CATEGORIES_SUBCATEGORIES: '/api/expenses/categories/subcategories',
  CATEGORIES_VALIDATE: '/api/expenses/categories/validate',
  CATEGORIES_SEARCH: '/api/expenses/categories/search',
  CATEGORIES_SUGGEST: '/api/expenses/categories/suggest',
  SUMMARY: '/api/expenses/summary',
  BY_POND: (pondId) => `/api/expenses/by-pond/${pondId}`,
  TRANSACTIONS: '/api/expenses/transactions',
  PAYMENTS: '/api/expenses/payments',
  PAYMENT_DETAIL: (paymentId) => `/api/expenses/payments/${paymentId}`,
  BANK_IMPORT: '/api/expenses/bank_statements/import',
  RECONCILE: '/api/expenses/reconcile/by-external',
};

// ============================================================================
// Transaction Endpoints (/api/transactions/*)
// ============================================================================
export const API_TRANSACTION = {
  BASE: '/api/transactions',
  LIST: '/api/transactions/',
  CREATE: '/api/transactions/',
  DETAIL: (txId) => `/api/transactions/${txId}`,
  UPDATE: (txId) => `/api/transactions/${txId}`,
  DELETE: (txId) => `/api/transactions/${txId}`,
};

// ============================================================================
// Dashboard Endpoints (/api/dashboard/*)
// ============================================================================
export const API_DASHBOARD = {
  BASE: '/api/dashboard',
  GET: '/api/dashboard/',
  ALERTS: '/api/dashboard/alerts',
  ACKNOWLEDGE_ALERT: (alertId) => `/api/dashboard/alerts/${alertId}/acknowledge`,
};

// ============================================================================
// Role Endpoints (/api/role/*)
// ============================================================================
export const API_ROLE = {
  BASE: '/api/role',
  LIST: '/api/role/',
  CREATE: '/api/role/',
  DETAIL: (roleCode) => `/api/role/${roleCode}`,
  UPDATE: (roleCode) => `/api/role/${roleCode}`,
  DELETE: (roleCode) => `/api/role/${roleCode}`,
  PERMISSIONS: (roleCode) => `/api/role/${roleCode}/permissions`,
};

// ============================================================================
// Permission Endpoints (/api/permission/*)
// ============================================================================
export const API_PERMISSION = {
  BASE: '/api/permission',
  MY: '/api/permission/my',
  USER: (userKey) => `/api/permission/user/${userKey}`,
  USER_OVERRIDES: (userKey) => `/api/permission/user/${userKey}/overrides`,
  CHECK: '/api/permission/check',
  GRANT: '/api/permission/grant',
  REVOKE: '/api/permission/revoke',
  SET: '/api/permission/set',
  SET_BULK: '/api/permission/set-bulk',
  ASSIGN_PONDS: '/api/permission/assign-ponds',
  MY_PONDS: '/api/permission/my-ponds',
  TEMPLATE: '/api/permission/template',
  ROLES: '/api/permission/roles',
  ROLE: (role) => `/api/permission/role/${role}`,
};

// ============================================================================
// AI / OpenAI Endpoints (/api/ai/*)
// ============================================================================
export const API_AI = {
  CHAT: '/api/ai/chat',
  QUERY: '/api/ai/query',
};

// ============================================================================
// Notification Endpoints (/api/notification/*)
// ============================================================================
export const API_NOTIFICATION = {
  BASE: '/api/notification',
  LIST: '/api/notification/',
  CREATE: '/api/notification/',
  DETAIL: (notificationId) => `/api/notification/${notificationId}`,
  MARK_READ: (notificationId) => `/api/notification/${notificationId}/read`,
  MARK_ALL_READ: '/api/notification/read-all',
  DELETE: (notificationId) => `/api/notification/${notificationId}`,
  BROADCAST: '/api/notification/broadcast',
  // Alert endpoints
  ALERT_LIST: '/api/notification/alert/',
  ALERT_CREATE: '/api/notification/alert/',
  ALERT_DETAIL: (alertId) => `/api/notification/alert/${alertId}`,
  ALERT_ACKNOWLEDGE: (alertId) => `/api/notification/alert/${alertId}/acknowledge`,
  ALERT_DELETE: (alertId) => `/api/notification/alert/${alertId}`,
};

// ============================================================================
// Public Endpoints (/api/public/*)
// ============================================================================
export const API_PUBLIC = {
  BASE: '/api/public',
};

// ============================================================================
// Legacy exports for backward compatibility
// ============================================================================
export const AUTH_LOGIN = API_AUTH.LOGIN;
export const AUTH_LOGOUT = API_AUTH.LOGOUT;
export const AUTH_REFRESH_TOKEN = API_AUTH.REFRESH;
export const AUTH_VALIDATE_TOKEN = API_AUTH.VALIDATE;
export const AUTH_ME = API_AUTH.ME;
export const AUTH_PERMISSIONS = API_AUTH.PERMISSIONS;
export const AUTH_SIGNUP = API_AUTH.SIGNUP;

export const PATH_USER_LIST = API_USER.LIST;
export const PATH_USER_PROFILE = API_USER.PROFILE;
export const PATH_USER_ME = API_USER.ME;

export const COMPANY_REGISTER = API_COMPANY.REGISTER;

// ============================================================================
// Helper function to build full URL
// ============================================================================
export const buildUrl = (baseUrl, path) => {
  const base = baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl;
  const pathStr = path.startsWith('/') ? path : `/${path}`;
  return `${base}${pathStr}`;
};

// ============================================================================
// Default export with all API groups
// ============================================================================
export default {
  AUTH: API_AUTH,
  USER: API_USER,
  TASK: API_TASK,
  POND: API_POND,
  POND_EVENT: API_POND_EVENT,
  FISH: API_FISH,
  SAMPLING: API_SAMPLING,
  FEEDING: API_FEEDING,
  COMPANY: API_COMPANY,
  EXPENSE: API_EXPENSE,
  TRANSACTION: API_TRANSACTION,
  DASHBOARD: API_DASHBOARD,
  ROLE: API_ROLE,
  PERMISSION: API_PERMISSION,
  NOTIFICATION: API_NOTIFICATION,
  AI: API_AI,
  PUBLIC: API_PUBLIC,
};

