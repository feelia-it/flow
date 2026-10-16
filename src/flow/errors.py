"""User-facing errors raised by Flow."""


class FlowError(Exception):
    """An error that can be reported directly to a Flow script author."""


class FlowSyntaxError(FlowError):
    """A script contains invalid Flow syntax."""


class FlowExecutionError(FlowError):
    """A valid Flow instruction could not be completed."""

