import json
from enum import Enum
from typing import Optional, Dict
from urllib.parse import quote_plus
from base64 import urlsafe_b64encode
from .api_config import BaseApiConfig


class CompressionFormat(Enum):
    """
    Document compression format.

    Attributes:
        GZIP: gzip format.
        ZSTD: zstd format.
    """

    GZIP = "gzip"
    ZSTD = "zstd"
    DEFLATE = "deflate"


class ExtractionConfigError(Exception):
    pass


class ExtractionConfig(BaseApiConfig):
    body: str
    content_type: str
    url: Optional[str] = None
    charset: Optional[str] = None
    template: Optional[str] = None  # a saved template name
    epehemeral_template: Optional[Dict]  # epehemeraly declared json template
    extraction_prompt: Optional[str] = None
    extraction_model: Optional[str] = None
    is_document_compressed: Optional[bool] = None
    document_compression_format: Optional[CompressionFormat] = None
    webhook: Optional[str] = None
    raise_on_upstream_error: bool = True

    def __init__(
        self,
        body: str,
        content_type: str,
        url: Optional[str] = None,
        charset: Optional[str] = None,
        template: Optional[str] = None,  # a saved template name
        epehemeral_template: Optional[Dict] = None,  # epehemeraly declared json template
        extraction_prompt: Optional[str] = None,
        extraction_model: Optional[str] = None,
        is_document_compressed: Optional[bool] = None,
        document_compression_format: Optional[CompressionFormat] = None,
        webhook: Optional[str] = None,
        raise_on_upstream_error: bool = True
    ):

        self.key = None
        self.body = body
        self.content_type = content_type
        self.url = url
        self.charset = charset
        self.template = template
        self.epehemeral_template = epehemeral_template
        self.extraction_prompt = extraction_prompt
        self.extraction_model = extraction_model
        self.is_document_compressed = is_document_compressed
        self.document_compression_format = document_compression_format
        self.webhook = webhook
        self.raise_on_upstream_error = raise_on_upstream_error

        if self.document_compression_format is not None:
            if self.is_document_compressed is None:
                raise ExtractionConfigError(
                    'When declaring compression format, your must declare the is_document_compressed parameter to compress the document or skip it.'
                )
            if self.is_document_compressed is False:
                if self.document_compression_format == CompressionFormat.GZIP:
                    import gzip
                    self.body = gzip.compress(bytes(self.body, 'utf-8'))
                else:
                    raise ExtractionConfigError(
                        f'Auto compression for {self.document_compression_format.value} format is not available. You can manually compress to {self.document_compression_format.value} or choose the gzip format for auto compression.'
                    )                    

    def to_api_params(self, key: str) -> Dict:
        params = {
            'key': self.key or key,
            'content_type': self.content_type
        }

        if self.url:
            params['url'] = self.url

        if self.charset:
            params['charset'] = self.charset

        if self.template and self.epehemeral_template:
            raise ExtractionConfigError('You cannot pass both parameters template and epehemeral_template. You must choose')

        if self.template:
            params['extraction_template'] = self.template

        if self.epehemeral_template:
            self.epehemeral_template = json.dumps(self.epehemeral_template)
            params['extraction_template'] = 'ephemeral:' + urlsafe_b64encode(self.epehemeral_template.encode('utf-8')).decode('utf-8')

        if self.extraction_prompt:
            params['extraction_prompt'] = quote_plus(self.extraction_prompt)

        if self.extraction_model:
            params['extraction_model'] = self.extraction_model

        if self.webhook:
            params['webhook_name'] = self.webhook

        return params
