import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';

import { SearchFilters, SearchHit, SearchMode, searchTex, SearchRequest, SearchResponse } from './api';
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

  const providerRaw = import.meta.env.VITE_PROVIDER ?? 'unknown';
  const provider = providerRaw.toString().trim().toLowerCase();
  const regexEnabled = provider === 'zoekt';

  const debouncedQuery = useDebouncedValue(query.trim());
  const PAGE_SIZE = 20;
  const requestPayload = useMemo<SearchRequest | undefined>(() => {
    if (!debouncedQuery) return undefined;
    return { q: debouncedQuery, mode, filters, size: PAGE_SIZE };
  }, [debouncedQuery, mode, filters]);

  const {
    data,
    isFetching,
    refetch,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage
  } = useInfiniteQuery({
    queryKey: ['search', requestPayload],
    queryFn: async ({ pageParam }: { pageParam?: { page?: number; cursor?: string | null } }) => {
      if (!requestPayload) {
        return {
          hits: [],
          total: 0,
          took_provider_ms: 0,
          took_end_to_end_ms: 0,
          page: 1,
          size: PAGE_SIZE,
          next_cursor: null
        };
      }

      const payload = { ...requestPayload };
      const cursor = pageParam?.cursor ?? null;
      if (cursor) {
        delete payload.page;
        payload.cursor = cursor;
      } else {
        payload.page = pageParam?.page ?? 1;
        delete payload.cursor;
      }

      return searchTex(payload);
    },
    getNextPageParam: (lastPage) => {
      if (lastPage.next_cursor) {
        return { cursor: lastPage.next_cursor };
      }
      if (lastPage.hits.length >= lastPage.size) {
        return { page: lastPage.page + 1 };
      }
      return undefined;
    },
    initialPageParam: { page: 1 },
    enabled: Boolean(requestPayload)
  });

  useEffect(() => {
    if (!document.getElementById('mathjax-script')) {
      // ① 設定を先に入れる
      (window as any).MathJax = {
        loader: { load: ['[tex]/html'] },
        tex: {
          inlineMath: [['$', '$'], ['\\(', '\\)']],
          processEscapes: true,
          // これがポイント：\begin{...} をページ全体で拾わない
          processEnvironments: false,
          // 必要なら追加パッケージ
          packages: { '[+]': ['ams', 'html'] },
        },
        // pre/code はデフォルトでスキップされるので、後で <div> に出す
        options: {
          // MathJax にこの要素だけを typeset させたい時に使う
          renderActions: {}
        }
      };
      const script = document.createElement('script');
      script.id = 'mathjax-script';
      script.async = true;
      script.src = 'https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js';
      document.head.appendChild(script);
    }
  }, []);

  const pages = data?.pages ?? [];
  const hits = useMemo(() => pages.flatMap((page) => page.hits), [pages]);
  const total = pages.length > 0 ? pages[0].total : undefined;
  const tookEndToEndMs = pages.length > 0 ? pages[pages.length - 1].took_end_to_end_ms : undefined;

  useEffect(() => {
    if (!regexEnabled && mode === 'regex') {
      setMode('literal');
    }
  }, [mode, regexEnabled]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [debouncedQuery, mode, filters]);

  useKeyboardShortcuts({
    focusSearch: () => inputRef.current?.focus(),
    toggleRegex: () => {
      if (!regexEnabled) return;
      setMode((current) => (current === 'literal' ? 'regex' : 'literal'));
    },
    selectNext: () =>
      setSelectedIndex((index) => {
        const maxIndex = Math.max(hits.length - 1, 0);
        return Math.min(maxIndex, index + 1);
      }),
    selectPrev: () => setSelectedIndex((index) => Math.max(0, index - 1)),
    regexEnabled
  });

  const totalResultsForDisplay = total ?? hits.length;
  const statusText = isFetchingNextPage
    ? 'Loading more…'
    : isFetching
      ? 'Searching…'
      : `${totalResultsForDisplay} results`;

  const handleEndReached = useCallback(() => {
    if (!hasNextPage || isFetchingNextPage) return;
    fetchNextPage();
  }, [fetchNextPage, hasNextPage, isFetchingNextPage]);

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
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-slate-500">
              <span>Provider</span>
              <span className="rounded border border-slate-800 bg-slate-900 px-2 py-1 font-mono text-[0.7rem] text-slate-300">
                {provider}
              </span>
            </div>
            <span className="rounded-full border border-slate-800 bg-slate-900 px-3 py-1 text-xs uppercase tracking-wide text-slate-400">
              {statusText}
            </span>
          </div>
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
          regexEnabled={regexEnabled}
          total={total}
          tookEndToEndMs={tookEndToEndMs}
        />
      </header>
      {debouncedQuery ? (
        <ResultList
          hits={hits}
          selectedIndex={selectedIndex}
          onSelect={setSelectedIndex}
          onCopy={handleCopy}
          onEndReached={handleEndReached}
          hasMore={Boolean(hasNextPage)}
          isLoadingMore={isFetchingNextPage}
        />
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
