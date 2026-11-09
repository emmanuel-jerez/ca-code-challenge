// @vitest-environment node
import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

import { compileTheme } from './compileTheme';
import { type Comparison, compareStylesheets } from './equivalence';
import { DEVIATIONS, type Deviation, WP_TO_BEM } from './wp-mapping';

describe('compareStylesheets', () => {
  it('matches a declaration through renamed custom properties and a new class name', () => {
    const reference = ':root { --color-card: #ffffff; } .card { background: var(--color-card); }';
    const ours =
      '@layer tokens { :root { --color-surface: #fff; } }' +
      '@layer components { .c-card { background: var(--color-surface); } }';

    const { comparisons } = compareStylesheets(reference, ours, { '.card': ['.c-card'] });

    expect(comparisons).toEqual([
      {
        selector: '.card',
        context: '',
        property: 'background',
        reference: '#ffffff',
        ours: '#ffffff',
        status: 'same',
      },
    ]);
  });

  it('compares box shorthands side by side with logical properties', () => {
    const reference = '.container { margin: 8px auto; padding: 0 24px; }';
    const ours = '.l-container { margin-inline: auto; padding: 0; padding-inline: 24px; }';

    const { comparisons } = compareStylesheets(reference, ours, { '.container': ['.l-container'] });

    expect(comparisons.map(({ property, status }) => `${property} ${status}`)).toEqual([
      'margin-top missing',
      'margin-right same',
      'margin-bottom missing',
      'margin-left same',
      'padding-top same',
      'padding-right same',
      'padding-bottom same',
      'padding-left same',
    ]);
  });

  it('matches range-syntax media queries and reports motion that is now opt-in', () => {
    const reference =
      '.card { transition: box-shadow 0.15s; }' +
      '@media (max-width: 640px) { .hero { padding-top: 40px; } }';
    const ours =
      '@layer components {' +
      '  @media (prefers-reduced-motion: no-preference) { .c-card { transition: box-shadow 150ms; } }' +
      '  @media (width <= 640px) { .c-hero { padding-block: 40px; } }' +
      '}';

    const { comparisons } = compareStylesheets(reference, ours, {
      '.card': ['.c-card'],
      '.hero': ['.c-hero'],
    });

    expect(comparisons.map(({ context, property, status }) => [context, property, status])).toEqual([
      ['', 'transition', 'motion-guarded'],
      ['(width<=640px)', 'padding-top', 'same'],
    ]);
  });

  it('lists WordPress selectors the mapping does not mention', () => {
    const reference = '.card { color: #111111; } .meta { color: #6b7280; }';
    const ours = '.c-card { color: #111111; }';

    const { unmapped } = compareStylesheets(reference, ours, { '.card': ['.c-card'] });

    expect(unmapped).toEqual(['.meta']);
  });

  it('compares a border shorthand with a later border-color', () => {
    const reference = '.page-numbers { border: 1px solid #e5e7eb; }';
    const ours = '.c-pagination__link { border: 1px solid transparent; border-color: #e5e7eb; }';

    const { comparisons } = compareStylesheets(reference, ours, {
      '.page-numbers': ['.c-pagination__link'],
    });

    expect(comparisons.map(({ property, status }) => `${property} ${status}`)).toEqual([
      'border-width same',
      'border-style same',
      'border-color same',
    ]);
  });

  it('reports a zero margin or padding side we leave at its initial value', () => {
    const reference = '.hero { padding: 64px 0 56px; }';
    const ours = '.c-hero { padding-block: 64px 56px; }';

    const { comparisons } = compareStylesheets(reference, ours, { '.hero': ['.c-hero'] });

    expect(comparisons.map(({ property, status }) => `${property} ${status}`)).toEqual([
      'padding-top same',
      'padding-right initial',
      'padding-bottom same',
      'padding-left initial',
    ]);
  });

  it('compares a physical border side with its logical equivalent', () => {
    const reference = '.site-header { border-bottom: 1px solid #e5e7eb; }';
    const ours = '.c-site-header { border-block-end: 1px solid #e5e7eb; }';

    const { comparisons } = compareStylesheets(reference, ours, {
      '.site-header': ['.c-site-header'],
    });

    expect(comparisons.map(({ property, status }) => `${property} ${status}`)).toEqual([
      'border-bottom-width same',
      'border-bottom-style same',
      'border-bottom-color same',
    ]);
  });

  it('matches attribute selectors whether or not the value is quoted', () => {
    const reference = '.current { color: #ffffff; }';
    const ours = '.c-pagination__link[aria-current=page] { color: #fff; }';

    const { comparisons } = compareStylesheets(reference, ours, {
      '.current': ['.c-pagination__link[aria-current="page"]'],
    });

    expect(comparisons.map(({ status }) => status)).toEqual(['same']);
  });
});

function covers(deviation: Deviation, comparison: Comparison): boolean {
  const { property, context } = deviation;
  return (
    deviation.selector === comparison.selector &&
    (property === undefined ||
      comparison.property === property ||
      comparison.property.startsWith(`${property}-`)) &&
    (context === undefined || comparison.context === context)
  );
}

describe('theme.scss against reference/theme.css', () => {
  const reference = readFileSync(new URL('../../reference/theme.css', import.meta.url), 'utf8');
  const { comparisons, unmapped } = compareStylesheets(reference, compileTheme(), WP_TO_BEM);
  const differences = comparisons.filter(
    ({ status }) => status === 'different' || status === 'missing',
  );

  it('maps every WordPress selector', () => {
    expect(unmapped).toEqual([]);
  });

  it('reproduces every WordPress declaration, except the listed deviations', () => {
    const unexplained = differences.filter(
      (comparison) => !DEVIATIONS.some((deviation) => covers(deviation, comparison)),
    );

    expect(unexplained).toEqual([]);
  });

  it('lists no deviation that no longer applies', () => {
    const stale = DEVIATIONS.filter(
      (deviation) => !differences.some((comparison) => covers(deviation, comparison)),
    );

    expect(stale).toEqual([]);
  });
});

