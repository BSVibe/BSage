"""Domain exception hierarchy for BSage."""


class BSageError(Exception):
    """Base exception for all BSage domain errors."""


class SkillLoadError(BSageError):
    """Raised when a skill fails to load (missing yaml, invalid fields)."""


class SkillRunError(BSageError):
    """Raised when a skill fails during execution."""


class SkillRejectedError(BSageError):
    """Raised when SafeModeGuard rejects a dangerous skill."""


class CredentialNotFoundError(BSageError):
    """Raised when credentials for a service are not found."""


class VaultPathError(BSageError):
    """Raised when a path traversal attempt is detected."""


class SafeModeError(BSageError):
    """Raised when the safe mode system encounters a failure."""
