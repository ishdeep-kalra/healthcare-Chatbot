/**
 * Centralized API configuration.
 *
 * In LOCAL DEV:  VITE_API_BASE_URL is empty string → Vite dev proxy handles /api → localhost:8000
 * In PRODUCTION: VITE_API_BASE_URL env var set in Vercel dashboard (preferred), OR
 *                falls back to the hardcoded Render URL so the app works even if the
 *                Vercel env var is missing.
 */
const RENDER_BACKEND = "https://healthcare-chatbot-q84v.onrender.com";

// import.meta.env.VITE_API_BASE_URL is:
//   - undefined  → not set at all (Vercel build without env var) → use Render URL
//   - ""         → explicitly set to empty (local dev, proxy mode) → keep empty
//   - "https://…" → set to a real URL → use it
const envUrl = import.meta.env.VITE_API_BASE_URL;
export const API_BASE_URL =
  envUrl === undefined ? RENDER_BACKEND :   // Vercel build, env var not configured
  envUrl === ""        ? ""              :   // Local dev: Vite proxy handles routing
  envUrl;                                   // Explicit URL from Vercel env var

export const API_ENDPOINTS = {
  chat:     `${API_BASE_URL}/api/chat`,
  retrieve: `${API_BASE_URL}/api/chat/retrieve`,
  upload:   `${API_BASE_URL}/api/documents/upload`,
  health:   `${API_BASE_URL}/health`,
};
