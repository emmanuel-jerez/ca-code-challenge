import { useEffect, useId, useMemo, useRef, useState } from 'react';

import { BrandGrid, SkeletonGrid } from './components/BrandGrid';
import { BrandFilters } from './components/BrandFilters';
import { EmptyState } from './components/EmptyState';
import { ErrorState } from './components/ErrorState';
import { Pagination } from './components/Pagination';
import type { Industry } from './schema';
import { statusMessage } from './statusMessage';
import { type BrandsState, useBrands } from './useBrands';
import {
  type EntrySource,
  currentEntrySource,
  navigate,
  useLocationSearch,
} from './useLocationSearch';
import { type ListingQuery, apiUrl, pageCount, parseQuery, toSearch } from './urlQuery';

export interface BrandListProps {
  /** The listing endpoint, e.g. `/api/brands/`. */
  readonly apiUrl: string;
  /** Every industry the filter offers, from the page (json_script). */
  readonly industries: readonly Industry[];
}

export function BrandList({ apiUrl: endpoint, industries }: BrandListProps) {
  const search = useLocationSearch();
  const knownSlugs = useMemo(() => new Set(industries.map((i) => i.slug)), [industries]);
  const query = useMemo(() => parseQuery(search, knownSlugs), [search, knownSlugs]);

  // Correct a hand-edited or stale URL in place: a correction, not a
  // navigation, so it replaces the entry. The request already uses the
  // corrected query, so this doesn't refetch.
  const canonicalSearch = toSearch(query, search);
  useEffect(() => {
    if (canonicalSearch !== search) {
      navigate(canonicalSearch, 'replace', currentEntrySource() ?? 'other');
    }
  }, [canonicalSearch, search]);

  const [reloadKey, setReloadKey] = useState(0);
  const requestUrl = apiUrl(endpoint, query);
  const loaded = useBrands(requestUrl, reloadKey);

  // A page past the end (fewer brands since the link was made) is DRF's 404.
  // Go to page 1 instead of showing an error; a correction, so replace.
  const pageGone =
    loaded.status === 'error' &&
    loaded.error.kind === 'http' &&
    loaded.error.status === 404 &&
    query.page > 1;
  useEffect(() => {
    if (pageGone) {
      navigate(toSearch({ ...query, page: 1 }, search), 'replace', currentEntrySource() ?? 'other');
    }
  }, [pageGone, query, search]);
  // Shown as loading until page 1 arrives, so the alert doesn't flash.
  const state: BrandsState = pageGone ? { status: 'loading', previous: null } : loaded;

  const headingId = useId();
  const headingRef = useRef<HTMLHeadingElement>(null);
  const filteredBy = industries.filter((industry) => query.industries.includes(industry.slug));

  // Announce only once the user has changed something: reading the count on
  // page load is chatter. Set during render, React's pattern for state that
  // follows a change in props or other state.
  const [firstRequest] = useState(requestUrl);
  const [announce, setAnnounce] = useState(false);
  if (!announce && (requestUrl !== firstRequest || reloadKey > 0)) setAnnounce(true);

  // Every user change is a new history entry, so Back undoes it, except that
  // repeated sort changes share one entry (arrow keys on a select can fire a
  // change per keypress). A filter or sort change starts again at page 1.
  const update = (next: ListingQuery, source: EntrySource) => {
    const mode = source === 'ordering' && currentEntrySource() === 'ordering' ? 'replace' : 'push';
    navigate(toSearch(next, window.location.search), mode, source);
  };

  // For actions whose button disappears (Clear filters, Retry, a page link):
  // without this, focus would fall back to <body>. Filter and sort changes
  // leave focus alone; moving it would be a change of context (WCAG 3.2.2).
  const focusResults = () => {
    headingRef.current?.focus();
  };

  const clearFilters = () => {
    update({ ...query, industries: [], page: 1 }, 'other');
    focusResults();
  };

  return (
    <div className="c-brand-list">
      <BrandFilters
        industries={industries}
        query={query}
        onIndustriesChange={(slugs) => {
          update({ ...query, industries: [...slugs].sort(), page: 1 }, 'other');
        }}
        onOrderingChange={(ordering) => {
          update({ ...query, ordering, page: 1 }, 'ordering');
        }}
        onClear={clearFilters}
      />
      <section className="c-brand-list__results" aria-labelledby={headingId}>
        <h2 className="c-brand-list__heading" id={headingId} ref={headingRef} tabIndex={-1}>
          Results
        </h2>
        {/* Always mounted: a live region must exist before its text changes. */}
        <p className="u-visually-hidden" role="status" aria-live="polite">
          {announce ? statusMessage(state, query, filteredBy) : ''}
        </p>
        {state.status === 'loading' &&
          (state.previous ? <BrandGrid brands={state.previous.results} stale /> : <SkeletonGrid />)}
        {state.status === 'error' && (
          <ErrorState
            error={state.error}
            onRetry={() => {
              setReloadKey((key) => key + 1);
              focusResults();
            }}
          />
        )}
        {state.status === 'success' &&
          (state.page.results.length === 0 ? (
            <EmptyState filteredBy={filteredBy} onClear={clearFilters} />
          ) : (
            <BrandGrid brands={state.page.results} />
          ))}
        {state.status === 'success' && (
          <Pagination
            current={query.page}
            total={pageCount(state.page.count)}
            hrefFor={(page) => `${window.location.pathname}${toSearch({ ...query, page }, search)}`}
            onNavigate={(page) => {
              update({ ...query, page }, 'other');
              focusResults();
            }}
          />
        )}
      </section>
    </div>
  );
}
