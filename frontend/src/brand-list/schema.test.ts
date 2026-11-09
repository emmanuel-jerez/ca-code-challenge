// Contract test (ADR 0010, 0027): the API's recorded responses must satisfy
// the schema the component parses live responses with.
import { describe, expect, it } from 'vitest';

import fixture from '../../../contracts/brand-list.example.json';
import { BrandPage } from './schema';

describe('brand list contract', () => {
  it.each(['first_page', 'last_page', 'empty_page'] as const)(
    'accepts the recorded %s response',
    (name) => {
      const result = BrandPage.safeParse(fixture[name].body);

      expect(result.error).toBeUndefined();
    },
  );

  it.each(['invalid_query', 'page_not_found'] as const)(
    'rejects the %s error body as a page',
    (name) => {
      expect(BrandPage.safeParse(fixture[name].body).success).toBe(false);
    },
  );
});
