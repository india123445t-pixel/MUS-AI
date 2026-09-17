import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Routes, Route, NavLink, Navigate, useNavigate, useLocation } from './router.js';
import { api } from './api.js';
import { useI18n } from './i18n/index.js';
import Icon from './components/Icon.jsx';
import ChatPage from './pages/ChatPage.jsx';
import WorkPage from './pages/WorkPage.jsx';
import DeveloperPage from './pages/DeveloperPage.jsx';
import ProjectsPage from './pages/ProjectsPage.jsx';
import ProjectDetail from './pages/ProjectDetail.jsx';
import LibraryPage from './pages/LibraryPage.jsx';
import PluginsPage from './pages/PluginsPage.jsx';
import ScheduledPage from './pages/ScheduledPage.jsx';
import SettingsPage from './pages/SettingsPage.jsx';
import SearchModal from './components/SearchModal.jsx';

function groupChats(chats) {
  const now = Date.now(), day = 86400000;
  const g = { pinned: [], today: [], week: [], older: [] };
  for (const c of chats) {
    if (c.pinned) { g.pinned.push(c); continue; }
    const age = now - new Date(c.updated_at).getTime();
    if (age < day) g.today.push(c);
    else if (age < 7 * day) g.week.push(c);
    else g.older.push(c);
  }
  return g;
}

function RecentItem({ chat, active, onOpen, onChanged, t }) {
  const [menu, setMenu] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState(chat.title);
  const ref = useRef();

  const doRename = async () => {
    const v = name.trim();
    setRenaming(false);
    if (v && v !== chat.title) { await api.patch('/chats/' + chat.id, { title: v }); onChanged(); }
  };

  if (renaming) return (
    <div style={{ padding: '2px 4px' }}>
      <input className="recent-rename" autoFocus value={name}
        onChange={e => setName(e.target.value)}
        onBlur={doRename}
        onKeyDown={e => { if (e.key === 'Enter') doRename(); if (e.key === 'Escape') setRenaming(false); }} />
    </div>
  );

  return (
    <div className={'recent-item' + (active ? ' active' : '')} ref={ref}>
      <button className="rtitle" title={chat.title} onClick={onOpen}>{chat.title || '…'}</button>
      <button className="rmenu" data-open={menu} aria-label="Options" onClick={e => { e.stopPropagation(); setMenu(v => !v); }}>
        <Icon name="dots" size={15} />
      </button>
      {menu && <>
        <div className="menu-backdrop" onClick={() => setMenu(false)} />
        <div className="menu" style={{ insetInlineEnd: 8, marginTop: 26 }}>
          <button onClick={async () => { setMenu(false); await api.patch('/chats/' + chat.id, { pinned: !chat.pinned }); onChanged(); }}>
            <Icon name="pin" size={15} />{chat.pinned ? t('menu.unpin') : t('menu.pin')}
          </button>
          <button onClick={() => { setMenu(false); setRenaming(true); setName(chat.title); }}>
            <Icon name="pencil" size={15} />{t('menu.rename')}
          </button>
          <button className="danger" onClick={async () => {
            setMenu(false);
            if (!confirm(t('confirm.deleteChat'))) return;
            await api.del('/chats/' + chat.id); onChanged();
          }}>
            <Icon name="trash" size={15} />{t('menu.delete')}
          </button>
        </div>
      </>}
    </div>
  );
}

