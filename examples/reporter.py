from time import sleep
from typing import Optional

from scrapfly import ScrapeConfig, ScrapflyClient, ScrapeApiResponse, ScrapflyError
from scrapfly.reporter import PrintReporter, ChainReporter
# from scrapfly.reporter.sentry import SentryReporter if sentry-sdk installed

def my_reporter(error:Optional[Exception]=None, scrape_api_response:Optional[ScrapeApiResponse]=None):
    if scrape_api_response is not None and scrape_api_response.scrape_result['status_code'] >= 400:
        print('whhoops from my custom reporter')
        # schedule retry for later, store some logs / metrics, anything you want

    if error is not None:
        # All errors code are available here https://scrapfly.local/docs/scrape-api/errors#api_response
        if isinstance(error, ScrapflyError):
            # custom action regarding the error code
            if error.code in ['ERR::SCRAPE::OPERATION_TIMEOUT', 'ERR::SCRAPE::TOO_MANY_CONCURRENT_REQUEST']:
                sleep(30)
            elif error.code in ['ERR::THROTTLE::MAX_CONCURRENT_REQUEST_EXCEEDED', 'ERR::THROTTLE::MAX_REQUEST_RATE_EXCEEDED']:
                sleep(60)
        else:
            pass # handle non scrapfly error

scrapfly = ScrapflyClient(
    key='__API_KEY__',
    reporter=ChainReporter(my_reporter, PrintReporter())
)

response:ScrapeApiResponse = scrapfly.scrape(scrape_config=ScrapeConfig(url='https://httpbin.dev/status/404'))

print(response)
