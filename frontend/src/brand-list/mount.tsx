import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { BrandList } from './BrandList';
import { IndustryList } from './schema';

const INDUSTRIES_ELEMENT_ID = 'brand-list-industries';

/** Reads the industries Django passes with json_script. Untrusted like any input. */
function readIndustries(): IndustryList {
  const element = document.getElementById(INDUSTRIES_ELEMENT_ID);
  let data: unknown;
  try {
    data = JSON.parse(element?.textContent ?? '');
  } catch {
    throw new Error(`#${INDUSTRIES_ELEMENT_ID} doesn't hold JSON industries.`);
  }
  const parsed = IndustryList.safeParse(data);
  if (!parsed.success) throw new Error(`#${INDUSTRIES_ELEMENT_ID} holds invalid industries.`);
  return parsed.data;
}

/**
 * Renders <BrandList /> into `root`, configured by the page: `data-api-url`
 * on the root and the industries data block. Fails loudly on a misconfigured
 * page rather than rendering a filter with no options. Returns an unmount
 * function.
 */
export function mountBrandList(root: HTMLElement): () => void {
  const endpoint = root.dataset.apiUrl;
  if (!endpoint) throw new Error('The brand list root needs a data-api-url attribute.');
  const industries = readIndustries();
  const reactRoot = createRoot(root);
  reactRoot.render(
    <StrictMode>
      <BrandList apiUrl={endpoint} industries={industries} />
    </StrictMode>,
  );
  return () => {
    reactRoot.unmount();
  };
}
