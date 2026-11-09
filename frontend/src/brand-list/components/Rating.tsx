const STARS = 5;

// The API sends ratings with two decimals. Round to one, half up, as the
// server-rendered stars do; toFixed() would round 4.05 down, because 4.05 is
// stored as 4.04999… in binary.
function formatRating(value: number): string {
  const hundredths = Math.round(value * 100);
  return (Math.round(hundredths / 10) / 10).toFixed(1);
}

// Visible number plus hidden "out of 5"; the stars are decoration. Unlike the
// WordPress markup, no aria-label sits on a plain span (ARIA 1.2 forbids it).
export function Rating({ value }: { readonly value: number | null }) {
  if (value === null) return <span className="c-stars c-stars--unrated">Not rated yet</span>;
  // Full stars are the rating rounded down, as on the server-rendered cards.
  const full = Math.floor(value);
  return (
    <span className="c-stars">
      <span className="c-stars__icons" aria-hidden="true">
        {Array.from({ length: STARS }, (_, i) => (
          <span
            key={i}
            className={i < full ? 'c-stars__star' : 'c-stars__star c-stars__star--empty'}
          >
            {i < full ? '★' : '☆'}
          </span>
        ))}
      </span>
      <span className="c-stars__value">{formatRating(value)}</span>
      <span className="u-visually-hidden"> out of 5</span>
    </span>
  );
}
