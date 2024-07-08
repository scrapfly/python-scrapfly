import base64
import json
from typing import Optional, Dict, Union
from urllib.parse import quote_plus
from base64 import urlsafe_b64encode


class ExtractionConfig:
    body: str
    content_type: str
    url: Optional[str] = None
    charset: Optional[str] = None
    extraction_template: Optional[Union[Dict, str]] = None
    extraction_prompt: Optional[str] = None
    extraction_model: Optional[str] = None
    webhook: Optional[str] = None
    raise_on_upstream_error: bool = True

    def __init__(
        self,
        body: str,
        content_type: str,
        url: Optional[str] = None,
        charset: Optional[str] = None,
        extraction_template: Optional[Union[Dict, str]] = None,
        extraction_prompt: Optional[str] = None,
        extraction_model: Optional[str] = None,
        webhook: Optional[str] = None,
        raise_on_upstream_error: bool = True
    ):
        
        self.key = None
        self.body = body
        self.content_type = content_type
        self.url = url
        self.charset = charset
        self.extraction_template = extraction_template
        self.extraction_prompt = extraction_prompt
        self.extraction_model = extraction_model
        self.webhook = webhook
        self.raise_on_upstream_error = raise_on_upstream_error

    def to_api_params(self, key:str) -> Dict:
        params = {
            'key': self.key if self.key is not None else key,
            'body': self.body,
            'content_type': self.content_type
        }

        if self.url:
            params['url'] = self.url

        if self.charset:
            params['charset'] = self.charset            

        if self.extraction_template:
            # passing a saved template name
            if isinstance(self.extraction_template, str):
                params['extraction_template'] = self.extraction_template

            # passing a phemeral template (declared on the fly on the API call)
            if isinstance(self.extraction_template, dict):
                self.extraction_template = json.dumps(self.extraction_template)
                params['extraction_template'] = 'ephemeral:' + urlsafe_b64encode(self.extraction_template.encode('utf-8')).decode('utf-8')

        if self.extraction_prompt:
            params['extraction_prompt'] = quote_plus(self.extraction_prompt)

        if self.extraction_model:
            params['extraction_model'] = self.extraction_model

        if self.webhook:
            params['webhook_name'] = self.webhook

        return params
    
    @staticmethod
    def from_exported_config(config:str) -> 'ExtractionConfig':
        try:
            from msgpack import loads as msgpack_loads
        except ImportError as e:
            print('You must install msgpack package - run: pip install "scrapfly-sdk[seepdup] or pip install msgpack')
            raise

        data = msgpack_loads(base64.b64decode(config))

        return ExtractionConfig(
            body=data['body'],
            content_type=data['content_type'],
            url=data['url'],
            charset=data['charset'],
            extraction_template=data['extraction_template'],
            extraction_prompt=data['extraction_prompt'],
            extraction_model=data['extraction_model'],
            webhook=data['webhook']
        )
