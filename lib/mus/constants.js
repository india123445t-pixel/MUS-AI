export const MUS_BOS_VERSION = '1.0.0';

export const VERIFICATION_RESULTS = Object.freeze({
  VERIFIED: 'VERIFIED',
  REFUTED: 'REFUTED',
  INCONCLUSIVE: 'INCONCLUSIVE',
  CONFLICTING: 'CONFLICTING',
});

export const TASK_OUTCOMES = Object.freeze({
  SUCCESS: 'SUCCESS',
  PARTIAL: 'PARTIAL',
  FAILED: 'FAILED',
  CANCELLED: 'CANCELLED',
  UNKNOWN: 'UNKNOWN',
});

export const EFFECT_CAPABILITIES = Object.freeze([
  'READ',
  'WRITE',
  'DELETE',
  'NETWORK',
  'DEPLOY',
  'SEND_EXTERNAL',
  'PERMISSION_CHANGE',
  'CREDENTIAL_ACCESS',
  'PRODUCTION_MUTATION',
]);

export const FAILURE_CLASSES = Object.freeze([
  'TRANSIENT_INFRA',
  'MISSING_DEPENDENCY',
  'ENV_MISMATCH',
  'AUTH_REQUIRED',
  'PERMISSION_DENIED',
  'SCOPE_BOUNDARY',
  'IRREVERSIBILITY_GATE',
  'POLICY_BLOCK',
  'UNKNOWN',
]);

export const ROUTE_MODES = Object.freeze({
  FAST: 'FAST',
  NORMAL: 'NORMAL',
  HIGH: 'HIGH',
});

export const PROVENANCE_CLASSES = Object.freeze([
  'POLICY',
  'INSTRUCTION',
  'USER_STATED',
  'SYSTEM_OBSERVED',
  'VERIFIED',
  'INFERRED',
  'ASSUMED',
  'PREFERENCE',
  'IMPORTED_UNTRUSTED',
  'MODEL_PROSE',
]);

export const HIGH_CONSEQUENCE_TERMS = Object.freeze([
  'medical','diagnosis','dose','prescription','legal advice','lawsuit','investment advice','trade for me',
  'delete','drop database','production','deploy to production','send email','publish','permission','credential','secret',
  'تشخيص','جرعة','دواء','طبي','قانوني','استشارة قانونية','استثمار','احذف','حذف','إنتاج','انشر','أرسل','صلاحية','كلمة سر','سر',
]);
