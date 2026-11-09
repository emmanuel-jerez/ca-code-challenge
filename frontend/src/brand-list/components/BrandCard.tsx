import type { Brand } from '../schema';
import { Rating } from './Rating';

function reviewCount(count: number): string {
  return count === 1 ? '1 review' : `${String(count)} reviews`;
}

// The same c-card block as Django's catalog/_brand_card.html (ADR 0023). The
// title link is the card's only link; CSS stretches it over the whole card,
// so the card is one tab stop.
export function BrandCard({ brand }: { readonly brand: Brand }) {
  const review = brand.top_review;
  return (
    <article className="c-card">
      <p className="c-card__eyebrow">
        <span className="c-badge">{brand.industry.name}</span>
      </p>
      <h3 className="c-card__title">
        <a className="c-card__link" href={`/brand/${encodeURIComponent(brand.slug)}/`}>
          {brand.name}
        </a>
      </h3>
      <p className="c-card__meta">
        <Rating value={brand.average_rating} />
        <span className="c-card__count">{reviewCount(brand.review_count)}</span>
      </p>
      {brand.short_description !== '' && (
        <p className="c-card__excerpt">{brand.short_description}</p>
      )}
      {review && (
        // Text children only: React escapes them, so the snippet can't become markup.
        <figure className="c-card__quote">
          <blockquote className="c-card__snippet">{review.snippet}</blockquote>
          <figcaption className="c-card__attribution">
            {review.reviewer_name} on <cite className="c-card__cite">{review.title}</cite>
          </figcaption>
        </figure>
      )}
    </article>
  );
}
