"""
errors.py — Custom exceptions for the Data Janitor & Orchestrator pipeline.
All errors inherit from PipelineError so you can catch everything with one except block.
"""


class PipelineError(Exception):
    """Base class for all pipeline errors."""
    pass


class FileIngestionError(PipelineError):
    """Raised when a file cannot be found, read, or is an unsupported type."""
    pass


class APIError(PipelineError):
    """Raised when the Gemini API call fails or returns an unexpected response."""
    pass


class InvalidOutputError(PipelineError):
    """Raised when an agent returns output that cannot be parsed (e.g. malformed JSON)."""
    pass


class AgentTimeoutError(PipelineError):
    """Raised when an agent takes too long to respond."""
    pass
