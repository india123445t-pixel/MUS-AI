import React, { useMemo } from 'react';

function escapeHtml(s='') {
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function inline(s='') {
  return escapeHtml(s)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
}

function renderMarkdown(text='') {
  const lines=String(text).replace(/\r\n/g,'\n').split('\n');
  const out=[]; let inCode=false, code=[], list=[];
  const flushList=()=>{if(list.length){out.push('<ul>'+list.map(x=>'<li>'+inline(x)+'</li>').join('')+'</ul>');list=[]}};
  const flushCode=()=>{if(code.length){out.push('<pre><code>'+escapeHtml(code.join('\n'))+'</code></pre>');code=[]}};
  for(const line of lines){
    if(line.trim().startsWith('```')){flushList(); if(inCode){flushCode();inCode=false}else inCode=true;continue}
    if(inCode){code.push(line);continue}
    const h=line.match(/^(#{1,4})\s+(.+)$/); if(h){flushList();out.push(`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`);continue}
    const li=line.match(/^\s*[-*]\s+(.+)$/); if(li){list.push(li[1]);continue}
    flushList();
    if(!line.trim()){out.push('');continue}
    if(line.startsWith('> ')){out.push('<blockquote>'+inline(line.slice(2))+'</blockquote>');continue}
    out.push('<p>'+inline(line)+'</p>');
  }
  flushList(); if(inCode)flushCode();
  return out.join('\n');
}

export default function Markdown({ text }) {
  const html=useMemo(()=>renderMarkdown(text||''),[text]);
  return <div className="md" dir="auto" dangerouslySetInnerHTML={{__html:html}}/>;
}