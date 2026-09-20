"""Expected failures with fixed, client-safe messages; no provider text is exposed."""

from typing import ClassVar


class ClaimAssistError(Exception):
    """Base for expected errors. Subclasses declare reviewed public messages."""

    code: ClassVar[str] = "APPLICATION_ERROR"
    message: ClassVar[str] = "The request could not be completed."
    status_code: ClassVar[int] = 400


class ValidationError(ClaimAssistError):
    code = "VALIDATION_ERROR"
    message = "The request is invalid."
    status_code = 422


class AuthenticationError(ClaimAssistError):
    code = "AUTHENTICATION_ERROR"
    message = "Authentication is required."
    status_code = 401


class AuthorizationError(ClaimAssistError):
    code = "AUTHORIZATION_ERROR"
    message = "You do not have permission to perform this action."
    status_code = 403


class ResourceNotFoundError(ClaimAssistError):
    code = "RESOURCE_NOT_FOUND"
    message = "The requested resource was not found."
    status_code = 404


class ConflictError(ClaimAssistError):
    code = "CONFLICT"
    message = "The request conflicts with the current resource state."
    status_code = 409


class DependencyError(ClaimAssistError):
    code = "DEPENDENCY_UNAVAILABLE"
    message = "The service is temporarily unavailable."
    status_code = 503
