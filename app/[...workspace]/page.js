import {notFound} from 'next/navigation';
import WorkspaceRoot from '../workspace/WorkspaceRoot.jsx';

const EXACT_ROOTS=new Set(['developer','scheduled','library','plugins']);
const ID_ROOTS=new Set(['chat','projects','work']);
const SETTINGS_SECTIONS=new Set([
  'general','appearance','language','personalization','memory',
  'models','providers','provider','web','data','advanced','about'
]);

export default async function WorkspaceCatchAll({params}){
  const resolved=await params;
  const parts=Array.isArray(resolved?.workspace)?resolved.workspace:[];
  const [root,...rest]=parts;

  if(EXACT_ROOTS.has(root)){
    if(rest.length!==0)notFound();
    return <WorkspaceRoot />;
  }
  if(ID_ROOTS.has(root)){
    if(rest.length>1)notFound();
    return <WorkspaceRoot />;
  }
  if(root==='settings'){
    if(rest.length>1)notFound();
    if(rest.length===1&&!SETTINGS_SECTIONS.has(rest[0]))notFound();
    return <WorkspaceRoot />;
  }
  notFound();
}
