import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from '../router.js';
import { api } from '../api.js';
import { useI18n } from '../i18n/index.js';
import Icon from './Icon.jsx';

export default function SearchModal({ onClose }) {
  const [q, setQ] = useState('');
  const [results, setResults] = useState([]);
  const nav = useNavigate();
  const ref = useRef();
  const { t } = useI18n();

  useEffect(() => { ref.current?.focus(); }, []);
  useEffect(() => {
    const timer = setTimeout(() => {
      api.get('/chats' + (q ? '?q=' + encodeURIComponent(q) : '')).then(setResults).catch(() => {});
    }, 180);
    return () => clearTimeout(timer);
  }, [q]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <input ref={ref} className="input" placeholder={t('search.placeholder')}
          value={q} onChange={e => setQ(e.target.value)}
          onKeyDown={e => { if (e.key === 'Escape') onClose(); }} />
        <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 2 }}>
          {results.slice(0, 20).map(c => (
            <button key={c.id} className="recent-item"
              onClick={() => { nav('/chat/' + c.id); onClose(); }}>
              <Icon name="chat" size={14} />
              <span className="rtitle">{c.title}</span>
              <span className="muted small" style={{ flex: 'none' }}>
                {new Date(c.updated_at).toLocaleDateString()}
              </span>
            </button>
          ))}
          {results.length === 0 && <div className="muted" style={{ padding: '8px 4px' }}>{t('search.noResults')}</div>}
        </div>
      </div>
    </div>
  );
}
