"""Pins the VNC client password to the form the server builds at allocation.

The Go API stores "<project_salt>-<vnc_password>" and native VNC clients must
send that exact string, so the separator and the 8-char salt width are a wire
contract, not an implementation detail. The expected salt below is hardcoded
rather than recomputed so a change to the derivation fails the test instead of
moving with it.
"""
import pytest

from scrapfly import BrowserConfig, ScrapflyClient

API_KEY = 'scp-test-0000000000000000000000000000000000'
SALT = '701018da'


class TestVncClientPassword:
    def test_matches_server_salting(self):
        config = BrowserConfig(enable_vnc=True, vnc_password='hunter2')

        assert config.vnc_client_password(API_KEY) == f'{SALT}-hunter2'

    def test_client_helper_uses_its_own_key(self):
        config = BrowserConfig(enable_vnc=True, vnc_password='hunter2')

        assert ScrapflyClient(key=API_KEY).cloud_browser_vnc_password(config) == f'{SALT}-hunter2'

    @pytest.mark.parametrize(
        'config',
        [
            BrowserConfig(enable_vnc=True),
            BrowserConfig(enable_vnc=True, vnc_password=''),
            BrowserConfig(vnc_password='hunter2'),
        ],
        ids=['password unset', 'password empty', 'vnc disabled'],
    )
    def test_raises_when_server_would_not_salt(self, config):
        with pytest.raises(ValueError):
            config.vnc_client_password(API_KEY)
