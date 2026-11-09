import type { Brand } from '../schema';
import { BrandCard } from './BrandCard';

interface BrandGridProps {
  readonly brands: readonly Brand[];
  /** Results of the previous query, shown dimmed while the next ones load. */
  readonly stale?: boolean;
}

export function BrandGrid({ brands, stale = false }: BrandGridProps) {
  return (
    <ul
      className={stale ? 'l-grid c-brand-list__grid c-brand-list__grid--stale' : 'l-grid c-brand-list__grid'}
      aria-label="Brands"
    >
      {brands.map((brand) => (
        <li key={brand.slug} className="c-brand-list__item">
          <BrandCard brand={brand} />
        </li>
      ))}
    </ul>
  );
}

const SKELETON_CARDS = 3;

// Placeholder cards at the real cards' size, so nothing jumps when data
// arrives. Hidden from assistive tech: the status region says what's happening.
export function SkeletonGrid() {
  return (
    <ul className="l-grid c-brand-list__grid" aria-hidden="true">
      {Array.from({ length: SKELETON_CARDS }, (_, i) => (
        <li key={i} className="c-brand-list__item">
          <div className="c-card c-card--skeleton" />
        </li>
      ))}
    </ul>
  );
}
