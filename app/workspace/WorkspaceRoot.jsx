'use client';

import React from 'react';
import { BrowserRouter } from './router.js';
import { I18nProvider } from './i18n/index.js';
import App from './App.jsx';

export default function WorkspaceRoot() {
  return <BrowserRouter><I18nProvider><App /></I18nProvider></BrowserRouter>;
}
