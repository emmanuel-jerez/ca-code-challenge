"""Why an import stopped. Every error aborts the run, and nothing is written."""


class WpImportError(Exception):
    """Base class: the import can't continue."""


class ImportAlreadyRunning(WpImportError):
    def __init__(self) -> None:
        super().__init__("another import holds the lock; try again when it finishes")


class WpRowError(WpImportError):
    """A WordPress row doesn't fit the model. Fix the data in WordPress, then re-run."""

    def __init__(self, kind: str, wp_id: int, problem: str) -> None:
        self.kind = kind
        self.wp_id = wp_id
        super().__init__(f"{kind} {wp_id}: {problem}")


class UnknownMetaKey(WpRowError):
    """A postmeta key nobody triaged. WordPress's schema changed (ADR 0021)."""


class InvalidValue(WpRowError):
    """A value is missing, malformed or out of range."""


class UnsafeUrl(WpRowError):
    """website_url isn't http or https."""


class BadReference(WpRowError):
    """A row points at something that doesn't exist, or at the wrong number of things."""
