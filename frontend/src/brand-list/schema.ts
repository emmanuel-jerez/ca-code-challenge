// Shapes of the data crossing into the component: API responses and the
// industry list the page provides. Both are parsed, never cast (ADR 0010).
// z.object strips unknown keys, so the API can add fields without breaking
// the UI (ADR 0027's additive-only policy).
import { z } from 'zod';

// The API's page-size cap (ADR 0022). Bounds the work a hostile or broken
// response can cause, on top of Zod 4.6.6's fix for CVE-2023-54404.
const MAX_PAGE_SIZE = 50;

export const Industry = z.object({
  slug: z.string().min(1),
  name: z.string().min(1),
});
export type Industry = z.infer<typeof Industry>;

// No real deployment has anywhere near this many; the cap only bounds parsing.
export const IndustryList = z.array(Industry).max(200);
export type IndustryList = z.infer<typeof IndustryList>;

const TopReview = z.object({
  slug: z.string(),
  title: z.string(),
  rating: z.number().int().min(1).max(5),
  reviewer_name: z.string(),
  // Plain text (ADR 0027). Rendered as text, never as HTML.
  snippet: z.string(),
});

export const Brand = z.object({
  slug: z.string().min(1),
  name: z.string(),
  industry: Industry,
  // null: the brand has no published reviews yet (ADR 0019).
  average_rating: z.number().min(0).max(5).nullable(),
  review_count: z.number().int().nonnegative(),
  short_description: z.string(),
  top_review: TopReview.nullable(),
});
export type Brand = z.infer<typeof Brand>;

export const BrandPage = z.object({
  count: z.number().int().nonnegative(),
  next: z.string().nullable(),
  previous: z.string().nullable(),
  results: z.array(Brand).max(MAX_PAGE_SIZE),
});
export type BrandPage = z.infer<typeof BrandPage>;
