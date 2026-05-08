import { cookies } from 'next/headers'
import crypto from 'crypto'

const SESSION_COOKIE_NAME = 'session_token'
const SESSION_SECRET = process.env.SESSION_SECRET || 'dev-secret-change-in-production'

/** Generate a fresh random 64-char hex session token. */
export async function createSessionToken(): Promise<string> {
  const token = crypto.randomBytes(32).toString('hex')
  return token
}

/** Persist a session token in the httpOnly session cookie (30-day max age). */
export async function setSessionCookie(token: string): Promise<void> {
  const cookieStore = await cookies()
  cookieStore.set(SESSION_COOKIE_NAME, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    maxAge: 60 * 60 * 24 * 30, // 30 days
    path: '/',
  })
}

/** Read the current session token from cookies, or null if absent. */
export async function getSessionToken(): Promise<string | null> {
  const cookieStore = await cookies()
  const token = cookieStore.get(SESSION_COOKIE_NAME)
  return token?.value || null
}

/** Remove the session cookie, effectively logging the user out. */
export async function clearSessionCookie(): Promise<void> {
  const cookieStore = await cookies()
  cookieStore.delete(SESSION_COOKIE_NAME)
}

/** Returns true when a session token is present in cookies. */
export async function verifySession(): Promise<boolean> {
  const token = await getSessionToken()
  return !!token
}
