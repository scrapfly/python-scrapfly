import pytest

from scrapfly import CrawlerConfig


@pytest.mark.parametrize('include_webhook', [False, True])
def test_legacy_positional_arguments_keep_their_meaning(include_webhook):
    # The positional signature published before search/refresh were added.
    args = [
        'https://example.test/', None, None,  # URL sources
        None, None, None,  # limits
        None, None,  # path filters
        False, False, None, None, None,  # crawl scope
        None, None, None, None, None,  # request configuration
        False, None, False,  # crawl strategy
        False, None, False,  # cache
        None, None,  # extraction
        True, 'public_residential_pool',  # asp, proxy_pool
    ]
    expected = {
        'url': 'https://example.test/',
        'asp': True,
        'proxy_pool': 'public_residential_pool',
    }
    if include_webhook:
        args.extend(['us', 'crawl-notifications', ['crawler_finished'], 1234])
        expected.update(country='us', webhook_name='crawl-notifications',
                        webhook_events=['crawler_finished'], max_api_credit=1234)

    assert CrawlerConfig(*args).to_api_params() == expected
