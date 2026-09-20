import { NextResponse } from 'next/server';

const TARGET_ORIGIN='https://mus-ai-probe-git-agent-01-owner-core-311e26-india123445t-pixel.vercel.app';

export function middleware(request){
  const target=new URL(request.nextUrl.pathname+request.nextUrl.search,TARGET_ORIGIN);
  return NextResponse.redirect(target,307);
}

export const config={
  matcher:'/:path*'
};
