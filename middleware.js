import { NextResponse } from 'next/server';

const TARGET_ORIGIN='https://mus-ai-probe-ghi7lelnj-india123445t-pixel.vercel.app';

export function middleware(request){
  const target=new URL(request.nextUrl.pathname+request.nextUrl.search,TARGET_ORIGIN);
  return NextResponse.redirect(target,307);
}

export const config={
  matcher:'/:path*'
};

// production-router-v3 -> verified Workspace + Owner Core V3 integration (ebf674456f16d0965c2577ef4863b98a4633ee2b)
