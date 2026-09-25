import React, { useEffect, useRef, useState } from 'react';
import { api } from '../api.js';
import { useI18n } from '../i18n/index.js';
import Icon from '../components/Icon.jsx';

const TEXT_MIME = /^(text\/|application\/(json|xml|javascript))/;
const extOf = n => (n.match(/\.([a-z0-9]+)$/i) || [])[1]?.toUpperCase() || 'FILE';

export default function LibraryPage({ onMenu }) {
  const { t } = useI18n();
  const [files, setFiles] = useState([]);
  const [q, setQ] = useState('');
  const [kind, setKind] = useState('all');
  const [view, setView] = useState(() => typeof window !== 'undefined' ? (localStorage.getItem('aqlevon-lib-view') || localStorage.getItem('kite-lib-view') || 'grid') : 'grid');
  const [renaming, setRenaming] = useState(null);
  const [preview, setPreview] = useState(null);
  const fileRef = useRef();

  const FILTERS = [
    { id: 'all', label: t('lib.all') },
    { id: 'uploaded', label: t('lib.docs') },
    { id: 'generated', label: t('lib.generated') },
    { id: 'image', label: t('lib.images') }
  ];

  const load = () => api.get(`/files?kind=${kind}&q=${encodeURIComponent(q)}`).then(setFiles).catch(() => {});
  useEffect(() => { const timer = setTimeout(() => { load(); }, 150); return () => clearTimeout(timer); }, [q, kind]);
  useEffect(() => { localStorage.setItem('aqlevon-lib-view', view); }, [view]);

  const upload = async f => {
    const fd = new FormData();
    fd.append('file', f);
    await api.upload('/files', fd);
    load();
  };

  const saveRename = async () => {
    const name = renaming.name.trim();
    if (!name) return;
    await api.patch(`/files/${renaming.id}`, { name });
    setRenaming(null);
    load();
  };

  const openPreview = async f => {
    if (f.kind === 'image' || (f.mime || '').startsWith('image/')) { setPreview({ file: f }); return; }
    if (TEXT_MIME.test(f.mime || '') || /\.(md|txt|json|csv|js|jsx|css|html)$/i.test(f.name)) {
      try {
        const text = await api.fileText(f.id);
        setPreview({ file: f, text: text.slice(0, 20000) });
      } catch { setPreview({ file: f, text: t('common.error') }); }
      return;
    }
    setPreview({ file: f, binary: true });
  };

  const del = async f => {
    if (!confirm(t('lib.deleteConfirm'))) return;
    await api.del('/files/' + f.id); load();
  };

  const isImg = f => f.kind === 'image' || (f.mime || '').startsWith('image/');

  const Actions = ({ f }) => (
    <>
      <button className="iconbtn" title={t('lib.preview')} onClick={e => { e.stopPropagation(); openPreview(f); }}><Icon name="search" size={14} /></button>
      <button className="iconbtn" title={t('menu.rename')} onClick={e => { e.stopPropagation(); setRenaming({ id: f.id, name: f.name }); }}><Icon name="pencil" size={14} /></button>
      <a className="iconbtn" title={t('lib.download')} href={api.fileUrl(f.id)} download={f.name} onClick={e => e.stopPropagation()}><Icon name="download" size={14} /></a>
      <button className="iconbtn" title={t('common.delete')} onClick={e => { e.stopPropagation(); del(f); }}><Icon name="trash" size={14} /></button>
    </>
  );

  return (
    <>
      <div className="topbar">
        <button className="iconbtn hamburger" aria-label="Menu" onClick={onMenu}><Icon name="menu" /></button>
        <h1>{t('lib.title')}</h1>
        <span className="tag warn">{t('lib.browserOnly')}</span>
        <button className="btn" onClick={() => fileRef.current.click()}><Icon name="plus" size={15} /> {t('lib.upload')}</button>
        <input hidden type="file" ref={fileRef} onChange={e => e.target.files[0] && upload(e.target.files[0])} />
      </div>
      <div className="content narrow">
        <div className="card" style={{ marginBottom: 14 }}><p className="muted small" style={{ margin: 0 }}>{t('lib.browserNotice')}</p></div>
        <div className="lib-toolbar">
          <input className="input" style={{ maxWidth: 260 }} placeholder={t('lib.search')} value={q} onChange={e => setQ(e.target.value)} />
          {FILTERS.map(f => (
            <button key={f.id} className={'chip' + (kind === f.id ? ' on' : '')} onClick={() => setKind(f.id)}>{f.label}</button>
          ))}
          <div style={{ flex: 1 }} />
          <div className="seg">
            <button className={view === 'grid' ? 'on' : ''} title={t('lib.gridView')} onClick={() => setView('grid')}><Icon name="image" size={14} /></button>
            <button className={view === 'list' ? 'on' : ''} title={t('lib.listView')} onClick={() => setView('list')}><Icon name="menu" size={14} /></button>
          </div>
        </div>

        {files.length === 0 && (
          <div className="empty"><Icon name="library" size={28} /><p>{t('lib.empty')}</p></div>
        )}

        {view === 'grid' ? (
          <div className="lib-grid">
            {files.map(f => (
              <div key={f.id} className="lib-tile">
                <button className="lib-thumb" onClick={() => openPreview(f)} style={{ border: 'none', cursor: 'pointer', width: '100%' }}>
                  {isImg(f)
                    ? <img src={api.fileUrl(f.id)} alt={f.name} loading="lazy" />
                    : <span className="ftype">{extOf(f.name)}</span>}
                </button>
                <div className="linfo">
                  {renaming?.id === f.id ? (
                    <input className="input" autoFocus value={renaming.name} style={{ padding: '3px 8px', fontSize: 12 }}
                      onChange={e => setRenaming({ ...renaming, name: e.target.value })}
                      onBlur={saveRename}
                      onKeyDown={e => { if (e.key === 'Enter') saveRename(); if (e.key === 'Escape') setRenaming(null); }} />
                  ) : (
                    <div className="lname" title={f.name} dir="auto">{f.name}</div>
                  )}
                  <div className="lmeta">
                    <span>{f.size ? (f.size / 1024).toFixed(0) + ' KB' : '—'}</span>
                    <span>{new Date(f.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
                <div className="lacts"><Actions f={f} /></div>
              </div>
            ))}
          </div>
        ) : (
          <table className="filetable">
            <thead><tr><th>{t('lib.name')}</th><th>{t('lib.type')}</th><th>{t('lib.size')}</th><th>{t('lib.added')}</th><th /></tr></thead>
            <tbody>
              {files.map(f => (
                <tr key={f.id}>
                  <td>
                    {renaming?.id === f.id ? (
                      <span className="row">
                        <input className="input" autoFocus value={renaming.name}
                          onChange={e => setRenaming({ ...renaming, name: e.target.value })}
                          onKeyDown={e => { if (e.key === 'Enter') saveRename(); if (e.key === 'Escape') setRenaming(null); }} />
                        <button className="btn sm" onClick={saveRename}>{t('common.save')}</button>
                      </span>
                    ) : (
                      <button className="linklike" onClick={() => openPreview(f)} dir="auto">
                        <Icon name={isImg(f) ? 'image' : 'file'} size={15} />{f.name}
                      </button>
                    )}
                  </td>
                  <td><span className="tag">{extOf(f.name)}</span></td>
                  <td className="muted">{f.size ? (f.size / 1024).toFixed(1) + ' KB' : '—'}</td>
                  <td className="muted">{new Date(f.created_at).toLocaleDateString()}</td>
                  <td><span className="row" style={{ flexWrap: 'nowrap', justifyContent: 'flex-end' }}><Actions f={f} /></span></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {preview && (
        <div className="modal-backdrop" onClick={() => setPreview(null)}>
          <div className="modal wide" onClick={e => e.stopPropagation()}>
            <div className="row spread">
              <h3 style={{ margin: 0 }} dir="auto">{preview.file.name}</h3>
              <button className="iconbtn" title={t('common.close')} onClick={() => setPreview(null)}><Icon name="x" size={16} /></button>
            </div>
            <div style={{ marginTop: 12, maxHeight: '60vh', overflow: 'auto' }}>
              {isImg(preview.file) ? (
                <img src={api.fileUrl(preview.file.id)} alt={preview.file.name} style={{ maxWidth: '100%', borderRadius: 10 }} />
              ) : preview.binary ? (
                <p className="muted">{t('lib.noPreview')} <a href={api.fileUrl(preview.file.id)} download={preview.file.name}>{t('lib.download')}</a></p>
              ) : (
                <pre className="preview-pre">{preview.text}</pre>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
