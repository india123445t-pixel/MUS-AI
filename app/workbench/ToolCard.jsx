'use client';

const LABELS=Object.freeze({web:'ويب',browser:'متصفح',terminal:'طرفية',files:'ملفات',media:'وسائط'});
const STATES=Object.freeze({
  CONFIGURED_OK:'مهيأ',
  ADAPTER_SELFTEST_UNSUPPORTED:'المحوّل لا يدعم الاختبار الذاتي',
  ADAPTER_REQUIRED:'يحتاج محوّلًا',
  PERMISSION_DISABLED:'الصلاحية موقوفة',
  OWNER_POLICY_DISABLED:'سياسة المالك تمنع الشبكة',
});

export default function ToolCard({tool,busy,onTest,children}){
  const levels=tool.name==='web'?['L1','L2','L3']:['L1','L2'];
  return <article className={`wb-tool wb-state-${String(tool.state||'ADAPTER_REQUIRED').toLowerCase()}`}>
    <div className="wb-tool-head"><div><span className="wb-kicker">{tool.protocol}</span><h3>{LABELS[tool.name]||tool.name}</h3></div><span className="wb-state">{STATES[tool.state]||tool.state}</span></div>
    <dl className="wb-meta"><div><dt>الوضع</dt><dd>{tool.mode||'—'}</dd></div><div><dt>مهيأ</dt><dd>{tool.configured?'نعم':'لا'}</dd></div><div><dt>آخر اختبار</dt><dd>{tool.last_selftest?.level||'—'}</dd></div></dl>
    <div className="wb-actions">{levels.map(level=><button key={level} type="button" disabled={busy} onClick={()=>onTest(tool.name,level)}>{busy?'جارٍ...':`اختبار ${level}`}</button>)}</div>
    {tool.name!=='web'&&<p className="wb-note">L3 غير قابل للاختبار الآمن لهذه الأداة.</p>}
    {children}
  </article>;
}