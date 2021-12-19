from typing import Optional

from sentry_sdk import set_tag, capture_exception, push_scope

from scrapfly import ScrapeApiResponse


class SentryReporter:

    def __call__(self, error:Optional[Exception]=None, scrape_api_response:Optional[ScrapeApiResponse]=None):
        with push_scope() as scope:
            scope.set_tag('scrapfly_project', scrape_api_response.config['project'])
            scope.set_tag('scrapfly_env', scrape_api_response.config['env'])

            if scrape_api_response:
                scope.set_extra('scrape_config', scrape_api_response.config)

                if scrape_api_response.scrape_result:
                    scope.set_extra('log_url', scrape_api_response.scrape_result['log_url'])
                    scope.set_extra('upstream_url', scrape_api_response.scrape_result['url'])
                    scope.set_tag('scrapfly_upstream_status_code', scrape_api_response.scrape_result['status_code'])

                if scrape_api_response.error is not None:
                    scope.set_tag('scrapfly_error_code', scrape_api_response.error['code'])

            if error is not None:
                capture_exception(error)
