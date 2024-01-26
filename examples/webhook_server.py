import argparse
from typing import Dict

import flask
import ngrok

from scrapfly import webhook
from scrapfly.webhook import ResourceType

#### Instructions
# 1. Install dependencies: `pip install ngrok flask scrapfly`
# 2. Export your authtoken from the ngrok dashboard https://dashboard.ngrok.com/get-started/your-authtoken  as NGROK_AUTHTOKEN in your terminal
# 3. Create a webhook on your dashboard https://scrapfly.home/dashboard/webhook/create
# 4. Retrieve your Webhook signing secret
# 5. Run this script e.g: python webhook_server.py --signing-secret=<signing-secret>

def webhook_callback(data:Dict, resource_type:ResourceType, request:flask.Request):
    if resource_type == ResourceType.SCRAPE.value:
        upstream_response = data['result']
        print(upstream_response)

        # Handle as you want
    else:
        # See ResourceType Enum for all possible values
        print(data)

        # Handle as you want


if __name__ == "__main__":
    listener = ngrok.werkzeug_develop()

    parser = argparse.ArgumentParser(description="Webhook server with signing secret")
    parser.add_argument("--signing-secret", required=True, help="Signing secret to verify webhook payload integrity")
    args = parser.parse_args()

    print("====== LISTENING ON ======")
    print(listener.url() + "/webhook")
    print("==========================")

    assert isinstance(args.signing_secret, str)
    app = webhook.create_server(signing_secrets=tuple([args.signing_secret]), callback=webhook_callback)
    app.run()
