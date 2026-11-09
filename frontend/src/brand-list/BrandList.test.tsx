import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axe from 'axe-core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import fixture from '../../../contracts/brand-list.example.json';
import { BrandList } from './BrandList';

const INDUSTRIES = [
  { slug: 'finance', name: 'Finance' },
  { slug: 'insurance', name: 'Insurance' },
  { slug: 'telecom', name: 'Telecom' },
];

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

/** Stubs fetch; each call gets the next response. Returns the mock for URL assertions. */
function stubFetch(...responses: (() => Promise<Response>)[]) {
  const fetchMock = vi.fn((_url: string, _init?: RequestInit) => {
    const next = responses.shift();
    if (!next) throw new Error('Unexpected fetch');
    return next();
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

/** The text assistive tech reads: textContent without aria-hidden parts. */
function spokenText(element: Element | null): string {
  if (!element) throw new Error('No element');
  const clone = element.cloneNode(true) as Element;
  for (const hidden of clone.querySelectorAll('[aria-hidden="true"]')) hidden.remove();
  return clone.textContent;
}

function deferred() {
  const { promise, resolve } = Promise.withResolvers<Response>();
  return { promise: () => promise, resolve };
}

/**
 * Runs axe on the rendered component. Rules jsdom can't evaluate are off:
 * color-contrast and target-size need layout (checked in a real browser),
 * and region expects a whole page around the component.
 */
async function axeViolations(container: Element): Promise<string[]> {
  const results = await axe.run(container, {
    rules: {
      'color-contrast': { enabled: false },
      'target-size': { enabled: false },
      region: { enabled: false },
    },
  });
  return results.violations.map((violation) => `${violation.id}: ${violation.help}`);
}

function renderBrandList() {
  return render(<BrandList apiUrl="/api/brands/" industries={INDUSTRIES} />);
}

beforeEach(() => {
  window.history.replaceState(null, '', '/brand/');
});

describe('BrandList', () => {
  it('shows a card for each brand, linking to its page', async () => {
    stubFetch(async () => json(fixture.first_page.body));

    renderBrandList();

    const list = await screen.findByRole('list', { name: 'Brands' });
    const links = within(list).getAllByRole('link');
    expect(links.map((link) => [link.textContent, link.getAttribute('href')])).toEqual([
      ['New Brand', '/brand/new-brand/'],
      ['PrimePath Bank', '/brand/primepath-bank/'],
    ]);
  });

  it('shows each card\'s industry, rating, review count, description and top review', async () => {
    stubFetch(async () => json(fixture.first_page.body));

    renderBrandList();

    const card = (await screen.findByRole('heading', { name: 'PrimePath Bank' })).closest('article');
    // The snippet is plain text: its <by far> must show literally, not become markup.
    expect(spokenText(card)).toBe(
      [
        'Finance',
        'PrimePath Bank',
        '4.0 out of 5',
        '1 review',
        'A regional retail bank with 220 branches.',
        "Support beat AT&T's <by far> & the app works.",
        "Roberto G. on Better than AT&T's support",
      ].join(''),
    );
  });

  it('says a brand without reviews is not rated yet', async () => {
    stubFetch(async () => json(fixture.first_page.body));

    renderBrandList();

    const card = (await screen.findByRole('heading', { name: 'New Brand' })).closest('article');
    expect(spokenText(card)).toBe(['Insurance', 'New Brand', 'Not rated yet', '0 reviews'].join(''));
  });

  it('draws ratings like the server-rendered cards: stars rounded down, value half up', async () => {
    const [brand] = fixture.first_page.body.results.slice(1);
    const rated = (name: string, average_rating: number) => ({ ...brand, slug: name, name, average_rating });
    stubFetch(async () =>
      json({ ...fixture.first_page.body, results: [rated('Low', 3.95), rated('High', 4.05)] }),
    );

    renderBrandList();

    const low = (await screen.findByRole('heading', { name: 'Low' })).closest('article');
    const high = screen.getByRole('heading', { name: 'High' }).closest('article');
    expect(low?.querySelector('[aria-hidden="true"]')?.textContent).toBe('★★★☆☆');
    expect(spokenText(high)).toContain('4.1 out of 5');
  });

  it('filters by industry from the keyboard, as a new history entry starting at page 1', async () => {
    window.history.replaceState(null, '', '/brand/?page=2&utm_source=mail');
    const fetchMock = stubFetch(
      async () => json(fixture.last_page.body),
      async () => json(fixture.empty_page.body),
    );
    const user = userEvent.setup();
    renderBrandList();
    await screen.findByRole('list', { name: 'Brands' });
    const historyLength = window.history.length;

    screen.getByRole('checkbox', { name: 'Telecom' }).focus();
    await user.keyboard('[Space]');

    expect(window.location.search).toBe('?utm_source=mail&industry=telecom');
    expect(window.history.length).toBe(historyLength + 1);
    expect(fetchMock).toHaveBeenLastCalledWith(
      '/api/brands/?industry=telecom&page_size=12',
      expect.anything(),
    );
  });

  it('sorts, folding repeated sort changes into one history entry', async () => {
    const page = async () => json(fixture.first_page.body);
    const fetchMock = stubFetch(page, page, page);
    const user = userEvent.setup();
    renderBrandList();
    await screen.findByRole('list', { name: 'Brands' });
    const historyLength = window.history.length;
    const sort = screen.getByRole('combobox', { name: 'Sort by' });

    await user.selectOptions(sort, 'Most reviews');
    await user.selectOptions(sort, 'Fewest reviews');

    expect(window.location.search).toBe('?ordering=review_count');
    expect(window.history.length).toBe(historyLength + 1);
    expect(fetchMock).toHaveBeenLastCalledWith(
      '/api/brands/?ordering=review_count&page_size=12',
      expect.anything(),
    );
  });

  it('follows Back and Forward: the controls and results match the URL', async () => {
    window.history.replaceState(null, '', '/brand/?industry=telecom');
    const fetchMock = stubFetch(
      async () => json(fixture.empty_page.body),
      async () => json(fixture.first_page.body),
    );
    renderBrandList();
    await screen.findByText(/No brands match/);

    // jsdom doesn't fire popstate from history.back(), so the test does.
    act(() => {
      window.history.replaceState(null, '', '/brand/');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });

    expect(screen.getByRole<HTMLInputElement>('checkbox', { name: 'Telecom' }).checked).toBe(false);
    await screen.findByRole('list', { name: 'Brands' });
    expect(fetchMock).toHaveBeenLastCalledWith('/api/brands/?page_size=12', expect.anything());
  });

  it('offers to clear filters when nothing matches, then moves focus to the results', async () => {
    window.history.replaceState(null, '', '/brand/?industry=telecom&industry=finance');
    stubFetch(
      async () => json(fixture.empty_page.body),
      async () => json(fixture.first_page.body),
    );
    const user = userEvent.setup();
    renderBrandList();
    const results = screen.getByRole('region', { name: 'Results' });
    await within(results).findByText('No brands match Finance or Telecom.');

    await user.click(within(results).getByRole('button', { name: 'Clear filters' }));

    expect(window.location.search).toBe('');
    expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Results' }));
  });

  it('shows an error with Retry when the server fails, and recovers on Retry', async () => {
    stubFetch(
      async () => json({ detail: 'Server error' }, 500),
      async () => json(fixture.first_page.body),
    );
    const user = userEvent.setup();
    renderBrandList();

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain("We couldn't load brands.");
    await user.click(within(alert).getByRole('button', { name: 'Retry' }));

    await screen.findByRole('list', { name: 'Brands' });
    expect(screen.queryByRole('alert')).toBeNull();
    expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Results' }));
  });

  it.each([
    ['a response that breaks the contract', async () => json({ results: 'nope' }), 'could not read'],
    ['a body that is not JSON', async () => new Response('<html>'), 'could not read'],
    ['a timeout', () => Promise.reject(new DOMException('', 'TimeoutError')), 'took too long'],
    ['a network failure', () => Promise.reject(new TypeError('Failed to fetch')), 'Check your connection'],
    ['a rejected request', async () => json(fixture.invalid_query.body, 400), 'not accepted'],
  ])('explains %s without showing raw error text', async (_case, response, message) => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    stubFetch(response);

    renderBrandList();

    expect((await screen.findByRole('alert')).textContent).toContain(message);
  });

  it('shows only the latest request\'s results when responses arrive out of order', async () => {
    const slow = deferred();
    const fast = deferred();
    stubFetch(slow.promise, fast.promise);
    const user = userEvent.setup();
    renderBrandList();

    await user.click(screen.getByRole('checkbox', { name: 'Telecom' }));
    fast.resolve(json(fixture.empty_page.body));
    await screen.findByText('No brands match Telecom.');
    await act(async () => {
      slow.resolve(json(fixture.first_page.body));
      await Promise.resolve();
    });

    expect(screen.getByText('No brands match Telecom.')).toBeDefined();
    expect(screen.queryByRole('list', { name: 'Brands' })).toBeNull();
  });

  it('announces loading and the result count after a change, but not on page load', async () => {
    const next = deferred();
    stubFetch(async () => json(fixture.first_page.body), next.promise);
    const user = userEvent.setup();
    renderBrandList();
    await screen.findByRole('list', { name: 'Brands' });
    const status = screen.getByRole('status');
    expect(status.textContent).toBe('');

    await user.click(screen.getByRole('checkbox', { name: 'Telecom' }));

    expect(status.textContent).toBe('Loading brands…');
    // The previous results stay on screen while the next ones load.
    expect(screen.getByRole('list', { name: 'Brands' })).toBeDefined();
    next.resolve(json(fixture.first_page.body));
    await screen.findByText('3 brands. Telecom. Sorted by highest rated. Page 1 of 1.');
  });

  it('corrects a hand-edited URL in place, keeping parameters it does not own', async () => {
    window.history.replaceState(
      null,
      '',
      '/brand/?industry=nope&industry=telecom&page=abc&ordering=-average_rating&utm_source=x',
    );
    const historyLength = window.history.length;
    stubFetch(async () => json(fixture.first_page.body));

    renderBrandList();
    await screen.findByRole('list', { name: 'Brands' });

    expect(window.location.search).toBe('?utm_source=x&industry=telecom');
    expect(window.history.length).toBe(historyLength);
  });

  it('pages with links: a new history entry, and focus moves to the results', async () => {
    const threePages = { ...fixture.first_page.body, count: 30 };
    const fetchMock = stubFetch(
      async () => json(threePages),
      async () => json(threePages),
    );
    const user = userEvent.setup();
    renderBrandList();
    const nav = await screen.findByRole('navigation', { name: 'Pagination' });
    const historyLength = window.history.length;
    expect(within(nav).getByRole('link', { name: 'Page 1' }).getAttribute('aria-current')).toBe('page');
    expect(within(nav).getByRole('link', { name: 'Page 2' }).getAttribute('href')).toBe('/brand/?page=2');

    within(nav).getByRole('link', { name: 'Next page' }).focus();
    await user.keyboard('[Enter]');

    expect(window.location.search).toBe('?page=2');
    expect(window.history.length).toBe(historyLength + 1);
    expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Results' }));
    expect(fetchMock).toHaveBeenLastCalledWith('/api/brands/?page=2&page_size=12', expect.anything());
  });

  it('shows the first, last and nearby pages when there are many', async () => {
    window.history.replaceState(null, '', '/brand/?page=10');
    stubFetch(async () => json({ ...fixture.first_page.body, count: 12 * 20 }));

    renderBrandList();

    const nav = await screen.findByRole('navigation', { name: 'Pagination' });
    const links = within(nav).getAllByRole('link').map((link) => link.getAttribute('aria-label'));
    expect(links).toEqual(['Previous page', 'Page 1', 'Page 9', 'Page 10', 'Page 11', 'Page 20', 'Next page']);
    expect(within(nav).getByRole('list').textContent).toBe('Previous1…91011…20Next');
  });

  it('shows no pagination when everything fits on one page', async () => {
    stubFetch(async () => json(fixture.first_page.body));

    renderBrandList();
    await screen.findByRole('list', { name: 'Brands' });

    expect(screen.queryByRole('navigation', { name: 'Pagination' })).toBeNull();
  });

  it('goes back to page 1 when the page no longer exists', async () => {
    window.history.replaceState(null, '', '/brand/?page=9');
    const historyLength = window.history.length;
    const fetchMock = stubFetch(
      async () => json(fixture.page_not_found.body, 404),
      async () => json(fixture.first_page.body),
    );

    renderBrandList();

    await screen.findByRole('list', { name: 'Brands' });
    expect(window.location.search).toBe('');
    expect(window.history.length).toBe(historyLength);
    expect(fetchMock).toHaveBeenLastCalledWith('/api/brands/?page_size=12', expect.anything());
  });

  it.each([
    ['results', async () => json({ ...fixture.first_page.body, count: 30 }), () => screen.findByRole('list', { name: 'Brands' })],
    ['no results', async () => json(fixture.empty_page.body), () => screen.findByText(/No brands match/)],
    ['an error', async () => json({}, 500), () => screen.findByRole('alert')],
    ['loading', () => new Promise<Response>(() => undefined), () => screen.findByRole('region', { name: 'Results' })],
  ])('has no axe violations with %s', async (_state, response, ready) => {
    window.history.replaceState(null, '', '/brand/?industry=telecom');
    stubFetch(response);

    const { container } = renderBrandList();
    await ready();

    expect(await axeViolations(container)).toEqual([]);
  });

  it('reaches every control by Tab in visual order, one stop per card', async () => {
    window.history.replaceState(null, '', '/brand/?industry=telecom');
    stubFetch(async () => json({ ...fixture.first_page.body, count: 30 }));
    const user = userEvent.setup();
    renderBrandList();
    await screen.findByRole('list', { name: 'Brands' });

    const stops: string[] = [];
    for (let i = 0; i < 11; i += 1) {
      await user.tab();
      const element = document.activeElement;
      const label = element instanceof HTMLInputElement || element instanceof HTMLSelectElement
        ? element.labels?.[0]?.textContent
        : undefined;
      stops.push(label ?? element?.getAttribute('aria-label') ?? element?.textContent ?? '');
    }

    expect(stops).toEqual([
      'Finance',
      'Insurance',
      'Telecom',
      'Clear filters',
      'Sort by',
      'New Brand',
      'PrimePath Bank',
      'Page 1',
      'Page 2',
      'Page 3',
      'Next page',
    ]);
  });
});
