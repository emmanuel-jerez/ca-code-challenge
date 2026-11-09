import { useId } from 'react';

import type { Industry } from '../schema';
import {
  ORDERINGS,
  ORDERING_LABELS,
  type ListingQuery,
  type Ordering,
  isOrdering,
} from '../urlQuery';

interface BrandFiltersProps {
  readonly industries: readonly Industry[];
  readonly query: ListingQuery;
  readonly onIndustriesChange: (industries: readonly string[]) => void;
  readonly onOrderingChange: (ordering: Ordering) => void;
  readonly onClear: () => void;
}

// Native controls only: the browser supplies keyboard support and semantics.
// Each change applies at once; it updates content, not context (WCAG 3.2.2),
// so there is no Apply button and focus stays where it is.
export function BrandFilters({
  industries,
  query,
  onIndustriesChange,
  onOrderingChange,
  onClear,
}: BrandFiltersProps) {
  const sortId = useId();
  const selected = new Set(query.industries);

  const toggle = (slug: string, checked: boolean) => {
    const next = new Set(selected);
    if (checked) next.add(slug);
    else next.delete(slug);
    onIndustriesChange([...next]);
  };

  return (
    <search className="c-brand-list__filters">
      {/* A form for semantics only; Enter must not reload the page. */}
      <form
        className="c-brand-list__form"
        onSubmit={(event) => {
          event.preventDefault();
        }}
      >
        <fieldset className="c-brand-list__industries">
          <legend className="c-brand-list__legend">Industry</legend>
          <div className="c-brand-list__options">
            {industries.map((industry) => (
              <label key={industry.slug} className="c-brand-list__option">
                <input
                  type="checkbox"
                  className="c-brand-list__checkbox"
                  name="industry"
                  value={industry.slug}
                  checked={selected.has(industry.slug)}
                  onChange={(event) => {
                    toggle(industry.slug, event.currentTarget.checked);
                  }}
                />
                {industry.name}
              </label>
            ))}
            {selected.size > 0 && (
              <button type="button" className="c-brand-list__button" onClick={onClear}>
                Clear filters
              </button>
            )}
          </div>
        </fieldset>
        <div className="c-brand-list__sort">
          <label className="c-brand-list__label" htmlFor={sortId}>
            Sort by
          </label>
          <select
            id={sortId}
            className="c-brand-list__select"
            name="ordering"
            value={query.ordering}
            onChange={(event) => {
              const { value } = event.currentTarget;
              if (isOrdering(value)) onOrderingChange(value);
            }}
          >
            {ORDERINGS.map((ordering) => (
              <option key={ordering} value={ordering}>
                {ORDERING_LABELS[ordering]}
              </option>
            ))}
          </select>
        </div>
      </form>
    </search>
  );
}
