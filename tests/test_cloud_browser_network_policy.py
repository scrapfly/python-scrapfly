import json
from urllib.parse import parse_qs, urlsplit

import pytest

from scrapfly import BrowserConfig, NetworkPolicy, ScrapflyClient


@pytest.mark.parametrize(('policy', 'expected'), [
    (NetworkPolicy.block('httpbin.dev'), {'block': ['httpbin.dev']}),
    (NetworkPolicy.allow('web-scraping.dev', '192.0.2.7'), {'allow': ['web-scraping.dev', '192.0.2.7']}),
    (NetworkPolicy(allow=['web-scraping.dev'], block=['ads.web-scraping.dev']),
     {'allow': ['web-scraping.dev'], 'block': ['ads.web-scraping.dev']}),
])
def test_network_policy_reaches_the_websocket_query(policy, expected):
    config = BrowserConfig(network_policy=policy)
    restored = BrowserConfig.from_dict(config.to_dict())
    url = ScrapflyClient(key='test').cloud_browser(restored)
    (value,) = parse_qs(urlsplit(url).query)['network_policy']
    assert json.loads(value) == expected


@pytest.mark.parametrize('options', [{}, {'network_policy': {}}, {'network_policy': {'allow': [], 'block': []}}])
def test_config_without_network_rules_keeps_its_url(options):
    config = BrowserConfig.from_dict(options)
    assert 'network_policy' not in config.to_dict()
    assert 'network_policy' not in parse_qs(urlsplit(config.websocket_url('test')).query)
