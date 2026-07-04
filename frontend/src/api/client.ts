import axios from "axios";

/** Shared Axios instance used by every domain service file in src/api/. */
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: Number(import.meta.env.VITE_API_TIMEOUT_MS),
  headers: {
    "Content-Type": "application/json",
  },
});
