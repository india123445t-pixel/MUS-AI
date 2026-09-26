'use client';

export default function ActionLog({logs=[]}){
  return <section className="wb-panel"><div className="wb-panel-head"><div><span className="wb-kicker">AUDIT</span><h2>سجل الاختبارات</h2></div><span>{logs.length}/50</span></div>
    <div className="wb-timeline">{logs.length?logs.map(row=><div className="wb-log" key={row.id||`${row.tool}-${row.created_at}`}><i className={row.ok?'ok':'bad'}/><div><b>{row.tool} · {row.level}</b><span>{row.state||row.error_class||'—'}</span><small>{row.latency_ms||0}ms · {row.created_at?new Date(row.created_at).toLocaleString('ar-MA'):'—'}</small></div></div>):<p className="wb-empty">لا توجد اختبارات مسجلة بعد.</p>}</div>
  </section>;
}