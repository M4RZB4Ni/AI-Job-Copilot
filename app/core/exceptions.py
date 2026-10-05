class AppError(Exception):
    """Base class for all application-specific exceptions."""
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        
class JobAnalysisError(AppError):
    """Raised when analyzing a job posting fails."""
    pass


class ConfigurationError(AppError):
    """Raised when required application settings are missing or invalid."""


class UsageValidationError(AppError):
    """Raised when usage metadata or token prices are invalid."""

    def __init__(self, message: str):
        super().__init__(message, status_code=400)


class UsageLogError(AppError):
    """Raised when PostgreSQL usage storage is unavailable or fails."""

    def __init__(self, message: str):
        super().__init__(message, status_code=503)
