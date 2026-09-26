'use client';

const LABELS=Object.freeze({public_model_access:'الوصول لنموذج العامة',production_weight_read:'قراءة أوزان الإنتاج',production_weight_write:'كتابة أوزان الإنتاج',training_lane_read:'قراءة مسار التدريب',training_lane_write:'الكتابة لمسار التدريب',worker03_access:'الوصول إلى Worker03',external_network:'الشبكة الخارجية',receipt_required:'اشتراط Receipt',automatic_promotion:'الترقية التلقائية',gpu_request_allowed:'طلب GPU'});

export default function PolicyPanel({policy={}}){
  return <section className="wb-panel"><div className="wb-panel-head"><div><span className="wb-kicker">READ ONLY</span><h2>سياسة المالك</h2></div></div>
    <div className="wb-policy">{Object.entries(policy).filter(([key])=>key!=='schema'&&key!=='updated_at').map(([key,value])=><div key={key}><span>{LABELS[key]||key}</span><b className={value?'on':'off'}>{value?'مسموح':'موقوف'}</b></div>)}</div>
  </section>;
}