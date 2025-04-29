from typing import Callable, Optional, Tuple
from enum import Enum

from scrapfly import ResponseBodyHandler
import logging as logger


class ResourceType(Enum):
    SCRAPE = 'scrape'
    PING = 'ping'


def create_server(signing_secrets:Tuple[str], callback:Callable, app:Optional['flask.Flask']=None) -> 'flask.Flask':
    try:
        import flask
    except ImportError:
        raise ImportError("flask is not installed, please install it with `pip install \"scrapfly-sdk[webhook-server]\"`")

    from flask import request, make_response

    if app is None:
        app = flask.Flask("Scrapfly Webhook Server")

    @app.route("/webhook", methods=["POST"])
    def webhook():
        headers = request.headers
        resource_type = headers.get('X-Scrapfly-Webhook-Resource-Type')

        if resource_type == ResourceType.SCRAPE.value or resource_type == ResourceType.PING.value:
            body_handler = ResponseBodyHandler(signing_secrets=signing_secrets)
            data = body_handler.read(
                content=request.data,
                content_encoding=headers.get('Content-Encoding'),
                content_type=headers.get('Content-Type'),
                signature=headers.get('X-Scrapfly-Webhook-Signature', None) # Can be none when ping during the webhook creation flow via "ping"
            )

            try:
                callback(data, resource_type, request)
                return make_response("", 200)
            except Exception as e:
                logger.error(e)
                return make_response("", 500)

        return make_response("Do not support resource type %s" % resource_type, 400)

    return app