export const CHILD_OWNER_POLICY_SCHEMA='AQLEVON_CHILD_OWNER_POLICY_V1';

export const CHILD_OWNER_POLICY_CATALOG=Object.freeze([
  {id:'public_model_access',label:'الوصول إلى نموذج المستخدمين',description:'يسمح للمختبر بالوصول إلى Runtime/واجهات نموذج المستخدمين عندما يكون هناك Adapter يدعم ذلك.'},
  {id:'production_weight_read',label:'قراءة أوزان الإنتاج',description:'يسمح بقراءة artifacts/metadata الخاصة بأوزان الإنتاج عبر Adapter مصرح.'},
  {id:'production_weight_write',label:'كتابة أوزان الإنتاج',description:'يسمح بطلب كتابة/استبدال أوزان الإنتاج عبر Adapter مصرح.'},
  {id:'training_lane_read',label:'قراءة مسار التدريب',description:'يسمح بقراءة حالة ونتائج مسارات التدريب.'},
  {id:'training_lane_write',label:'الكتابة إلى مسار التدريب',description:'يسمح بإرسال حزم/أمثلة أو أوامر إلى مسار تدريب موصول.'},
  {id:'worker03_access',label:'الوصول إلى Worker 03',description:'يسمح للطفل باستخدام Worker 03 إذا كان موصولًا ومصرحًا.'},
  {id:'external_network',label:'الوصول الخارجي للشبكة',description:'يسمح للأدوات الموصولة بطلب موارد خارجية ضمن الصلاحيات التي فعّلها المالك.'},
  {id:'receipt_required',label:'اشتراط Receipt',description:'عند تفعيله لا يعتبر تنفيذ الأداة ناجحًا بدون إيصال قابل للتتبع.'},
]);

export function defaultChildOwnerPolicy(){
  return {
    schema:CHILD_OWNER_POLICY_SCHEMA,
    public_model_access:false,
    production_weight_read:false,
    production_weight_write:false,
    training_lane_read:false,
    training_lane_write:false,
    worker03_access:false,
    external_network:true,
    receipt_required:true,
    updated_at:new Date().toISOString(),
  };
}

export function normalizeChildOwnerPolicy(raw={}){
  const base=defaultChildOwnerPolicy();
  return {
    schema:CHILD_OWNER_POLICY_SCHEMA,
    public_model_access:raw.public_model_access===true,
    production_weight_read:raw.production_weight_read===true,
    production_weight_write:raw.production_weight_write===true,
    training_lane_read:raw.training_lane_read===true,
    training_lane_write:raw.training_lane_write===true,
    worker03_access:raw.worker03_access===true,
    external_network:raw.external_network!==false,
    receipt_required:raw.receipt_required!==false,
    updated_at:String(raw.updated_at||new Date().toISOString()),
  };
}

export function enableAllOwnerControllablePolicy(){
  return normalizeChildOwnerPolicy({
    public_model_access:true,
    production_weight_read:true,
    production_weight_write:true,
    training_lane_read:true,
    training_lane_write:true,
    worker03_access:true,
    external_network:true,
    receipt_required:false,
  });
}
