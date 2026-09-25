export const dynamic='force-dynamic';
export async function GET(){
  return Response.json({
    runpod_api_key:!!process.env.RUNPOD_API_KEY,
    aqlevon_model_key:!!process.env.AQLEVON_MODEL_KEY,
    aqlevon_model_url:!!process.env.AQLEVON_MODEL_URL,
    aqlevon_child_model_key:!!process.env.AQLEVON_CHILD_MODEL_KEY,
    aqlevon_child_model_url:!!process.env.AQLEVON_CHILD_MODEL_URL
  },{headers:{'Cache-Control':'no-store'}});
}
