import datetime

from scrapfly import ScrapflyClient, ScraperAPI
from pprint import pprint

# You can check the full documentation of the API at https://scrapfly.io/docs/monitoring#api
# NOTICE: Those API Endpoint are only available from Enterprise plans
scrapfly = ScrapflyClient(key='__API_KEY__')

# Retrieve global stats
account_stats = scrapfly.get_monitoring_metrics(
    aggregation=[ScraperAPI.MONITORING_ACCOUNT_AGGREGATION],
    # aggregation=[ScraperAPI.MONITORING_ACCOUNT_AGGREGATION, ScraperAPI.MONITORING_PROJECT_AGGREGATION, ScraperAPI.MONITORING_TARGET_AGGREGATION],
    period=ScraperAPI.MONITORING_PERIOD_LAST_24H,
)

print("==== Account Metrics ====")
pprint(account_stats['account_metrics'])

print("==== Projects Metrics ====")
pprint(account_stats['projects_metrics'])

print("==== Targets Metrics ====")
pprint(account_stats['targets_metrics'])

print("==== Target Metrics on httpbin.dev ====")
target_stats = scrapfly.get_monitoring_target_metrics(domain="httpbin.dev", start=datetime.datetime.now() - datetime.timedelta(days=1), end=datetime.datetime.now())
pprint(target_stats)
