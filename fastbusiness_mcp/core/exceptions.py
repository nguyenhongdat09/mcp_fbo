"""Custom exceptions for FastBusiness MCP Server."""


class FastBusinessMCPError(Exception):
    """Base exception for FastBusiness MCP errors."""

    pass


class ValidationError(FastBusinessMCPError):
    """Raised when validation fails."""

    pass


class ParserError(FastBusinessMCPError):
    """Raised when parsing fails."""

    pass


class DatabaseError(FastBusinessMCPError):
    """Raised when database operations fail."""

    pass


class GeneratorError(FastBusinessMCPError):
    """Raised when code generation fails."""

    pass


class FixerError(FastBusinessMCPError):
    """Raised when automatic fixing fails."""

    pass
