import type { BrandsError } from '../api';
import { assertNever } from '../assertNever';

// What the user can do about it, never raw error or schema text.
function detail(error: BrandsError): string {
  switch (error.kind) {
    case 'network':
      return 'Check your connection and try again.';
    case 'timeout':
      return 'The server took too long to respond. Try again in a moment.';
    case 'http':
      return error.status >= 500
        ? 'Something went wrong on our side. Try again in a moment.'
        : 'The request was not accepted. Reload the page and try again.';
    case 'contract':
      return 'The server sent something we could not read. Try again in a moment.';
    default:
      return assertNever(error);
  }
}

interface ErrorStateProps {
  readonly error: BrandsError;
  readonly onRetry: () => void;
}

// role="alert": an error after a user action is announced at once (WCAG 4.1.3).
export function ErrorState({ error, onRetry }: ErrorStateProps) {
  return (
    <div className="c-brand-list__message c-brand-list__message--error" role="alert">
      <p className="c-brand-list__message-text">
        <strong>We couldn&apos;t load brands.</strong> {detail(error)}
      </p>
      <button type="button" className="c-brand-list__button" onClick={onRetry}>
        Retry
      </button>
    </div>
  );
}
