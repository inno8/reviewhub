/**
 * Shared Shiki highlighter singleton — one instance per page load, reused by
 * InlineCommentEditor and DiffInlineViewer. Lazy-imports shiki so the
 * bundle only pulls it in when a teacher opens a session detail view.
 */
const state: { highlighter: any; loader: Promise<any> | null } = {
  highlighter: null,
  loader: null,
};

export async function getSharedHighlighter(): Promise<any> {
  if (state.highlighter) return state.highlighter;
  if (state.loader) return state.loader;
  state.loader = (async () => {
    try {
      const shiki = await import('shiki');
      state.highlighter = await shiki.createHighlighter({
        themes: ['github-dark'],
        langs: [],
      });
      return state.highlighter;
    } catch (err) {
      console.warn('Shiki failed to load', err);
      return null;
    }
  })();
  return state.loader;
}

const EXT_LANG: Record<string, string> = {
  js: 'javascript', mjs: 'javascript', cjs: 'javascript', jsx: 'jsx',
  ts: 'typescript', tsx: 'tsx',
  py: 'python',
  rb: 'ruby',
  go: 'go',
  rs: 'rust',
  java: 'java',
  kt: 'kotlin',
  cs: 'csharp',
  cpp: 'cpp', cc: 'cpp', cxx: 'cpp', hpp: 'cpp', h: 'c',
  c: 'c',
  php: 'php',
  sh: 'bash', bash: 'bash', zsh: 'bash',
  yml: 'yaml', yaml: 'yaml',
  json: 'json',
  html: 'html', htm: 'html',
  css: 'css', scss: 'scss', sass: 'sass',
  vue: 'vue',
  md: 'markdown', markdown: 'markdown',
  sql: 'sql',
  xml: 'xml',
  toml: 'toml',
};

export function detectLangFromPath(filePath: string | undefined | null): string {
  if (!filePath) return 'text';
  const ext = filePath.split('.').pop()?.toLowerCase() || '';
  return EXT_LANG[ext] || 'text';
}

export async function ensureLanguage(lang: string): Promise<any> {
  const hl = await getSharedHighlighter();
  if (!hl) return null;
  if (lang && lang !== 'text') {
    const loaded = hl.getLoadedLanguages?.() || [];
    if (!loaded.includes(lang)) {
      try {
        await hl.loadLanguage(lang);
      } catch {
        /* fallback: render as text */
      }
    }
  }
  return hl;
}

export async function highlightCode(code: string, lang: string): Promise<string> {
  if (!code) return '';
  const hl = await ensureLanguage(lang);
  if (!hl) return '';
  try {
    return hl.codeToHtml(code, { lang: lang === 'text' ? 'text' : lang, theme: 'github-dark' });
  } catch {
    return '';
  }
}

/**
 * Tokenize code line-by-line and return one HTML string per line. Preserves
 * empty lines as a non-breaking space so the row still has height.
 */
export async function highlightLines(code: string, lang: string): Promise<string[]> {
  const hl = await ensureLanguage(lang);
  if (!hl) return code.split(/\r?\n/).map(escapeHtml);
  try {
    const tokens = hl.codeToTokensBase(code, {
      lang: lang === 'text' ? 'text' : lang,
      theme: 'github-dark',
    });
    return tokens.map((lineTokens: any[]) => {
      if (!lineTokens.length) return '&nbsp;';
      return lineTokens
        .map(t => {
          const color = t.color ? ` style="color:${t.color}"` : '';
          return `<span${color}>${escapeHtml(t.content)}</span>`;
        })
        .join('');
    });
  } catch {
    return code.split(/\r?\n/).map(escapeHtml);
  }
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
