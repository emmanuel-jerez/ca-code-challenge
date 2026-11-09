// How reference/theme.css (the WordPress theme) maps onto our tree. The
// equivalence test compares every WordPress declaration through this table,
// so a rule can't be dropped or changed without a line here saying why.
import type { SelectorMapping } from './equivalence';

export const WP_TO_BEM: SelectorMapping = {
  // Base
  '*': ['*'],
  html: [],
  body: ['body'],
  a: ['a'],
  'a:hover': ['a:hover'],
  img: ['img'],

  // Layout
  '.container': ['.l-container'],
  '.grid': ['.l-grid'],
  '.section': ['.l-section'],
  '.section h2': ['.l-section__title'],
  '.section-header': ['.l-section__header'],
  '.section-header h2': ['.l-section__header .l-section__title'],
  '.section-header a': ['.l-section__more'],
  '.brand-body': ['.l-section', '.l-section--article'],
  '.reviews-section': ['.l-section', '.l-section--reviews'],
  '.reviews-section h2': ['.l-section__title', '.l-section--reviews .l-section__title'],

  // Site chrome
  '.site-header': ['.c-site-header'],
  '.site-header .container': ['.c-site-header__inner'],
  '.site-title': ['.c-site-header__title'],
  '.site-title a': ['.c-site-header__home-link'],
  '.site-nav': ['.c-site-nav'],
  '.site-nav a': ['.c-site-nav__link'],
  '.site-nav a:hover': ['.c-site-nav__link:hover'],
  '.site-footer': ['.c-site-footer'],
  '.site-footer a': ['.c-site-footer__link'],

  // Heroes
  '.hero': ['.c-hero'],
  '.hero h1': ['.c-hero__title'],
  '.hero p': ['.c-hero__lead'],
  '.brand-hero': ['.c-brand-hero'],
  '.brand-hero h1': ['.c-brand-hero__title'],
  '.brand-hero .brand-meta': ['.c-brand-facts'],
  '.brand-hero .brand-meta strong': ['.c-brand-facts__label'],
  '.review-hero': ['.c-review-hero'],
  '.review-hero .brand-link': ['.c-review-hero__back'],
  '.review-hero h1': ['.c-review-hero__title'],

  // Cards and their parts
  '.card': ['.c-card'],
  '.card:hover': ['.c-card:hover'],
  '.card h3': ['.c-card__title'],
  '.card h3 a': ['.c-card__link'],
  '.card .meta': ['.c-card__meta'],
  '.card .excerpt': ['.c-card__excerpt'],
  '.stars': ['.c-stars'],
  '.stars .star-full': ['.c-stars__star'],
  '.stars .star-empty': ['.c-stars__star--empty'],
  '.stars .rating-value': ['.c-stars__value'],
  '.badge': ['.c-badge'],

  // Reviews
  '.review-item': ['.c-review'],
  '.review-item .review-head': ['.c-review__head'],
  '.review-item h3': ['.c-review__title'],
  '.review-item h3 a': ['.c-review__link'],
  '.review-item .review-byline': ['.c-byline', '.c-review__byline'],
  '.review-item .review-body': ['.c-review__body'],

  // Long-form content
  '.brand-body .content': ['.c-panel', '.c-panel--article'],
  '.page-body': ['.c-panel'],
  '.page-body h1': ['.c-panel__title'],

  // Pagination
  '.pagination': ['.c-pagination__list'],
  '.pagination .page-numbers': ['.c-pagination__link'],
  '.pagination .page-numbers.current': ['.c-pagination__link[aria-current="page"]'],
};

export interface Deviation {
  /** The WordPress selector. */
  selector: string;
  /** A property, or a shorthand covering its sides; omitted for the whole rule. */
  property?: string;
  /** The normalized media condition; omitted for any. */
  context?: string;
  reason: string;
}

// Every WordPress declaration we don't reproduce, and why. Two kinds aren't
// listed, because the comparison reports them as their own statuses: motion
// that now waits for prefers-reduced-motion: no-preference (ADR 0030, item 6),
// and margin or padding sides set to 0 that we leave at their initial 0.
export const DEVIATIONS: readonly Deviation[] = [
  {
    selector: 'html',
    reason:
      'Set once, on body. The canvas takes body\'s background, html has no default margin or padding, and the forced 16px root size is dropped (ADR 0030, item 6).',
  },
  {
    selector: 'body',
    property: 'font-size',
    reason: 'No forced 16px: it overrides the reader\'s browser setting (ADR 0030, item 6).',
  },
  {
    selector: '.grid',
    property: 'grid-template-columns',
    reason:
      'minmax(min(100%, 17.5rem), 1fr): the same 280px column at the default font size, but it scales with the reader\'s font size and collapses to one column without a media query.',
  },
  {
    selector: '.grid',
    context: '(width<=640px)',
    reason: 'Not needed: the min(100%, …) column collapses to one on its own.',
  },
  {
    selector: '.page-body',
    property: 'margin',
    reason: 'A block doesn\'t place itself: the l-section around the panel gives the 48px.',
  },
];
