import { describe, expect, it } from 'vitest';

import { type ListingQuery, apiUrl, parseQuery, toSearch } from './urlQuery';

const DEFAULTS: ListingQuery = { industries: [], ordering: '-average_rating', page: 1 };

const KNOWN = new Set(['finance', 'insurance', 'telecom']);

describe('parseQuery', () => {
  it('reads industries, ordering and page from the address bar', () => {
    expect(parseQuery('?industry=telecom&ordering=review_count&page=2', KNOWN)).toEqual({
      industries: ['telecom'],
      ordering: 'review_count',
      page: 2,
    });
  });

  it('falls back to the defaults when nothing is set', () => {
    expect(parseQuery('', KNOWN)).toEqual(DEFAULTS);
  });

  it('keeps only known industries, once each, in a stable order', () => {
    const query = parseQuery(
      '?industry=telecom&industry=nope&industry=finance&industry=telecom',
      KNOWN,
    );

    expect(query.industries).toEqual(['finance', 'telecom']);
  });

  it.each(['name', '', '-name', 'average_rating,id'])(
    'replaces unknown ordering %j with the default',
    (ordering) => {
      expect(parseQuery(`?ordering=${ordering}`, KNOWN).ordering).toBe('-average_rating');
    },
  );

  it.each(['0', '-1', '1.5', 'abc', '', '02', '99999999999999999999'])(
    'replaces page %j with page 1',
    (page) => {
      expect(parseQuery(`?page=${page}`, KNOWN).page).toBe(1);
    },
  );
});

describe('toSearch', () => {
  it('writes nothing for the default query', () => {
    expect(toSearch(DEFAULTS, '')).toBe('');
  });

  it('writes industries, then ordering, then page, omitting defaults', () => {
    const search = toSearch(
      { industries: ['finance', 'telecom'], ordering: 'review_count', page: 3 },
      '',
    );

    expect(search).toBe('?industry=finance&industry=telecom&ordering=review_count&page=3');
  });

  it('keeps parameters it does not own and replaces the ones it does', () => {
    const search = toSearch(
      { ...DEFAULTS, industries: ['finance'] },
      '?utm_source=mail&industry=nope&page=4',
    );

    expect(search).toBe('?utm_source=mail&industry=finance');
  });
});

describe('apiUrl', () => {
  it('asks the API for the query with an explicit page size', () => {
    const url = apiUrl('/api/brands/', { industries: ['telecom'], ordering: 'review_count', page: 2 });

    expect(url).toBe('/api/brands/?industry=telecom&ordering=review_count&page=2&page_size=12');
  });
});
