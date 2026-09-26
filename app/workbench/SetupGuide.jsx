'use client';

export default function SetupGuide({guide}){
  if(!guide?.name)return null;
  const snippet=JSON.stringify(guide.request_example,null,2);
  async function copy(){try{await navigator.clipboard.writeText(snippet)}catch{}}
  return <details className="wb-guide"><summary>دليل التهيئة</summary><div className="wb-guide-body">
    <p>متغيرات المحوّل المطلوبة: <code>{guide.required_env?.join(' · ')||'—'}</code></p>
    {guide.native_jina_alternative?.length>0&&<p>بديل web الأصلي Jina: <code>{guide.native_jina_alternative.join(' · ')}</code></p>}
    <div className="wb-code-head"><b>AQLEVON_CHILD_TOOL_V1</b><button type="button" onClick={copy}>نسخ JSON</button></div>
    <pre dir="ltr">{snippet}</pre>
    <p>{guide.receipt_required}</p>
    <p>الاستجابة المطلوبة:</p><pre dir="ltr">{JSON.stringify(guide.response_example,null,2)}</pre>
    <p>الأفعال الحقيقية مرجع عرض فقط:</p><pre dir="ltr">{JSON.stringify(guide.real_actions,null,2)}</pre>
  </div></details>;
}