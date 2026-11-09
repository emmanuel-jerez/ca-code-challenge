import { act, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { mountBrandList } from './mount';

// The markup Django's template will provide: a root with the API URL, and the
// industries as a json_script data block.
function page(industriesJson: string): HTMLElement {
  document.body.innerHTML = `
    <div id="brand-list" data-api-url="/api/brands/"></div>
    <script type="application/json" id="brand-list-industries">${industriesJson}</script>`;
  const root = document.getElementById('brand-list');
  if (!root) throw new Error('No root');
  return root;
}

afterEach(() => {
  document.body.innerHTML = '';
});

describe('mountBrandList', () => {
  it('renders the component from the data the page provides', async () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(() => undefined)));
    const root = page('[{"slug": "telecom", "name": "Telecom"}]');

    const unmount = mountBrandList(root);

    expect(await screen.findByRole('checkbox', { name: 'Telecom' })).toBeDefined();
    act(unmount);
  });

  it.each([
    ['malformed JSON', '[{'],
    ['the wrong shape', '[{"slug": 1}]'],
  ])('refuses industry data with %s', (_case, industriesJson) => {
    const root = page(industriesJson);

    expect(() => mountBrandList(root)).toThrow(/industries/);
  });
});
