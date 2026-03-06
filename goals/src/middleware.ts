import { NextRequest, NextResponse } from 'next/server'

export function middleware(request: NextRequest) {
  // Check if accessing a protected route
  if (request.nextUrl.pathname.startsWith('/dashboard')) {
    const sessionToken = request.cookies.get('session_token')

    if (!sessionToken) {
      return NextResponse.redirect(new URL('/login', request.url))
    }
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/dashboard/:path*'],
}
