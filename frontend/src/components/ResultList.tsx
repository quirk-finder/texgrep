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
    estimateSize: () => 180,            // 初期推定だけ。実測が上書きします
    overscan: 8,
    // ← 安定した key を渡す（React と virtualizer の両方で活用される）
    getItemKey: (index) => `${hits[index]?.file_id}:${hits[index]?.line}`,
  });

  // 選択移動したらスクロール
  useEffect(() => {
    if (hits.length > 0) {
      virtualizer.scrollToIndex(selectedIndex, { align: 'center' });
    }
  }, [selectedIndex, hits.length, virtualizer]);

  // ヒットが変わった（ハイライト増減・MathJax 等で高さ変化）ら再測定
  useEffect(() => {
    const id = requestAnimationFrame(() => virtualizer.measure());
    return () => cancelAnimationFrame(id);
  }, [hits, virtualizer]);

  return (
    <div
      ref={parentRef}
      className="h-[calc(100vh-260px)] overflow-auto rounded-xl border border-slate-800 bg-slate-900/60 p-4"
    >
      <div style={{ height: virtualizer.getTotalSize(), position: 'relative' }}>
        {virtualizer.getVirtualItems().map((item) => {
          const hit = hits[item.index];
          if (!hit) return null;

          const isSelected = item.index === selectedIndex;

          return (
            <div
              key={`${hit.file_id}:${hit.line}`}  // ← 衝突しない key
              ref={virtualizer.measureElement}     // ← 実測対象
              data-index={item.index}
              className={`absolute left-0 right-0 rounded-lg border transition ${
                isSelected ? 'border-brand bg-brand/10 shadow-lg' : 'border-transparent'
              } pb-4`}                               // ← 余白はクラスで（高さに含まれる）
              style={{ transform: `translateY(${item.start}px)` }} // ← height 指定は削除
            >
              <button
                className="mb-4 flex w-full flex-col items-start gap-2 rounded-lg px-4 py-3 text-left"
                onClick={() => onSelect(item.index)}
              >
                <div className="flex w-full items-center justify-between text-sm text-slate-300">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-slate-100">{hit.path}</span>
                    <span className="rounded bg-slate-800 px-2 py-0.5 font-mono text-xs text-slate-300">
                      L{hit.line}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      className="rounded bg-slate-800 px-2 py-1 text-xs text-slate-300 hover:bg-slate-700"
                      onClick={(e) => {
                        e.stopPropagation();
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
                      onClick={(e) => e.stopPropagation()}
                    >
                      Open source
                    </a>
                  </div>
                </div>

                <pre
                  className="w-full overflow-x-auto whitespace-pre-wrap break-words rounded-md bg-slate-950/60 p-3 text-sm leading-relaxed text-slate-100"
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
