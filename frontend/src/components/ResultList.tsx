import { useEffect, useRef } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';

import { SearchHit } from '../api';

interface ResultListProps {
  hits: SearchHit[];
  selectedIndex: number;
  onSelect: (index: number) => void;
  onCopy: (hit: SearchHit) => void;
}

export function ResultList({ hits, selectedIndex, onSelect, onCopy }: ResultListProps) {
  const parentRef = useRef<HTMLDivElement | null>(null);

  const virtualizer = useVirtualizer({
    count: hits.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 180,
    overscan: 8
  });

  useEffect(() => {
    if (hits.length > 0) {
      virtualizer.scrollToIndex(selectedIndex, { align: 'center' });
    }
  }, [selectedIndex, hits.length, virtualizer]);

  return (
    <div ref={parentRef} className="h-[calc(100vh-260px)] overflow-auto rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <div style={{ height: `${virtualizer.getTotalSize()}px`, position: 'relative' }}>
        {virtualizer.getVirtualItems().map((item) => {
          const hit = hits[item.index];
          const isSelected = item.index === selectedIndex;
          return (
            <div
              key={hit.file_id}
              ref={virtualizer.measureElement}
              data-index={item.index}
              className={`absolute left-0 right-0 rounded-lg border transition ${isSelected ? 'border-brand bg-brand/10 shadow-lg' : 'border-transparent'}`}
              style={{ transform: `translateY(${item.start}px)`, height: `${item.size}px`, paddingBottom: '1rem' }}
            >
              <button
                className="flex w-full flex-col items-start gap-2 rounded-lg px-4 py-3 text-left"
                onClick={() => onSelect(item.index)}
              >
                <div className="flex w-full items-center justify-between text-sm text-slate-300">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-slate-100">{hit.path}</span>
                    <span className="rounded bg-slate-800 px-2 py-0.5 font-mono text-xs text-slate-300">L{hit.line}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      className="rounded bg-slate-800 px-2 py-1 text-xs text-slate-300 hover:bg-slate-700"
                      onClick={(event) => {
                        event.stopPropagation();
                        onCopy(hit);
                      }}
                    >
                      Copy
                    </button>
                    <a
                      href={hit.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-brand hover:text-brand-dark"
                      onClick={(event) => event.stopPropagation()}
                    >
                      Open source
                    </a>
                  </div>
                </div>
                <pre
                  className="w-full overflow-x-auto rounded-md bg-slate-950/60 p-3 text-sm leading-relaxed text-slate-100"
                >
                  <code dangerouslySetInnerHTML={{ __html: hit.snippet }} />
                </pre>
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
