// Compiles theme.scss the way the `scss` script does, for the tests.
import { fileURLToPath } from 'node:url';

import { type Options, Version, compile } from 'sass';

export const SCSS_DIR = fileURLToPath(new URL('.', import.meta.url));

// The same policy as the `scss` script's --fatal-deprecation=1.107.0 (ADR 0023).
export const SASS_OPTIONS = {
  fatalDeprecations: [Version.parse('1.107.0')],
  loadPaths: [SCSS_DIR],
} satisfies Options<'sync'>;

export function compileTheme(): string {
  return compile(`${SCSS_DIR}theme.scss`, SASS_OPTIONS).css;
}
