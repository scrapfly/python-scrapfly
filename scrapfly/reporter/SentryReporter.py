"""
Backwards-compat shim. The canonical path is ``scrapfly.reporter.sentry``
(snake_case, idiomatic Python). This file re-exports ``SentryReporter`` so
existing imports of the form

    from scrapfly.reporter.SentryReporter import SentryReporter

continue to work after the rename.
"""

from .sentry import SentryReporter

__all__ = ('SentryReporter',)
