// Compares our compiled theme with the WordPress theme's CSS, declaration by
// declaration, after resolving custom properties on both sides. Class names
// differ, so a mapping says which of our selectors replace each WordPress one.
import postcss, { AtRule, type Node, type Root } from 'postcss';

/**
 * WordPress selector → our selectors that together replace it. Where two set
 * the same property, the later one in this list wins. An empty list means the
 * rule was dropped on purpose.
 */
export type SelectorMapping = Readonly<Record<string, readonly string[]>>;

// motion-guarded: the same value, but only under prefers-reduced-motion:
// no-preference, where WordPress applied it to everyone.
// initial: WordPress set a margin or padding side to 0 and we don't set it,
// so it stays at its initial value, 0. That holds on the divs, sections and
// headers these blocks sit on, which have no browser margin or padding.
export type Status = 'same' | 'motion-guarded' | 'initial' | 'different' | 'missing';

const MOTION_SAFE = '(prefers-reduced-motion:no-preference)';

export interface Comparison {
  selector: string;
  /** The media condition around the rule, normalized; '' outside any. */
  context: string;
  property: string;
  reference: string;
  ours: string | undefined;
  status: Status;
}

export interface Report {
  comparisons: Comparison[];
  /** WordPress selectors with no mapping entry, so never compared. */
  unmapped: string[];
}

type Declarations = Map<string, string>;

/** Every custom property in the sheet, wherever it's declared. */
function customProperties(root: Root): Map<string, string> {
  const properties = new Map<string, string>();
  root.walkDecls(/^--/, (decl) => {
    properties.set(decl.prop, decl.value);
  });
  return properties;
}

/** Replaces var() calls with their values, recursively; a fallback is used when the name is unknown. */
function resolve(value: string, properties: Map<string, string>, depth = 0): string {
  if (depth > 10) throw new Error(`Custom property cycle in "${value}"`);
  const resolved = value.replace(
    /var\(\s*(--[\w-]+)\s*(?:,\s*([^()]*))?\)/g,
    (_, name: string, fallback: string | undefined) => properties.get(name) ?? fallback ?? '',
  );
  return resolved.includes('var(') ? resolve(resolved, properties, depth + 1) : resolved;
}

/** Spelling differences that don't change the value: case, spaces, short hex. */
function normalize(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .replace(/\s*([,/()])\s*/g, '$1')
    .replace(/#([0-9a-f])([0-9a-f])([0-9a-f])\b/g, '#$1$1$2$2$3$3')
    .replace(/\b(\d*\.?\d+)ms\b/g, (_, ms: string) => `${Number(ms) / 1000}s`);
}

/** `(max-width: 640px)` and `(width <= 640px)` both become `(width<=640px)`. */
function normalizeMedia(params: string): string {
  return params
    .toLowerCase()
    .replace(/\s+/g, '')
    .replace(/\(max-width:([^)]+)\)/g, '(width<=$1)')
    .replace(/\(min-width:([^)]+)\)/g, '(width>=$1)');
}

const SIDES = ['top', 'right', 'bottom', 'left'] as const;

// Logical sides in a left-to-right, horizontal writing mode, which the site uses.
const LOGICAL_SIDES: Readonly<Record<string, readonly (typeof SIDES)[number][]>> = {
  inline: ['left', 'right'],
  block: ['top', 'bottom'],
  'inline-start': ['left'],
  'inline-end': ['right'],
  'block-start': ['top'],
  'block-end': ['bottom'],
};

const BORDER_STYLES = new Set(['none', 'hidden', 'dotted', 'dashed', 'solid', 'double']);

/** `border: 1px solid X` → width, style and color, matching a later border-color. */
function expandBorder(prefix: string, value: string): [string, string][] {
  const words = value.split(' ');
  const style = words.find((word) => BORDER_STYLES.has(word));
  const width = words.find((word) => /^(\d|\.\d|thin|medium|thick)/.test(word));
  const color = words.filter((word) => word !== style && word !== width).join(' ');
  return [
    [`${prefix}-width`, width ?? 'medium'],
    [`${prefix}-style`, style ?? 'none'],
    [`${prefix}-color`, color || 'currentcolor'],
  ];
}

