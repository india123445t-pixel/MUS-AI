import React, { useMemo } from 'react';
import { marked } from 'marked';

marked.setOptions({ breaks: true });

// Minimal sanitizer: strip script/style tags and inline event handlers.
function sanitize(html) {
  return html
    .replace(/<\s*(script|style|iframe|object|embed)[^>]*>[\s\S]*?<\s*\/\s*\1\s*>/gi, '')
    .replace(/<\s*(script|iframe|object|embed)[^>]*\/?>/gi, '')
    .replace(/\son\w+\s*=\s*(".*?"|'.*?'|[^\s>]+)/gi, '')
    .replace(/javascript:/gi, '');
}

export default function Markdown({ text }) {
  const html = useMemo(() => sanitize(marked.parse(text || '')), [text]);
  return <div className="md" dir="auto" dangerouslySetInnerHTML={{ __html: html }} />;
}
