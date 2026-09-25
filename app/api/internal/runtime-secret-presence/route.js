export const dynamic='force-dynamic';
export async function GET(){
  const keys=[
    'RUNPOD_API_KEY','AQLEVON_MODEL_KEY','AQLEVON_MODEL_URL','AQLEVON_CHILD_MODEL_KEY','AQLEVON_CHILD_MODEL_URL',
    'SUPABASE_SERVICE_ROLE_KEY','KV_REST_API_URL','KV_REST_API_TOKEN','UPSTASH_REDIS_REST_URL','UPSTASH_REDIS_REST_TOKEN',
    'REDIS_URL','BLOB_READ_WRITE_TOKEN','POSTGRES_URL','POSTGRES_PRISMA_URL','DATABASE_URL'
  ];
  return Response.json(Object.fromEntries(keys.map(k=>[k.toLowerCase(),!!process.env[k]])),{headers:{'Cache-Control':'no-store'}});
}
