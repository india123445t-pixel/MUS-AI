'use client';

import React, { useEffect } from 'react';
import { BrowserRouter } from './router.js';
import { I18nProvider } from './i18n/index.js';
import App from './App.jsx';

const LEGACY_PUBLIC_KEYS=[
  'aqlevon-ai-public-chats-v1','aqlevon-ai-public-chats-v2','aqlevon-ai-public-chats-v3',
  'mus-ai-public-chats-v1','mus-ai-public-chats-v2',
  'aqlevon-ai-public-session-v1','aqlevon-ai-public-session-v2'
];

export default function WorkspaceRoot() {
  useEffect(()=>{ for(const key of LEGACY_PUBLIC_KEYS) localStorage.removeItem(key); },[]);
  return <BrowserRouter><I18nProvider><App /></I18nProvider></BrowserRouter>;
}