/**
 * Splits `border`, and margin and padding (shorthand or logical) into the
 * four physical sides, so `margin: 0 auto` and `margin-inline: auto` can be
 * compared.
 */
function expand(property: string, value: string): [string, string][] {
  if (property === 'border') return expandBorder('border', value);
  const border = /^border-(top|right|bottom|left|inline|block|inline-start|inline-end|block-start|block-end)$/.exec(property);
  if (border) {
    const [, part = ''] = border;
    const sides = LOGICAL_SIDES[part] ?? [part];
    return sides.flatMap((side) => expandBorder(`border-${side}`, value));
  }
  const match = /^(margin|padding)(?:-(.+))?$/.exec(property);
  if (!match) return [[property, value]];
  const [, box = '', part] = match;
  const parts = value.split(' ');
  if (part === undefined) {
    // 1 to 4 values: top, right, bottom, left, each defaulting to its opposite.
    const [top = '', right = top, bottom = top, left = right] = parts;
    return [top, right, bottom, left].map((side, i) => [`${box}-${SIDES[i] ?? ''}`, side]);
  }
  const sides = LOGICAL_SIDES[part];
  if (!sides) return [[property, value]];
  // A logical pair takes one or two values: start, then end.
  return sides.map((side, i) => [`${box}-${side}`, parts[i] ?? parts[0] ?? '']);
}

/** Collapses spaces and drops quotes around identifier attribute values. */
function normalizeSelector(selector: string): string {
  return selector
    .trim()
    .replace(/\s+/g, ' ')
    .replace(/=\s*(["'])([\w-]+)\1\s*\]/g, '=$2]');
}

function contextOf(node: Node): string {
  const conditions: string[] = [];
  for (let parent = node.parent; parent; parent = parent.parent) {
    if (parent instanceof AtRule && parent.name === 'media') conditions.unshift(normalizeMedia(parent.params));
  }
  return conditions.join(' and ');
}

/** Declarations per context and selector, resolved and normalized. Later ones win. */
function index(root: Root): Map<string, Declarations> {
  const properties = customProperties(root);
  const rules = new Map<string, Declarations>();
  root.walkRules((rule) => {
    const context = contextOf(rule);
    for (const selector of rule.selectors) {
      const key = `${context}|${normalizeSelector(selector)}`;
      const declarations = rules.get(key) ?? new Map<string, string>();
      rule.each((child) => {
        if (child.type === 'decl' && !child.prop.startsWith('--')) {
          const value = normalize(resolve(child.value, properties));
          for (const [property, side] of expand(child.prop, value)) {
            declarations.set(property, side);
          }
        }
      });
      rules.set(key, declarations);
    }
  });
  return rules;
}

export function compareStylesheets(
  reference: string,
  ours: string,
  mapping: SelectorMapping,
): Report {
  const theirs = index(postcss.parse(reference));
  const mine = index(postcss.parse(ours));
  const comparisons: Comparison[] = [];
  const unmapped = new Set<string>();

  for (const [key, declarations] of theirs) {
    // Media conditions never contain '|'; an attribute selector might.
    const split = key.indexOf('|');
    const context = key.slice(0, split);
    const selector = key.slice(split + 1);
    if (selector === ':root') continue;
    const replacements = mapping[selector];
    if (replacements === undefined) {
      unmapped.add(selector);
      continue;
    }
    for (const [property, value] of declarations) {
      const lookup = (where: string): string | undefined => {
        let found: string | undefined;
        for (const replacement of replacements) {
          found = mine.get(`${where}|${normalizeSelector(replacement)}`)?.get(property) ?? found;
        }
        return found;
      };
      const found = lookup(context);
      const guarded = context === '' ? lookup(MOTION_SAFE) : undefined;
      let status: Status;
      if (found !== undefined) status = found === value ? 'same' : 'different';
      else if (guarded !== undefined) status = guarded === value ? 'motion-guarded' : 'different';
      else if (value === '0' && /^(margin|padding)-/.test(property)) status = 'initial';
      else status = 'missing';
      comparisons.push({
        selector,
        context,
        property,
        reference: value,
        ours: found ?? guarded,
        status,
      });
    }
  }
  return { comparisons, unmapped: [...unmapped] };
}
