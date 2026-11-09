// Contract test (ADR 0010, 0027): the API's recorded responses must satisfy
// the schema the component parses live responses with.
import { describe, expect, it, vi } from 'vitest';

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

describe('parsing under the CSP', () => {
  it('compiles no code from strings, which script-src without unsafe-eval forbids', async () => {
    // Fresh schemas: Zod compiles each one on its first parse, and the tests
    // above have parsed these already.
    vi.resetModules();
    const { BrandPage: FreshBrandPage } = await import('./schema');
    const compiled: unknown[] = [];
    const record = (args: unknown[]): void => {
      compiled.push(args);
    };
    vi.stubGlobal(
      'Function',
      new Proxy(Function, {
        construct: (target, args) => (record(args), Reflect.construct(target, args)),
        apply: (target, self, args) => (record(args), Reflect.apply(target, self, args)),
      }),
    );

    FreshBrandPage.parse(fixture.first_page.body);

    expect(compiled).toEqual([]);
  });
});

