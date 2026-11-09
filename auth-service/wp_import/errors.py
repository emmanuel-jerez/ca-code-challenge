"""Why a user import stopped. Every error aborts the run, and nothing is written."""


class WpImportError(Exception):
    """Base class: the import can't continue."""


class InvalidValue(WpImportError):
    """A WordPress user row doesn't fit the model. Fix it in WordPress, then re-run."""

    def __init__(self, wp_id: int, problem: str) -> None:
        self.wp_id = wp_id
        super().__init__(f"user {wp_id}: {problem}")
