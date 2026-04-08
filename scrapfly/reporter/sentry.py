"""
Sentry integration for the Scrapfly Python SDK.

Provides a ``SentryReporter`` callable that captures scrape errors and tags
them with Scrapfly metadata (project, env, log URL, upstream status, error
code) for easier debugging in the Sentry UI.

This module **lazy-imports** ``sentry_sdk`` so that simply having the
``scrapfly`` package installed does not force users to also install
``sentry-sdk``. The import error is raised at instantiation time with a
clear message instead of at module-load time.

Example:

    >>> import sentry_sdk
    >>> sentry_sdk.init(dsn="https://...@sentry.io/...")
    >>>
    >>> from scrapfly import ScrapflyClient
    >>> from scrapfly.reporter import SentryReporter, ChainReporter, PrintReporter
    >>>
    >>> client = ScrapflyClient(
    ...     key="YOUR_API_KEY",
    ...     reporter=ChainReporter(SentryReporter(), PrintReporter()),
    ... )
"""

from typing import Optional


class SentryReporter:
    """
    A reporter callable that forwards Scrapfly errors to Sentry with
    contextual tags and extras.

    Raises:
        ImportError: If ``sentry-sdk`` is not installed when the reporter
            is instantiated. Install with ``pip install sentry-sdk``.
    """

    def __init__(self):
        try:
            import sentry_sdk  # noqa: F401  # validate the dependency is present
        except ImportError as e:
            raise ImportError(
                "SentryReporter requires the 'sentry-sdk' package. "
                "Install it with: pip install sentry-sdk"
            ) from e

    def __call__(
        self,
        error: Optional[Exception] = None,
        scrape_api_response: Optional['ScrapeApiResponse'] = None,  # noqa: F821
    ):
        # Late import — already validated in __init__, safe to import here.
        from sentry_sdk import capture_exception, push_scope

        with push_scope() as scope:
            if scrape_api_response is not None:
                scope.set_tag('scrapfly_project', scrape_api_response.config['project'])
                scope.set_tag('scrapfly_env', scrape_api_response.config['env'])
                scope.set_extra('scrape_config', scrape_api_response.config)

                if scrape_api_response.scrape_result:
                    scope.set_extra('log_url', scrape_api_response.scrape_result['log_url'])
                    scope.set_extra('upstream_url', scrape_api_response.scrape_result['url'])
                    scope.set_tag(
                        'scrapfly_upstream_status_code',
                        scrape_api_response.scrape_result['status_code'],
                    )

                if scrape_api_response.error is not None:
                    scope.set_tag('scrapfly_error_code', scrape_api_response.error['code'])

            if error is not None:
                capture_exception(error)
