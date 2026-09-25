import React, { createContext, useContext, useMemo, useState, useEffect } from 'react';
import en from './en.js';
import ar from './ar.js';

const LOCALES = { en, ar };
export const LANGS = [
  { id: 'en', label: 'English', native: 'English' },
  { id: 'ar', label: 'Arabic', native: 'العربية' }
];

const I18nCtx = createContext({ t: k => k, lang: 'ar', setLang: () => {} });

export function I18nProvider({ children }) {
  const [lang, setLang] = useState(() => typeof window !== 'undefined' ? (localStorage.getItem('aqlevon-lang') || localStorage.getItem('kite-lang') || 'ar') : 'ar');

  useEffect(() => {
    localStorage.setItem('aqlevon-lang', lang);
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
  }, [lang]);

  const value = useMemo(() => ({
    lang, setLang,
    t: (key, vars) => {
      let s = LOCALES[lang]?.[key] ?? LOCALES.en[key] ?? key;
      if (vars) for (const [k, v] of Object.entries(vars)) s = s.replace('{' + k + '}', v);
      return s;
    }
  }), [lang]);

  return React.createElement(I18nCtx.Provider, { value }, children);
}

export const useI18n = () => useContext(I18nCtx);
