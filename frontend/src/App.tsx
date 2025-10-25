import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { SearchFilters, SearchHit, SearchMode, searchTex } from './api';
import { ResultList } from './components/ResultList';
import { SearchForm } from './components/SearchForm';
import { useDebouncedValue } from './hooks/useDebouncedValue';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';

interface MathJaxGlobal {
  typesetPromise?: () => Promise<void>;
}

declare global {
  interface Window {
    MathJax?: MathJaxGlobal;
  }
}

const DEFAULT_FILTERS: SearchFilters = { source: 'samples' };

export default function App() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState<SearchMode>('literal');
  const [filters, setFilters] = useState<SearchFilters>(DEFAULT_FILTERS);
  const [selectedIndex, setSelectedIndex] = useState(0);

  const debouncedQuery = useDebouncedValue(query.trim());
  const requestPayload = useMemo(() => {
    if (!debouncedQuery) return undefined;
    return { q: debouncedQuery, mode, filters, size: 20 };
  }, [debouncedQuery, mode, filters]);

  const { data, isFetching, refetch } = useQuery({
    queryKey: ['search', requestPayload],
    queryFn: () => (requestPayload ? searchTex(requestPayload) : Promise.resolve({ hits: [], total: 0, took_ms: 0 })),
    enabled: Boolean(requestPayload)
  });

  useEffect(() => {
    if (!document.getElementById('mathjax-script')) {
      const script = document.createElement('script');
      script.id = 'mathjax-script';
      script.async = true;
      script.src = 'https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js';
      document.head.appendChild(script);
    }
  }, []);

  useEffect(() => {
    if (window.MathJax?.typesetPromise) {
      window.MathJax.typesetPromise();
    }
  }, [data?.hits]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [data?.hits]);

  useKeyboardShortcuts({
    focusSearch: () => inputRef.current?.focus(),
    toggleRegex: () => setMode((current) => (current === 'literal' ? 'regex' : 'literal')),
    selectNext: () => setSelectedIndex((index) => Math.min(Math.max((data?.hits.length || 0) - 1, 0), index + 1)),
    selectPrev: () => setSelectedIndex((index) => Math.max(0, index - 1))
  });

  const hits = data?.hits ?? [];
  const total = hits.length;

  const handleCopy = async (hit: SearchHit) => {
    try {
      const queryText = requestPayload?.q ?? query;
      await navigator.clipboard.writeText(`${hit.path}:${hit.line}\n${queryText}\n${hit.url}`);
    } catch (error) {
      console.error('Failed to copy snippet', error);
    }
  };

  return (
    <div className="mx-auto flex min-h-screen max-w-6xl flex-col gap-6 px-6 py-8">
      <header className="space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold text-white">texgrep.app</h1>
          <span className="rounded-full border border-slate-800 bg-slate-900 px-3 py-1 text-xs uppercase tracking-wide text-slate-400">
            {isFetching ? 'Searching…' : `${total} results`}
          </span>
        </div>
        <SearchForm
          query={query}
          onQueryChange={setQuery}
          mode={mode}
          onModeChange={setMode}
          filters={filters}
          onFiltersChange={setFilters}
          onSubmit={() => refetch()}
          inputRef={inputRef}
        />
      </header>
      {debouncedQuery ? (
        <ResultList hits={hits} selectedIndex={selectedIndex} onSelect={setSelectedIndex} onCopy={handleCopy} />
      ) : (
        <div className="flex flex-1 items-center justify-center rounded-3xl border border-dashed border-slate-800 bg-slate-900/50">
          <div className="text-center text-slate-400">
            <p className="text-xl font-semibold">Search for LaTeX commands and environments</p>
            <p className="mt-3 text-sm">Try queries like <code>\\iiint</code>, <code>\\newcommand</code>, or <code>\\tikzpicture</code>.</p>
          </div>
        </div>
      )}
    </div>
  );
}
