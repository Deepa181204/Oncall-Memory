"""Safe-to-return application errors for upstream provider failures."""


class ProviderUnavailable(RuntimeError):
    """A provider request failed; details stay in server logs, not API responses."""
