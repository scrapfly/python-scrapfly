from pprint import pprint
from typing import Optional
from scrapfly import ScrapeApiResponse

class PrintReporter:

    def __call__(self, error:Optional[Exception]=None, scrape_api_response:Optional[ScrapeApiResponse]=None):
        debug_data = {
            'scrape_config': None,
            'log_url': None,
            'scrape_error': None,
            'error': None
        }

        if scrape_api_response:
            debug_data['scrape_config'] = scrape_api_response.config

            if scrape_api_response.error is not None:
                debug_data['scrape_error'] = scrape_api_response.error

            if scrape_api_response.scrape_result:
                debug_data['log_url'] = scrape_api_response.scrape_result['log_url']

        if error is not None:
            debug_data['error'] = {
                'message': str(error),
                'type': error.__class__.__name__
            }

        pprint(debug_data)
