class AppError(Exception):
    """Base class for all application-specific exceptions."""
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        
class JobAnalysisError(AppError):
    """Raised when analyzing a job posting fails."""
    pass