/**
 * Centralized API configuration.
 *
 * In LOCAL DEV:  VITE_API_BASE_URL is empty → Vite proxy routes /api → localhost:8000
 * In PRODUCTION: VITE_API_BASE_URL = "https://healthcare-chatbot-q84v.onrender.com"
 *                (set via Vercel environment variable)
 */
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

export const API_ENDPOINTS = {
  chat:     `${API_BASE_URL}/api/chat`,
  retrieve: `${API_BASE_URL}/api/chat/retrieve`,
  upload:   `${API_BASE_URL}/api/documents/upload`,
  health:   `${API_BASE_URL}/health`,
};
