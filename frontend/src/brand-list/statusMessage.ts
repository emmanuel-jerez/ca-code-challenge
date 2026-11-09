import type { BrandsState } from './useBrands';
import type { Industry } from './schema';
import { ORDERING_LABELS, type ListingQuery, pageCount } from './urlQuery';

/**
 * The status region's text: a short summary, the textbook status message
 * (WCAG 4.1.3). Errors are left to the alert, so they aren't read twice.
 */
export function statusMessage(
  state: BrandsState,
  query: ListingQuery,
  filteredBy: readonly Industry[],
): string {
  switch (state.status) {
    case 'loading':
      return 'Loading brands…';
    case 'error':
      return '';
    case 'success': {
      const { count } = state.page;
      const parts = [count === 1 ? '1 brand.' : `${String(count)} brands.`];
      if (filteredBy.length > 0) parts.push(`${filteredBy.map((i) => i.name).join(', ')}.`);
      parts.push(`Sorted by ${ORDERING_LABELS[query.ordering].toLowerCase()}.`);
      parts.push(`Page ${String(query.page)} of ${String(pageCount(count))}.`);
      return parts.join(' ');
    }
  }
}
