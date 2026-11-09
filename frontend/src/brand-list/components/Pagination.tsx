import type { MouseEvent } from 'react';

type PageItem = number | 'gap';

// Every page when there are few; otherwise the first, the last and the
// current one with its neighbours, with gaps between.
const SHOW_ALL_UP_TO = 7;

function pageItems(current: number, total: number): PageItem[] {
  if (total <= SHOW_ALL_UP_TO) return Array.from({ length: total }, (_, i) => i + 1);
  const pages = [...new Set([1, current - 1, current, current + 1, total])]
    .filter((page) => page >= 1 && page <= total)
    .sort((a, b) => a - b);
  return pages.flatMap((page, i): PageItem[] => {
    const prev = pages[i - 1];
    return prev !== undefined && page - prev > 1 ? ['gap', page] : [page];
  });
}

// A plain click stays in the page; modified clicks (new tab, new window)
// are left to the browser, which is why these are links, not buttons.
function isPlainClick(event: MouseEvent): boolean {
  return (
    event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey
  );
}

interface PaginationProps {
  readonly current: number;
  readonly total: number;
  readonly hrefFor: (page: number) => string;
  readonly onNavigate: (page: number) => void;
}

export function Pagination({ current, total, hrefFor, onNavigate }: PaginationProps) {
  if (total <= 1) return null;

  // aria-label rather than visually hidden text: the visible text ("2",
  // "Next") is part of each name, as WCAG 2.5.3 asks, and accessible-name
  // tools disagree on spaces inside hidden spans.
  const link = (page: number, text: string, label: string, isCurrent = false) => (
    <a
      className="c-pagination__link"
      href={hrefFor(page)}
      aria-label={label}
      aria-current={isCurrent ? 'page' : undefined}
      onClick={(event) => {
        if (!isPlainClick(event)) return;
        event.preventDefault();
        onNavigate(page);
      }}
    >
      {text}
    </a>
  );

  return (
    <nav className="c-pagination" aria-label="Pagination">
      <ul className="c-pagination__list">
        {/* At either end, plain text rather than a disabled link. */}
        <li className="c-pagination__item">
          {current > 1 ? (
            link(current - 1, 'Previous', 'Previous page')
          ) : (
            <span className="c-pagination__end">Previous</span>
          )}
        </li>
        {pageItems(current, total).map((item, i) =>
          item === 'gap' ? (
            <li key={`gap-${String(i)}`} className="c-pagination__item c-pagination__gap" aria-hidden="true">
              …
            </li>
          ) : (
            <li key={item} className="c-pagination__item">
              {link(item, String(item), `Page ${String(item)}`, item === current)}
            </li>
          ),
        )}
        <li className="c-pagination__item">
          {current < total ? (
            link(current + 1, 'Next', 'Next page')
          ) : (
            <span className="c-pagination__end">Next</span>
          )}
        </li>
      </ul>
    </nav>
  );
}
