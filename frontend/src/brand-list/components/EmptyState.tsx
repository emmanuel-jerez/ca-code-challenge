import type { Industry } from '../schema';

interface EmptyStateProps {
  /** The industries filtered by; empty when nothing is filtered. */
  readonly filteredBy: readonly Industry[];
  readonly onClear: () => void;
}

export function EmptyState({ filteredBy, onClear }: EmptyStateProps) {
  if (filteredBy.length === 0) return (
      <div className="c-brand-list__message">
        <p className="c-brand-list__message-text">No brands yet.</p>
      </div>
    );
  return (
    <div className="c-brand-list__message">
      <p className="c-brand-list__message-text">No brands match {filteredBy.map((industry) => industry.name).join(' or ')}.</p>
      <button type="button" className="c-brand-list__button" onClick={onClear}>
        Clear filters
      </button>
    </div>
  );
}
