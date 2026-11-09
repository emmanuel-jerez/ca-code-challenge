// The address bar's query string as a React store. No router: the component
// only owns a query string on a page Django routes.
import { useSyncExternalStore } from 'react';

const listeners = new Set<() => void>();

// Outside the component, so React doesn't re-subscribe on every render.
function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  window.addEventListener('popstate', listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener('popstate', listener);
  };
}

// A string, so React's Object.is check sees no change until it really changes.
function getSnapshot(): string {
  return window.location.search;
}

export function useLocationSearch(): string {
  return useSyncExternalStore(subscribe, getSnapshot);
}

/** Tags a history entry with what created it, so repeated sort changes can share one. */
export type EntrySource = 'ordering' | 'other';

interface EntryState {
  readonly brandListSource: EntrySource;
}

function isEntryState(value: unknown): value is EntryState {
  return typeof value === 'object' && value !== null && 'brandListSource' in value;
}

export function currentEntrySource(): EntrySource | null {
  const state: unknown = window.history.state;
  return isEntryState(state) ? state.brandListSource : null;
}

/**
 * Changes only the query string of the current page. `push` adds a history
 * entry (Back undoes it); `replace` corrects the current one. Only the query
 * string changes, so the URL can never point at another origin.
 */
export function navigate(search: string, mode: 'push' | 'replace', source: EntrySource): void {
  const url = `${window.location.pathname}${search}${window.location.hash}`;
  const state: EntryState = { brandListSource: source };
  if (mode === 'push') window.history.pushState(state, '', url);
  else window.history.replaceState(state, '', url);
  // pushState and replaceState don't fire popstate.
  for (const listener of listeners) listener();
}
