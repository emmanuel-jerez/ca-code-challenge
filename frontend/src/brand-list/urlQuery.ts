// The listing's state lives in the page URL (shareable, Back works). These
// pure functions turn an untrusted query string into a canonical query and
// back. The page URL uses the API's parameter names (ADR 0022), so one
// serialization serves both.

export const ORDERINGS = [
  '-average_rating',
  'average_rating',
  '-review_count',
  'review_count',
] as const;
export type Ordering = (typeof ORDERINGS)[number];

export const ORDERING_LABELS: Record<Ordering, string> = {
  '-average_rating': 'Highest rated',
  average_rating: 'Lowest rated',
  '-review_count': 'Most reviews',
  review_count: 'Fewest reviews',
};

export interface ListingQuery {
  /** Known industry slugs, de-duplicated and sorted. Empty means all. */
  readonly industries: readonly string[];
  readonly ordering: Ordering;
  /** 1-based. */
  readonly page: number;
}

const DEFAULT_QUERY: ListingQuery = {
  industries: [],
  ordering: '-average_rating',
  page: 1,
};

// The parameters this component owns. Anything else in the address bar
// (utm_*, for example) is left alone.
const OWN_PARAMS = ['industry', 'ordering', 'page'] as const;

export function isOrdering(value: string | null): value is Ordering {
  return ORDERINGS.some((ordering) => ordering === value);
}

// Digits only, no leading zero, so each page has exactly one spelling.
const PAGE_PATTERN = /^[1-9]\d*$/;

function parsePage(value: string | null): number {
  if (value === null || !PAGE_PATTERN.test(value)) return 1;
  const page = Number(value);
  return Number.isSafeInteger(page) ? page : 1;
}

export function parseQuery(search: string, knownIndustries: ReadonlySet<string>): ListingQuery {
  const params = new URLSearchParams(search);
  const industries = [...new Set(params.getAll('industry'))]
    .filter((slug) => knownIndustries.has(slug))
    .sort();
  const ordering = params.get('ordering');
  return {
    industries,
    ordering: isOrdering(ordering) ? ordering : DEFAULT_QUERY.ordering,
    page: parsePage(params.get('page')),
  };
}

// The canonical parameters for a query: defaults omitted, fixed order.
function queryParams(query: ListingQuery): URLSearchParams {
  const params = new URLSearchParams();
  for (const slug of query.industries) params.append('industry', slug);
  if (query.ordering !== DEFAULT_QUERY.ordering) params.set('ordering', query.ordering);
  if (query.page !== 1) params.set('page', String(query.page));
  return params;
}

/** The page's query string for `query`, keeping parameters this component doesn't own. */
export function toSearch(query: ListingQuery, currentSearch: string): string {
  const params = new URLSearchParams(currentSearch);
  for (const name of OWN_PARAMS) params.delete(name);
  for (const [name, value] of queryParams(query)) params.append(name, value);
  const search = params.toString();
  return search === '' ? '' : `?${search}`;
}

// Sent explicitly so page counts don't depend on the server's default.
const PAGE_SIZE = 12;

/** The API request for `query`. Never forwards the page's other parameters. */
export function apiUrl(endpoint: string, query: ListingQuery): string {
  const params = queryParams(query);
  params.set('page_size', String(PAGE_SIZE));
  return `${endpoint}?${params.toString()}`;
}

/** How many pages `count` brands fill; at least 1, so "page 1 of 1" holds for none. */
export function pageCount(count: number): number {
  return Math.max(1, Math.ceil(count / PAGE_SIZE));
}
