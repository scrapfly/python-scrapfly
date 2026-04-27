"""
Public schedule client for the Scrapfly API.

This module wraps the /scrape/schedules, /screenshot/schedules,
/crawl/schedules and cross-kind /schedules endpoints. It is intentionally
a thin wrapper: the server returns fully-formed Schedule objects (dicts)
and we surface them as-is so callers always see the live server shape.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import quote


@dataclass
class ScheduleEnd:
    """Bounds a recurring schedule by either a date or a fire count."""
    type: str  # "date" | "count"
    date: Optional[str] = None
    count: Optional[int] = None


@dataclass
class ScheduleRecurrence:
    """When a schedule fires next.

    Cron mode wins when ``cron`` is set; otherwise ``interval`` + ``unit``
    drive the cadence. All times are interpreted in UTC server-side.
    """
    cron: Optional[str] = None
    interval: Optional[int] = None
    unit: Optional[str] = None  # "minute" | "hour" | "day" | "week" | "month"
    days: Optional[List[str]] = None
    ends: Optional[ScheduleEnd] = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        if self.cron:
            out["cron"] = self.cron
        if self.interval is not None:
            out["interval"] = self.interval
        if self.unit:
            out["unit"] = self.unit
        if self.days:
            out["days"] = self.days
        if self.ends:
            ends: Dict[str, Any] = {"type": self.ends.type}
            if self.ends.date:
                ends["date"] = self.ends.date
            if self.ends.count is not None:
                ends["count"] = self.ends.count
            out["ends"] = ends
        return out


@dataclass
class CreateScheduleRequest:
    """Public-facing request envelope for creating a schedule.

    The kind-specific configuration (scrape_config / screenshot_config /
    crawler_config) is supplied as a separate argument by the matching
    ``create_*_schedule`` method.
    """
    webhook_name: str = ""
    recurrence: Optional[ScheduleRecurrence] = None
    scheduled_date: Optional[str] = None
    allow_concurrency: bool = False
    retry_on_failure: bool = False
    max_retries: Optional[int] = None
    notes: Optional[str] = None


@dataclass
class UpdateScheduleRequest:
    """Patch payload. Only fields with a non-None value are forwarded."""
    recurrence: Optional[ScheduleRecurrence] = None
    scheduled_date: Optional[str] = None
    allow_concurrency: Optional[bool] = None
    retry_on_failure: Optional[bool] = None
    max_retries: Optional[int] = None
    notes: Optional[str] = None
    scrape_config: Optional[Dict[str, Any]] = None
    screenshot_config: Optional[Dict[str, Any]] = None
    crawler_config: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        if self.recurrence is not None:
            out["recurrence"] = self.recurrence.to_dict()
        if self.scheduled_date is not None:
            out["scheduled_date"] = self.scheduled_date
        if self.allow_concurrency is not None:
            out["allow_concurrency"] = self.allow_concurrency
        if self.retry_on_failure is not None:
            out["retry_on_failure"] = self.retry_on_failure
        if self.max_retries is not None:
            out["max_retries"] = self.max_retries
        if self.notes is not None:
            out["notes"] = self.notes
        if self.scrape_config is not None:
            out["scrape_config"] = self.scrape_config
        if self.screenshot_config is not None:
            out["screenshot_config"] = self.screenshot_config
        if self.crawler_config is not None:
            out["crawler_config"] = self.crawler_config
        return out


# Server returns Schedule as a plain JSON object; expose as an aliased dict
# for now. Callers that want field access can wrap with `.get(...)` or build
# their own typed model on top.
Schedule = Dict[str, Any]


@dataclass
class ListSchedulesOptions:
    """Filter options for list_schedules / list_<kind>_schedules. Use either
    this dataclass or the equivalent keyword arguments interchangeably."""
    kind: Optional[str] = None  # "api.scrape" | "api.screenshot" | "api.crawler"
    status: Optional[str] = None  # "ACTIVE" | "PAUSED" | "CANCELLED"


class ScheduleClientMixin:
    """Mixed into ScrapflyClient — provides the public schedule surface.

    All methods funnel through ``_schedule_request``, which uses the same
    ``self._http_handler`` and ``self.host`` / ``self.key`` as the rest of the
    client so retries, verify, headers and timeouts behave identically.
    """

    # Attributes provided by the concrete ``ScrapflyClient`` subclass. Declared
    # here so type checkers can resolve them on the mixin without complaint.
    key: str
    host: str
    verify: bool
    ua: str
    _http_handler: Callable[..., Any]

    # ---- Create ---------------------------------------------------------

    def create_scrape_schedule(
        self,
        scrape_config: Dict[str, Any],
        request: CreateScheduleRequest,
    ) -> Schedule:
        """Create a Web Scraping API schedule. ``scrape_config`` is the same
        dict you would pass to :meth:`scrape` (e.g. ``{"url": "...", "render_js": True}``)."""
        return self._create_schedule("/scrape/schedules", "scrape_config", scrape_config, request)

    def create_screenshot_schedule(
        self,
        screenshot_config: Dict[str, Any],
        request: CreateScheduleRequest,
    ) -> Schedule:
        """Create a Screenshot API schedule."""
        return self._create_schedule(
            "/screenshot/schedules", "screenshot_config", screenshot_config, request
        )

    def create_crawler_schedule(
        self,
        crawler_config: Dict[str, Any],
        request: CreateScheduleRequest,
    ) -> Schedule:
        """Create a Crawler API schedule."""
        return self._create_schedule(
            "/crawl/schedules", "crawler_config", crawler_config, request
        )

    # ---- Read -----------------------------------------------------------

    def get_schedule(self, schedule_id: str) -> Schedule:
        """Return a schedule by id (works across all kinds)."""
        return self._schedule_request("GET", "/schedules/" + quote(schedule_id, safe=""))

    def list_schedules(
        self,
        *,
        kind: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Schedule]:
        """List every schedule on the account, optionally filtered by kind or status."""
        params: Dict[str, str] = {}
        if kind:
            params["kind"] = kind
        if status:
            params["status"] = status
        return self._schedule_request("GET", "/schedules", query=params)

    def list_scrape_schedules(self, *, status: Optional[str] = None) -> List[Schedule]:
        params = {"status": status} if status else None
        return self._schedule_request("GET", "/scrape/schedules", query=params)

    def list_screenshot_schedules(self, *, status: Optional[str] = None) -> List[Schedule]:
        params = {"status": status} if status else None
        return self._schedule_request("GET", "/screenshot/schedules", query=params)

    def list_crawler_schedules(self, *, status: Optional[str] = None) -> List[Schedule]:
        params = {"status": status} if status else None
        return self._schedule_request("GET", "/crawl/schedules", query=params)

    # ---- Mutate ---------------------------------------------------------

    def update_schedule(self, schedule_id: str, request: UpdateScheduleRequest) -> Schedule:
        """Patch an active schedule. Only fields set in ``request`` change."""
        return self._schedule_request(
            "PATCH", "/schedules/" + quote(schedule_id, safe=""), body=request.to_dict()
        )

    def cancel_schedule(self, schedule_id: str) -> None:
        """Cancel a schedule. Cancellation is terminal (returns no body)."""
        self._schedule_request("DELETE", "/schedules/" + quote(schedule_id, safe=""))

    def pause_schedule(self, schedule_id: str) -> Schedule:
        return self._schedule_request("POST", "/schedules/" + quote(schedule_id, safe="") + "/pause")

    def resume_schedule(self, schedule_id: str) -> Schedule:
        return self._schedule_request("POST", "/schedules/" + quote(schedule_id, safe="") + "/resume")

    def execute_schedule(self, schedule_id: str) -> Schedule:
        """Fire a schedule immediately, regardless of next_scheduled_date."""
        return self._schedule_request("POST", "/schedules/" + quote(schedule_id, safe="") + "/execute")

    # ---- Internals ------------------------------------------------------

    def _create_schedule(
        self,
        path: str,
        config_key: str,
        config: Dict[str, Any],
        request: CreateScheduleRequest,
    ) -> Schedule:
        body: Dict[str, Any] = {
            config_key: config,
            "webhook_name": request.webhook_name,
            "allow_concurrency": request.allow_concurrency,
            "retry_on_failure": request.retry_on_failure,
        }
        if request.recurrence is not None:
            body["recurrence"] = request.recurrence.to_dict()
        if request.scheduled_date is not None:
            body["scheduled_date"] = request.scheduled_date
        if request.max_retries is not None:
            body["max_retries"] = request.max_retries
        if request.notes is not None:
            body["notes"] = request.notes
        return self._schedule_request("POST", path, body=body)

    def _schedule_request(
        self,
        method: str,
        path: str,
        *,
        query: Optional[Dict[str, str]] = None,
        body: Optional[Dict[str, Any]] = None,
    ) -> Any:
        params: Dict[str, str] = {"key": self.key}
        if query:
            params.update(query)

        kwargs: Dict[str, Any] = {
            "method": method,
            "url": self.host + path,
            "params": params,
            "verify": self.verify,
            "headers": {
                "user-agent": self.ua,
                "accept": "application/json",
            },
        }
        if body is not None:
            kwargs["json"] = body
            kwargs["headers"]["content-type"] = "application/json"

        response = self._http_handler(**kwargs)

        if response.status_code == 204:
            return None
        if response.status_code >= 400:
            self._raise_schedule_error(response)

        if not response.content:
            return None
        return response.json()

    def _raise_schedule_error(self, response) -> None:
        try:
            envelope = response.json()
        except Exception:
            envelope = {}
        code = envelope.get("error", "ERR::SCHEDULER::BACKEND_ERROR")
        message = envelope.get("message", "")
        reason = envelope.get("reason", "")
        details = envelope.get("details")
        text = message
        if reason:
            text = f"{message} ({reason})" if message else reason
        if not text:
            text = response.text[:500] or f"HTTP {response.status_code}"

        raise ScheduleAPIError(
            message=text,
            code=code,
            http_status_code=response.status_code,
            details=details,
        )


class ScheduleAPIError(Exception):
    """Raised on any non-2xx response from a /schedules/* endpoint.

    The ``code`` attribute carries the public ``ERR::SCHEDULER::*`` identifier
    so callers can branch on it without parsing the message string.
    """

    def __init__(
        self,
        message: str,
        code: str,
        http_status_code: int,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.http_status_code = http_status_code
        self.details = details

    def __str__(self) -> str:  # noqa: D401
        return f"{self.code} ({self.http_status_code}): {self.args[0] if self.args else ''}"
