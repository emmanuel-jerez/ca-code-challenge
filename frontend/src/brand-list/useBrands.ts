import { useEffect, useState } from 'react';

import { type BrandsError, type BrandsResult, fetchBrands } from './api';
import type { BrandPage } from './schema';

export type BrandsState =
  // `previous` keeps the last page on screen while the next one loads.
  | { readonly status: 'loading'; readonly previous: BrandPage | null }
  | { readonly status: 'success'; readonly page: BrandPage }
  | { readonly status: 'error'; readonly error: BrandsError };

interface Settled {
  /** The request this result answers. */
  readonly key: string;
  readonly result: BrandsResult;
  readonly lastPage: BrandPage | null;
}

/**
 * Loads `url` and reloads whenever it or `reloadKey` changes. The request a
 * change replaces is aborted, so a slow old response can't overwrite a newer
 * one. Loading is derived (the settled result answers another request) rather
 * than stored, so it can't get out of step with the URL.
 */
export function useBrands(url: string, reloadKey: number): BrandsState {
  const key = `${String(reloadKey)} ${url}`;
  const [settled, setSettled] = useState<Settled | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void fetchBrands(url, controller.signal).then((result) => {
      if (controller.signal.aborted) return;
      setSettled((prev) => ({
        key,
        result,
        lastPage: result.ok ? result.page : (prev?.lastPage ?? null),
      }));
    });
    return () => {
      controller.abort();
    };
  }, [url, key]);

  if (settled?.key !== key) return { status: 'loading', previous: settled?.lastPage ?? null };
  const { result } = settled;
  return result.ok
    ? { status: 'success', page: result.page }
    : { status: 'error', error: result.error };
}
