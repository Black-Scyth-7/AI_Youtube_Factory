/** Lightweight, dependency-free validation helpers. */

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const URL_RE = /^https?:\/\/[^\s/$.?#].[^\s]*$/i;

/** Validate an email address shape (not deliverability). */
export function isEmail(value: string): boolean {
  return EMAIL_RE.test(value);
}

/** Validate an http(s) URL shape. */
export function isHttpUrl(value: string): boolean {
  return URL_RE.test(value);
}

/** Validate a YouTube-style slug/handle (letters, digits, _, -, .). */
export function isHandle(value: string): boolean {
  return /^[A-Za-z0-9_.-]{1,64}$/.test(value);
}
