// @vitest-environment node
// The architecture rules from ADR 0023, checked on the compiled CSS. They
// stand in for stylelint, whose SCSS setup pulls a hijacked dependency chain.
import { fileURLToPath } from 'node:url';

import postcss, { AtRule, type Node, type Root } from 'postcss';
import { Version, compile, compileString } from 'sass';
import { describe, expect, it } from 'vitest';

const SCSS_DIR = fileURLToPath(new URL('.', import.meta.url));

// The same policy as the `scss` script's --fatal-deprecation=1.107.0.
const OPTIONS = { fatalDeprecations: [Version.parse('1.107.0')], loadPaths: [SCSS_DIR] };

const LAYER_ORDER = 'reset, tokens, base, layout, components, utilities';

// Prefixed BEM: l- layout, c- component, u- utility; then an optional
// __element and --modifier, each in lowercase kebab case.
const CLASS_NAME = /^[lcu]-[a-z0-9]+(-[a-z0-9]+)*(__[a-z0-9]+(-[a-z0-9]+)*)?(--[a-z0-9]+(-[a-z0-9]+)*)?$/;

const RAW_COLOR = /#[0-9a-f]{3,8}\b|\b(rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(/i;

// In properties that can take a color, the only words allowed besides var()
// are these, so a named color (red, teal …) can't slip in.
const COLOR_PROPERTY = /color|background|border|outline|shadow|fill|stroke/;
const NON_COLOR_WORDS = new Set([
  'none', 'solid', 'dashed', 'dotted', 'inset', 'transparent', 'currentcolor', 'inherit',
  'initial', 'unset',
]);

/** The words left in a value once var() calls and numbers are removed. */
function bareWords(value: string): string[] {
  return value
    .replace(/var\([^)]*\)/g, '')
    .split(/[\s,/]+/)
    .filter((word) => /^[a-z-]+$/i.test(word) && !word.startsWith('--'))
    .map((word) => word.toLowerCase());
}

function hasRawColor(prop: string, value: string): boolean {
  if (RAW_COLOR.test(value)) return true;
  return (
    COLOR_PROPERTY.test(prop) &&
    !prop.endsWith('radius') &&
    bareWords(value).some((word) => !NON_COLOR_WORDS.has(word))
  );
}

function compileTheme(): Root {
  return postcss.parse(compile(`${SCSS_DIR}theme.scss`, OPTIONS).css);
}

/** The names of the @layer blocks around `node`, outermost first. */
function layersAround(node: Node): string[] {
  const layers: string[] = [];
  for (let parent: Node | undefined = node.parent; parent; parent = parent.parent) {
    if (parent instanceof AtRule && parent.name === 'layer') layers.unshift(parent.params);
  }
  return layers;
}

/** Class, attribute and pseudo-class count, ignoring :where() (which adds none). */
function specificity(selector: string): { ids: number; classes: number } {
  const counted = selector.replace(/:where\([^)]*\)/g, '').replace(/::[a-z-]+/g, '');
  return {
    ids: (counted.match(/#[\w-]+/g) ?? []).length,
    classes: (counted.match(/\.[\w-]+|\[[^\]]*\]|:[a-z-]+/g) ?? []).length,
  };
}

describe('compiled theme.css', () => {
  const css = compileTheme();

  it('declares the cascade layer order once, before any rule', () => {
    const first = css.first;

    expect(first?.type === 'atrule' && first.name === 'layer' && first.params).toBe(LAYER_ORDER);
    const statements = css.nodes.filter(
      (node) => node.type === 'atrule' && node.name === 'layer' && node.nodes === undefined,
    );
    expect(statements).toHaveLength(1);
  });

  it('puts every rule inside a cascade layer', () => {
    const unlayered: string[] = [];
    css.walkRules((rule) => {
      if (layersAround(rule).length === 0) unlayered.push(rule.selector);
    });

    expect(unlayered).toEqual([]);
  });

  it('names every class with the layer-prefixed BEM pattern', () => {
    const names = new Set<string>();
    css.walkRules((rule) => {
      for (const [, name] of rule.selector.matchAll(/\.([\w-]+)/g)) if (name) names.add(name);
    });

    expect([...names].filter((name) => !CLASS_NAME.test(name))).toEqual([]);
    expect(names.size).toBeGreaterThan(0);
  });

  it('keeps raw colors in the tokens layer', () => {
    const raw: string[] = [];
    css.walkDecls((decl) => {
      if (!layersAround(decl).includes('tokens') && hasRawColor(decl.prop, decl.value)) {
        raw.push(`${decl.prop}: ${decl.value}`);
      }
    });

    expect(raw).toEqual([]);
  });

  it('never uses !important', () => {
    const important: string[] = [];
    css.walkDecls((decl) => {
      if (decl.important) important.push(`${decl.prop}: ${decl.value}`);
    });

    expect(important).toEqual([]);
  });

  it('keeps selectors flat: no ids, at most two classes or states', () => {
    const heavy: string[] = [];
    css.walkRules((rule) => {
      for (const selector of rule.selectors) {
        const { ids, classes } = specificity(selector);
        if (ids > 0 || classes > 2) heavy.push(selector);
      }
    });

    expect(heavy).toEqual([]);
  });
});

describe('token functions', () => {
  it('fail the build on an unknown token instead of emitting a dead var()', () => {
    const source = '@use "tools" as t;\n.c-x { color: t.color("txet-muted"); }';

    expect(() => compileString(source, OPTIONS)).toThrow(/Unknown color token/);
  });
});
