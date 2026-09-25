"""Pins the `linked_service` discriminator the vault link endpoints put on the wire.

The server keys its provider registry on this exact string and refuses anything
else, so the value is a wire contract: LinkedService only changes the type
callers hold, never what is sent.
"""
import json

import pytest
from requests import Request, Response

from scrapfly import LinkedService, ScrapflyClient


class TestVaultLinkedServiceDiscriminator:

    pytestmark = pytest.mark.unit

    @staticmethod
    def _client_with(handler):
        client = ScrapflyClient(key='scp-live-0000000000000000000000000000000000000000')
        # _http_handler is a cached_property; seed the cache to stub transport.
        client.__dict__['_http_handler'] = handler
        return client

    @staticmethod
    def _json_response(payload):
        response = Response()
        response.status_code = 200
        response._content = json.dumps(payload).encode('utf-8')
        response.headers['Content-Type'] = 'application/json'
        response.url = 'https://browser.scrapfly.io/vault/v1/service'
        response.request = Request(method='POST', url=response.url).prepare()
        return response

    def _capture(self):
        captured = {}

        def handler(**kwargs):
            captured.update(kwargs)
            return self._json_response({'vault': {}, 'message': 'ok'})

        return captured, self._client_with(handler)

    @pytest.mark.parametrize(
        'linked_service',
        [LinkedService.ONE_PASSWORD, '1password', None],
        ids=['enum member', 'string value', 'omitted'],
    )
    def test_link_sends_the_provider_string(self, linked_service):
        captured, client = self._capture()
        kwargs = {} if linked_service is None else {'linked_service': linked_service}

        client.cloud_browser_vault_service_link(
            vault_id='v1',
            vault_key='dmF1bHRrZXk=',
            token='ops_token',
            linked_service_data={'vault_name': 'Engineering'},
            **kwargs,
        )

        assert captured['json']['linked_service'] == '1password'

    def test_link_forwards_an_unknown_provider_verbatim(self):
        # The registry is server-side; a provider it learns first must be
        # reachable without an SDK release.
        captured, client = self._capture()

        client.cloud_browser_vault_service_link(
            vault_id='v1',
            vault_key='dmF1bHRrZXk=',
            token='ops_token',
            linked_service_data={'vault_name': 'Engineering'},
            linked_service='bitwarden',
        )

        assert captured['json']['linked_service'] == 'bitwarden'

    def test_update_omits_the_discriminator(self):
        # PATCH re-decodes against the vault's stored discriminator, so a body
        # field could only ever lie about switching provider.
        captured, client = self._capture()

        client.cloud_browser_vault_service_update(
            vault_id='v1',
            linked_service_data={'vault_name': 'Engineering'},
        )

        assert 'linked_service' not in captured['json']

    def test_test_omits_the_discriminator_unless_asked(self):
        captured, client = self._capture()

        client.cloud_browser_vault_service_test(vault_id='v1', vault_key='dmF1bHRrZXk=', token='ops_token')
        assert 'linked_service' not in captured['json']

        client.cloud_browser_vault_service_test(
            vault_id='v1',
            vault_key='dmF1bHRrZXk=',
            token='ops_token',
            linked_service=LinkedService.ONE_PASSWORD,
        )
        assert captured['json']['linked_service'] == '1password'