export default function App() {
  const nav = useNavigate();
  const loc = useLocation();
  const { t } = useI18n();
  const [recents, setRecents] = useState([]);
  const [showSearch, setShowSearch] = useState(false);
  const [sideOpen, setSideOpen] = useState(false);
  const [theme, setTheme] = useState(() => typeof window !== 'undefined' ? (localStorage.getItem('aqlevon-theme') || localStorage.getItem('kite-theme') || 'dark') : 'dark');
  const [density, setDensity] = useState(() => typeof window !== 'undefined' ? (localStorage.getItem('aqlevon-density') || localStorage.getItem('kite-density') || 'comfortable') : 'comfortable');

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('aqlevon-theme', theme);
  }, [theme]);
  useEffect(() => {
    document.documentElement.dataset.density = density;
    localStorage.setItem('aqlevon-density', density);
  }, [density]);

  const refreshRecents = useCallback(() => {
    api.get('/chats').then(setRecents).catch(() => {});
  }, []);

  useEffect(() => {
    refreshRecents();
  }, [refreshRecents]);

  useEffect(() => { setSideOpen(false); }, [loc.pathname]);

  useEffect(() => {
    const onKey = e => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); setShowSearch(true); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const newChat = async (temporary = false) => {
    const c = await api.post('/chats', { temporary });
    refreshRecents();
    nav('/chat/' + c.id + (temporary ? '?temp=1' : ''));
  };

  const activeChatId = loc.pathname.startsWith('/chat/') ? loc.pathname.split('/')[2] : null;
  const groups = groupChats(recents);
  const groupDefs = [
    ['pinned', t('group.pinned')], ['today', t('group.today')],
    ['week', t('group.week')], ['older', t('group.older')]
  ];
  let shown = 0;

  return (
    <div className="app">
      {sideOpen && <div className="sidebar-backdrop" onClick={() => setSideOpen(false)} />}
      <aside className={'sidebar' + (sideOpen ? ' open' : '')}>
        <div className="brand"><span className="logo"><img src="/logo.svg" alt="AQLEVON" /></span> AQLEVON</div>

        <div className="side-actions">
          <button className="navlink" onClick={() => newChat(false)}><Icon name="plus" size={17} /> {t('app.newChat')}</button>
          <button className="navlink" onClick={() => setShowSearch(true)}>
            <Icon name="search" size={17} /> {t('app.search')} <span className="kbd">Ctrl K</span>
          </button>
        </div>

        <div className="side-scroll">
          <div className="side-section">{t('app.spaces')}</div>
          <NavLink to="/chat" className={() => 'navlink' + (loc.pathname.startsWith('/chat') ? ' active' : '')}><Icon name="chat" size={17} /> {t('app.chats')}</NavLink>
          <NavLink to="/projects" className={() => 'navlink' + (loc.pathname.startsWith('/projects') ? ' active' : '')}><Icon name="folder" size={17} /> {t('app.projects')}</NavLink>
          <NavLink to="/work" className={() => 'navlink' + (loc.pathname.startsWith('/work') ? ' active' : '')}><Icon name="work" size={17} /> {t('app.work')}</NavLink>
          <NavLink to="/developer" className={() => 'navlink' + (loc.pathname.startsWith('/developer') ? ' active' : '')}><Icon name="code" size={17} /> {t('app.developer')}</NavLink>
          <NavLink to="/scheduled" className={() => 'navlink' + (loc.pathname.startsWith('/scheduled') ? ' active' : '')}><Icon name="clock" size={17} /> {t('app.automations')}</NavLink>
          <NavLink to="/library" className={() => 'navlink' + (loc.pathname.startsWith('/library') ? ' active' : '')}><Icon name="library" size={17} /> {t('app.library')}</NavLink>
          <NavLink to="/plugins" className={() => 'navlink' + (loc.pathname.startsWith('/plugins') ? ' active' : '')}><Icon name="puzzle" size={17} /> {t('app.apps')}</NavLink>

          {groupDefs.map(([key, label]) => {
            const list = groups[key];
            if (!list.length || shown >= 30) return null;
            const slice = list.slice(0, 30 - shown);
            shown += slice.length;
            return (
              <React.Fragment key={key}>
                <div className="side-section">{label}</div>
                {slice.map(c => (
                  <RecentItem key={c.id} chat={c} active={c.id === activeChatId} t={t}
                    onOpen={() => nav('/chat/' + c.id)} onChanged={refreshRecents} />
                ))}
              </React.Fragment>
            );
          })}
          {recents.length > 30 && (
            <button className="navlink" onClick={() => setShowSearch(true)} style={{ fontSize: 12 }}>{t('app.viewAll')}</button>
          )}
        </div>

        <div className="side-foot">
          <NavLink to="/settings/general" className={() => 'navlink' + (loc.pathname.startsWith('/settings') ? ' active' : '')}>
            <Icon name="gear" size={17} /> {t('app.settings')}
          </NavLink>
          <div className="ws-label">{t('app.workspace')}</div>
        </div>
      </aside>

      <main className="main">
        <Routes>
          <Route path="/" element={<Navigate to="/chat" replace />} />
          <Route path="/chat" element={<ChatPage onChatsChanged={refreshRecents} newChat={newChat} onMenu={() => setSideOpen(true)} />} />
          <Route path="/chat/:id" element={<ChatPage onChatsChanged={refreshRecents} newChat={newChat} onMenu={() => setSideOpen(true)} />} />
          <Route path="/work" element={<WorkPage onMenu={() => setSideOpen(true)} />} />
          <Route path="/work/:id" element={<WorkPage onMenu={() => setSideOpen(true)} />} />
          <Route path="/developer" element={<DeveloperPage onMenu={() => setSideOpen(true)} />} />
          <Route path="/projects" element={<ProjectsPage onMenu={() => setSideOpen(true)} />} />
          <Route path="/projects/:id" element={<ProjectDetail onChatsChanged={refreshRecents} onMenu={() => setSideOpen(true)} />} />
          <Route path="/library" element={<LibraryPage onMenu={() => setSideOpen(true)} />} />
          <Route path="/scheduled" element={<ScheduledPage onMenu={() => setSideOpen(true)} />} />
          <Route path="/plugins" element={<PluginsPage onMenu={() => setSideOpen(true)} />} />
          <Route path="/settings/*" element={<SettingsPage theme={theme} setTheme={setTheme} density={density} setDensity={setDensity} onMenu={() => setSideOpen(true)} />} />
          <Route path="*" element={<div className="empty"><Icon name="warn" size={28} /><p>{t('notfound')}</p></div>} />
        </Routes>
      </main>

      {showSearch && <SearchModal onClose={() => setShowSearch(false)} onOpen={id => { setShowSearch(false); nav('/chat/' + id); }} />}
    </div>
  );
}
