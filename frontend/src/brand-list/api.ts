// The one network call. Every outcome becomes a typed result, so callers
// switch on it instead of catching.
import { z } from 'zod';

import { BrandPage } from './schema';

export type BrandsError =
  | { readonly kind: 'network' }
  | { readonly kind: 'timeout' }
  | { readonly kind: 'http'; readonly status: number }
  // The response didn't match the schema. Details go to the console only.
  | { readonly kind: 'contract' };

export type BrandsResult =
  | { readonly ok: true; readonly page: BrandPage }
  | { readonly ok: false; readonly error: BrandsError };

// Long enough for a slow mobile connection, short enough that a hung request
// turns into an error with Retry instead of an endless loading state.
const TIMEOUT_MS = 10_000;

/**
 * Fetches one page of brands. Never rejects: failures come back as error
 * results. After `signal` aborts the result means nothing, so callers check
 * `signal.aborted` first.
 */
export async function fetchBrands(url: string, signal: AbortSignal): Promise<BrandsResult> {
  let response: Response;
  let body: unknown;
  try {
    response = await fetch(url, {
      headers: { Accept: 'application/json' },
      signal: AbortSignal.any([signal, AbortSignal.timeout(TIMEOUT_MS)]),
    });
    if (!response.ok) return { ok: false, error: { kind: 'http', status: response.status } };
    body = await response.json();
  } catch (error) {
    // AbortSignal.timeout() rejects with a TimeoutError DOMException.
    if (error instanceof DOMException && error.name === 'TimeoutError') {
      return { ok: false, error: { kind: 'timeout' } };
    }
    // A failed connection, a cancelled request, or a body that isn't JSON.
    if (error instanceof SyntaxError) return { ok: false, error: { kind: 'contract' } };
    return { ok: false, error: { kind: 'network' } };
  }

  const parsed = BrandPage.safeParse(body);
  if (!parsed.success) {
    console.error(`Brand list response didn't match the schema:\n${z.prettifyError(parsed.error)}`);
    return { ok: false, error: { kind: 'contract' } };
  }
  return { ok: true, page: parsed.data };
}
