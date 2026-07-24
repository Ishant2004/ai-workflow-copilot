/**
 * Frontend runtime config.
 *
 * No hardcoded URLs: the API base comes from `NEXT_PUBLIC_API_BASE_URL`
 * (set per environment via .env.development / .env.production), with a sane
 * local default. `NEXT_PUBLIC_*` vars are inlined at build time by Next.js.
 */
export const config = {
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000",
} as const;
