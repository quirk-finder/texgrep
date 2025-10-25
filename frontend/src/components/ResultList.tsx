import { useEffect, useRef, useMemo } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { SearchHit } from '../api';

interface ResultListProps {
  hits: SearchHit[];
  selectedIndex: number;
  onSelect: (index: number) => void;
  onCopy: (hit: SearchHit) => void;
}

function convertMarksInsideMath(html: string): string {
  const wrap = (s: string) => s.replace(/<mark>([\s\S]*?)<\/mark>/g, (_m, g1) => `\\class{mjx-hl}{${g1}}`);
  // display 数式（$$ ... $$）
  html = html.replace(/\$\$([\s\S]*?)\$\$/g, (_m, g1) => `$$${wrap(g1)}$$`);
  // display 数式（\[ ... \]）
  html = html.replace(/\\\[([\s\S]*?)\\\]/g, (_m, g1) => `\\[${wrap(g1)}\\]`);
  // inline 数式（$ ... $）
  html = html.replace(/\$([\s\S]*?)\$/g, (_m, g1) => `$${wrap(g1)}$`);
  return html;
}

function MathSnippet({ snippet }: { snippet: string }) {
  const htmlForMathJax = useMemo(
    () => convertMarksInsideMath(snippet),
    [snippet]
  );

  return (
    <div
      className="w-full rounded-md bg-slate-950/60 p-3 text-sm leading-relaxed text-slate-100
                 font-mono whitespace-pre-wrap break-words"
      dangerouslySetInnerHTML={{ __html: htmlForMathJax }}
    />
  );
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

  // 可視アイテムの“署名”（インデックス列）を作る
  const visibleItems = virtualizer.getVirtualItems();
  const visibleSig = visibleItems.map(v => v.key ?? v.index).join(',');

  // 可視範囲だけ MathJax を typeset → 終わったら高さを測り直す
  useEffect(() => {
    const el = parentRef.current as unknown as HTMLElement | null;
    const mj = (window as any).MathJax;
    if (!el || !mj?.typesetPromise) return;

    let cancelled = false;
    mj.typesetPromise([el]).then(() => {
      if (!cancelled) virtualizer.measure();
    }).catch(() => {/* noop */});

    return () => { cancelled = true; };
  }, [visibleSig, hits.length, virtualizer]);

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
              <div
                className="mb-4 flex w-full flex-col items-start gap-2 rounded-lg px-4 py-3 text-left cursor-pointer"
                role="button"
                tabIndex={0}
                onClick={() => onSelect(item.index)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();           // Space でのスクロール抑止
                    onSelect(item.index);
                  }
                }}
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
                        e.stopPropagation();       // 親の onClick に伝播させない
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

                <MathSnippet snippet={hit.snippet} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
