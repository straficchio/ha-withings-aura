"""Exceptions for the Withings Aura integration."""


class AuraError(Exception):
    """Base exception."""


class AuraConnectionError(AuraError):
    """The bridge could not be reached or the connection was lost."""


class AuraTimeoutError(AuraError):
    """The bridge did not answer in time."""
