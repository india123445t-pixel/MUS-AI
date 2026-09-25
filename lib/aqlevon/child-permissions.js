export const CHILD_PERMISSIONS_SCHEMA='AQLEVON_CHILD_PERMISSIONS_V1';

export const CHILD_PERMISSION_CATALOG=Object.freeze([
  {id:'web.research',group:'web',label:'بحث الويب',description:'البحث وقراءة صفحات الويب.'},
  {id:'browser.navigate',group:'browser',label:'تصفح المواقع',description:'فتح الروابط والتنقل بين الصفحات.'},
  {id:'browser.form_fill',group:'browser',label:'ملء النماذج',description:'كتابة البيانات في حقول المواقع.'},
  {id:'browser.session_login',group:'browser',label:'استخدام جلسة دخول مفتوحة',description:'استخدام جلسة أنت سجلت الدخول إليها بدون كشف كلمة المرور.'},
  {id:'browser.download',group:'browser',label:'تنزيل الملفات',description:'تنزيل الملفات إلى مساحة الطفل.'},
  {id:'browser.upload',group:'browser',label:'رفع الملفات',description:'رفع ملفات من مساحة الطفل إلى موقع.'},
  {id:'browser.submit',group:'browser',label:'إرسال/تأكيد النماذج',description:'ضغط أزرار الإرسال أو التأكيد في المواقع.'},
  {id:'files.read',group:'files',label:'قراءة الملفات',description:'قراءة ملفات مساحة الطفل.'},
  {id:'files.write',group:'files',label:'إنشاء وتعديل الملفات',description:'إنشاء ملفات أو تعديلها داخل مساحة الطفل.'},
  {id:'files.delete',group:'files',label:'حذف الملفات',description:'حذف ملفات داخل مساحة الطفل.'},
  {id:'terminal.run',group:'terminal',label:'تشغيل الطرفية والكود',description:'تشغيل أوامر وبرامج داخل Sandbox الطفل.'},
  {id:'media.read',group:'media',label:'قراءة الوسائط',description:'فتح وتحليل صور وصوت وفيديو.'},
  {id:'media.write',group:'media',label:'إنشاء/تعديل الوسائط',description:'إنشاء أو تعديل وسائط عبر Adapter الطفل.'},
  {id:'workflow.multi_step',group:'automation',label:'تنفيذ متعدد الخطوات',description:'متابعة مهمة عبر عدة خطوات دون انتظار بين كل خطوة.'},
  {id:'external.publish',group:'external',label:'النشر الخارجي',description:'نشر محتوى أو تغييرات إلى خدمة خارجية موصولة.'},
  {id:'account.modify',group:'external',label:'تعديل إعدادات الحسابات',description:'تعديل إعدادات حساب خارجي موصول.'}
]);

export const CHILD_TOOL_ACTIONS=Object.freeze({
  web:Object.freeze([
    {id:'research',label:'بحث وقراءة',permissions:['web.research']},
  ]),
  browser:Object.freeze([
    {id:'navigate',label:'فتح/تنقل',permissions:['browser.navigate']},
    {id:'form_fill',label:'ملء نموذج',permissions:['browser.form_fill']},
    {id:'session_login',label:'استخدام جلسة دخول',permissions:['browser.session_login']},
    {id:'download',label:'تنزيل ملف',permissions:['browser.download']},
    {id:'upload',label:'رفع ملف',permissions:['browser.upload']},
    {id:'submit',label:'إرسال/تأكيد',permissions:['browser.submit']},
    {id:'publish',label:'نشر خارجي',permissions:['browser.submit','external.publish']},
    {id:'account_modify',label:'تعديل حساب موصول',permissions:['browser.submit','account.modify']},
  ]),
  files:Object.freeze([
    {id:'read',label:'قراءة',permissions:['files.read']},
    {id:'write',label:'إنشاء/تعديل',permissions:['files.write']},
    {id:'delete',label:'حذف',permissions:['files.delete']},
  ]),
  terminal:Object.freeze([
    {id:'run',label:'تشغيل',permissions:['terminal.run']},
  ]),
  media:Object.freeze([
    {id:'read',label:'قراءة/تحليل',permissions:['media.read']},
    {id:'write',label:'إنشاء/تعديل',permissions:['media.write']},
  ]),
});

export function defaultChildPermissions(){
  return {
    schema:CHILD_PERMISSIONS_SCHEMA,
    execution_enabled:false,
    autonomy:'ask_each_action',
    grants:Object.fromEntries(CHILD_PERMISSION_CATALOG.map(x=>[x.id,false])),
    updated_at:new Date().toISOString()
  };
}

export function normalizeChildPermissions(raw={}){
  const base=defaultChildPermissions();
  const grants={...base.grants};
  for(const item of CHILD_PERMISSION_CATALOG)grants[item.id]=raw?.grants?.[item.id]===true;
  const autonomy=['observe_only','ask_each_action','run_within_grants'].includes(raw.autonomy)?raw.autonomy:base.autonomy;
  return {
    schema:CHILD_PERMISSIONS_SCHEMA,
    execution_enabled:raw.execution_enabled===true,
    autonomy,
    grants,
    updated_at:String(raw.updated_at||new Date().toISOString())
  };
}

export function isChildPermissionGranted(raw,id){
  const p=normalizeChildPermissions(raw);
  return p.execution_enabled===true&&p.grants[id]===true;
}

export function childActionDefinition(tool,action){
  const actions=CHILD_TOOL_ACTIONS[String(tool||'')]||[];
  return actions.find(x=>x.id===String(action||''))||null;
}

export function requiredChildPermissions(tool,action,{multi_step=false}={}){
  const def=childActionDefinition(tool,action);
  if(!def)return [];
  const required=[...def.permissions];
  if(multi_step===true&&!required.includes('workflow.multi_step'))required.push('workflow.multi_step');
  return required;
}
