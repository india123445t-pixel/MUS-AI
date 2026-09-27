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
      api.get('/search' + (q ? '?q=' + encodeURIComponent(q) : '')).then(setResults).catch(() => {});
    }, 180);
    return () => clearTimeout(timer);
  }, [q]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={t('app.search')} onClick={e => e.stopPropagation()}>
        <input ref={ref} className="input" placeholder={t('search.placeholder')}
          value={q} onChange={e => setQ(e.target.value)}
          onKeyDown={e => { if (e.key === 'Escape') onClose(); }} />
        <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 2 }}>
          {results.slice(0, 30).map(r => {
            const icon={chat:'chat',project:'folder',file:'file',job:'work',automation:'clock'}[r.type]||'search';
            return <button key={r.type+':'+r.id} className="recent-item" onClick={() => { nav(r.path||'/chat'); onClose(); }}>
              <Icon name={icon} size={14} />
              <span className="rtitle" dir="auto">{r.title}</span>
              {r.subtitle&&<span className="muted small" style={{maxWidth:220,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}} dir="auto">{r.subtitle}</span>}
            </button>;
          })}
          {results.length === 0 && <div className="muted" style={{ padding: '8px 4px' }}>{t('search.noResults')}</div>}
        </div>
      </div>
    </div>
  );
}
