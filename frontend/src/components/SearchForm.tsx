import { ChangeEvent, FormEvent } from 'react';

import { SearchFilters, SearchMode } from '../api';

interface SearchFormProps {
  query: string;
  onQueryChange: (value: string) => void;
  mode: SearchMode;
  onModeChange: (mode: SearchMode) => void;
  filters: SearchFilters;
  onFiltersChange: (filters: SearchFilters) => void;
  onSubmit: () => void;
  inputRef: React.RefObject<HTMLInputElement>;
  regexEnabled: boolean;
  total?: number;
  tookEndToEndMs?: number;
}

export function SearchForm({
  query,
  onQueryChange,
  mode,
  onModeChange,
  filters,
  onFiltersChange,
  onSubmit,
  inputRef,
  regexEnabled,
  total,
  tookEndToEndMs
}: SearchFormProps) {
  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit();
  };

  const updateFilter = (key: keyof SearchFilters) => (event: ChangeEvent<HTMLSelectElement | HTMLInputElement>) => {
    onFiltersChange({ ...filters, [key]: event.target.value || undefined });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="flex items-center gap-3">
        <input
          ref={inputRef}
          type="search"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="Search LaTeX…"
          className="flex-1 rounded-lg border border-slate-700 bg-slate-900 px-4 py-3 text-lg shadow-inner focus:border-brand focus:outline-none"
        />
        <div className="flex overflow-hidden rounded-lg border border-slate-700">
          {(['literal', 'regex'] as SearchMode[]).map((modeOption) => (
            <button
              key={modeOption}
              type="button"
              onClick={() => {
                if (modeOption === 'regex' && !regexEnabled) return;
                onModeChange(modeOption);
              }}
              disabled={modeOption === 'regex' && !regexEnabled}
              title={modeOption === 'regex' && !regexEnabled ? 'Regex search is available only when using the Zoekt provider.' : undefined}
              className={`px-4 py-2 text-sm font-medium ${
                modeOption === mode
                  ? 'bg-brand text-white'
                  : 'bg-slate-900 text-slate-300'
              } ${modeOption === 'regex' && !regexEnabled ? 'cursor-not-allowed opacity-60' : ''}`}
            >
              {modeOption === 'literal' ? 'Literal' : 'Regex'}
            </button>
          ))}
        </div>
        <button
          type="submit"
          className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold uppercase tracking-wide text-white shadow hover:bg-brand-dark"
        >
          Search
        </button>
      </div>
      <div className="flex flex-wrap items-center gap-4 text-sm text-slate-300">
        <label className="flex items-center gap-2">
          <span className="text-slate-400">Source</span>
          <select
            value={filters.source ?? ''}
            onChange={updateFilter('source')}
            className="rounded-md border border-slate-700 bg-slate-900 px-2 py-1"
          >
            <option value="">All</option>
            <option value="samples">Samples</option>
            <option value="arxiv">arXiv</option>
          </select>
        </label>
        <label className="flex items-center gap-2">
          <span className="text-slate-400">Year</span>
          <input
            value={filters.year ?? ''}
            onChange={updateFilter('year')}
            placeholder="2024"
            className="w-24 rounded-md border border-slate-700 bg-slate-900 px-2 py-1"
          />
        </label>
        <div className="ml-auto flex flex-col items-end gap-1 text-xs uppercase tracking-wide text-slate-500">
          <div className="flex gap-3">
            <span>Total: {total ?? '–'}</span>
            <span>End-to-end: {typeof tookEndToEndMs === 'number' ? `${Math.round(tookEndToEndMs)} ms` : '–'}</span>
          </div>
          <p>
            ⌘K focus · {regexEnabled ? 'Alt+R regex' : 'Alt+R regex (Zoekt only)'} · j/k move
          </p>
        </div>
      </div>
    </form>
  );
}
