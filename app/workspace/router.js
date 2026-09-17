'use client';

import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

const RouterCtx = createContext({ pathname: '/chat', search: '', navigate: () => {} });

function readLocation() {
  if (typeof window === 'undefined') return { pathname: '/chat', search: '' };
  return { pathname: window.location.pathname || '/chat', search: window.location.search || '' };
}

function normalizeTarget(to, pathname) {
  if (!to) return pathname || '/chat';
  if (to.startsWith('/')) return to;
  const current = pathname || '/chat';
  if (current.startsWith('/settings/')) {
    if (to.startsWith('../')) return '/settings/' + to.replace(/^\.\.\//, '');
    return '/settings/' + to.replace(/^\.\//, '');
  }
  const parts = current.split('/').filter(Boolean);
  if (!current.endsWith('/')) parts.pop();
  for (const seg of to.split('/')) {
    if (!seg || seg === '.') continue;
    if (seg === '..') parts.pop(); else parts.push(seg);
  }
  return '/' + parts.join('/');
}

export function BrowserRouter({ children }) {
  const [loc, setLoc] = useState(() => readLocation());
  useEffect(() => {
    setLoc(readLocation());
    const onPop = () => setLoc(readLocation());
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);
  const navigate = (to, opts = {}) => {
    const target = normalizeTarget(String(to || '/chat'), loc.pathname);
    if (typeof window !== 'undefined') {
      if (opts.replace) window.history.replaceState({}, '', target);
      else window.history.pushState({}, '', target);
      setLoc(readLocation());
      window.dispatchEvent(new Event('aqlevon:navigate'));
    }
  };
  const value = useMemo(() => ({ ...loc, navigate }), [loc.pathname, loc.search]);
  return <RouterCtx.Provider value={value}>{children}</RouterCtx.Provider>;
}

export function useNavigate() { return useContext(RouterCtx).navigate; }
export function useLocation() {
  const { pathname, search } = useContext(RouterCtx);
  return { pathname, search };
}
export function useSearchParams() {
  const { search } = useContext(RouterCtx);
  return [new URLSearchParams(search || '')];
}
export function useParams() {
  const { pathname } = useContext(RouterCtx);
  const seg = pathname.split('/').filter(Boolean);
  if (['chat', 'work', 'projects'].includes(seg[0]) && seg[1]) return { id: decodeURIComponent(seg[1]) };
  return {};
}

export function NavLink({ to, className, children, ...rest }) {
  const { pathname, navigate } = useContext(RouterCtx);
  const target = normalizeTarget(String(to), pathname);
  const active = pathname === target || (target !== '/' && pathname.startsWith(target + '/'));
  const cls = typeof className === 'function' ? className({ isActive: active }) : className;
  return <a href={target} className={cls} onClick={e => { e.preventDefault(); navigate(target); }} {...rest}>{children}</a>;
}

export function Navigate({ to, replace = false }) {
  const nav = useNavigate();
  useEffect(() => { nav(to, { replace }); }, [to, replace]);
  return null;
}

export function Route() { return null; }

function matchAbsolute(pattern, pathname) {
  if (!pattern) return false;
  if (pattern === '*') return true;
  if (pattern.endsWith('/*')) return pathname === pattern.slice(0, -2) || pathname.startsWith(pattern.slice(0, -1));
  const pp = pattern.split('/').filter(Boolean);
  const ss = pathname.split('/').filter(Boolean);
  if (pp.length !== ss.length) return false;
  return pp.every((p, i) => p.startsWith(':') || p === ss[i]);
}

export function Routes({ children }) {
  const { pathname } = useContext(RouterCtx);
  const routes = React.Children.toArray(children).filter(Boolean);
  let fallback = null;
  for (const el of routes) {
    const p = el.props || {};
    if (p.index) {
      if (pathname === '/settings' || pathname === '/settings/') return p.element || null;
      continue;
    }
    const pattern = p.path;
    if (pattern === '*') { fallback = p.element; continue; }
    let ok = false;
    if (pattern?.startsWith('/')) ok = matchAbsolute(pattern, pathname);
    else if (pattern) {
      if (pathname.startsWith('/settings')) ok = pathname === '/settings/' + pattern.replace(/^\.\//, '');
      else ok = pathname.split('/').filter(Boolean).at(-1) === pattern;
    }
    if (ok) return p.element || null;
  }
  return fallback || null;
}
