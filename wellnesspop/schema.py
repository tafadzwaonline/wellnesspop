"""Input schema: field specifications, default rules, and typed plan dataclasses.

The specifications in this module are the machine-readable input contract (D1).
Every editable field has a type, default rule, validation description, unit, and
provenance convention. ``docs/input-schema.md`` is generated from these specs.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import asdict, dataclass, fields, is_dataclass
from typing import Any
from zoneinfo import ZoneInfo

SCHEMA_VERSION = "1.0"
ENGINE_VERSION = "1.0.0"
DEFAULT_TZ = "America/Chicago"
CURRENCY = "USD"

EVENT_TYPES = ("single_class", "one_day_fair")
SETTINGS = ("indoor", "outdoor", "hybrid")
GOALS = ("net_revenue", "community_reach", "paid_program_pilot")
CHANNELS = ("instagram", "email", "flyers", "partner_newsletter", "eventbrite")
COST_CATEGORIES = (
    "equipment", "signage", "printing", "supplies", "sound", "tents", "furniture",
    "speaker", "venue", "insurance", "other",
)
PAY_BASES = ("flat", "hourly")
CERTIFICATIONS = ("cpr", "first_aid", "instructor_credential")
TIER_PRESETS = ("general", "early_bird", "sliding_scale", "free", "custom")
ALLOCATIONS = ("weighted", "free_quota")
BILLING_BASES = ("attended", "registered")
QUANTITY_BASES = ("fixed", "per_attendee")
PHASES = ("pre_event", "event_day", "post_event")
TASK_STATUSES = ("not_started", "in_progress", "complete", "blocked")
RISK_RESPONSES = ("avoid", "mitigate", "transfer", "accept")
RISK_STATUSES = ("open", "monitoring", "closed")
SOURCE_KINDS = ("user", "brief", "illustrative", "researched", "derived")

WEATHER_DEFAULTS = {"indoor": 0.0, "outdoor": 0.25, "hybrid": 0.20}
MIN_RUNS, MAX_RUNS = 10_000, 100_000
MAX_CAPACITY = 100_000
MAX_SEED = 2**63 - 1

LABELS = {
    "single_class": "Single class", "one_day_fair": "One-day fair",
    "indoor": "Indoor", "outdoor": "Outdoor", "hybrid": "Hybrid (indoor and outdoor)",
    "net_revenue": "Net revenue", "community_reach": "Community reach",
    "paid_program_pilot": "Paid program pilot",
    "instagram": "Instagram", "email": "Email", "flyers": "Flyers",
    "partner_newsletter": "Partner newsletter", "eventbrite": "Eventbrite listing",
    "pre_event": "Pre-event", "event_day": "Event day", "post_event": "Post-event",
    "not_started": "Not started", "in_progress": "In progress", "complete": "Complete",
    "blocked": "Blocked", "open": "Open", "monitoring": "Monitoring", "closed": "Closed",
    "cpr": "CPR", "first_aid": "First aid", "instructor_credential": "Instructor credential",
    "flat": "Flat fee", "hourly": "Hourly", "weighted": "Weighted share",
    "free_quota": "Fixed free places", "attended": "Pay on attendance",
    "registered": "Prepaid at registration", "fixed": "Fixed quantity",
    "per_attendee": "Per attendee",
}


def label(code: str | None) -> str:
    if code is None:
        return ""
    return LABELS.get(code, str(code).replace("_", " ").capitalize())


def today_in(tz: str = DEFAULT_TZ) -> dt.date:
    return dt.datetime.now(ZoneInfo(tz)).date()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


# --------------------------------------------------------------------------- specs


@dataclass(frozen=True)
class FieldSpec:
    """One editable field. ``kind`` drives coercion; the rest documents the contract."""

    path: str
    kind: str  # str, int, float, money, signed_money, rate, bool, date, time, enum, list_enum, tz
    unit: str
    default_rule: str
    validation: str
    provenance: str = "illustrative"
    choices: tuple = ()
    nullable: bool = False
    min: float | None = None
    max: float | None = None
    max_len: int | None = None
    help: str = ""


def _f(path, kind, unit, default_rule, validation, provenance="illustrative", **kw) -> FieldSpec:
    return FieldSpec(path, kind, unit, default_rule, validation, provenance, **kw)


SCALAR_SPECS: tuple[FieldSpec, ...] = (
    _f("schema_version", "str", "-", "1.0", "Must equal 1.0", "derived"),
    _f("currency", "enum", "-", "USD", "USD only in MVP", "derived", choices=("USD",)),
    _f("event.name", "str", "text", "My wellness event", "1-120 characters; no contact details",
       "illustrative", max_len=120),
    _f("event.event_type", "enum", "-", "single_class", "single_class or one_day_fair",
       "brief", choices=EVENT_TYPES),
    _f("event.setting", "enum", "-", "indoor", "indoor, outdoor or hybrid", "illustrative",
       choices=SETTINGS),
    _f("event.date", "date", "date", "Today in event timezone + 42 days",
       "Past dates require historical-plan acknowledgment"),
    _f("event.start_time", "time", "local time", "10:00", "Before end time"),
    _f("event.end_time", "time", "local time", "11:15", "After start time, same day"),
    _f("event.timezone", "tz", "IANA zone", DEFAULT_TZ, "Valid IANA timezone", "brief"),
    _f("event.session_count", "int", "sessions", "1", "Positive integer", min=1, max=100),
    _f("event.historical_ack", "bool", "-", "false",
       "Must be true to plan an event or marketing start in the past", "derived"),
    _f("rain.has_rain_plan", "bool", "-", "false", "Warn on outdoor/hybrid without a plan"),
    _f("rain.alternate_date", "date", "date", "null",
       "After event date; required (or venue) when rain plan enabled", nullable=True),
    _f("rain.alternate_venue", "str", "text", "null", "Descriptive venue name only, 0-120 chars",
       nullable=True, max_len=120),
    _f("goals.primary_goal", "enum", "-", "community_reach", "One of the listed goals",
       choices=GOALS),
    _f("goals.target_attendance", "int", "people on site", "40", "0 to venue capacity", min=0),
    _f("goals.target_net_income", "signed_money", "USD", "0",
       "May be negative for subsidized events"),
    _f("goals.spending_limit", "money", "USD", "null (not supplied)", "Nonnegative or empty",
       nullable=True, min=0),
    _f("venue.name", "str", "text", "Venue to confirm", "1-120 characters", max_len=120),
    _f("venue.capacity", "int", "people", "60", "1-100,000 (product limit, not a legal standard)",
       min=1, max=MAX_CAPACITY),
    _f("venue.permit_required", "bool", "-", "false", "Enables permit cost and tasks"),
    _f("venue.permit_cost", "money", "USD", "0", "Nonnegative; counted once in fixed ledger", min=0),
    _f("venue.permit_lead_days", "int", "days", "30 (illustrative, unverified)", "0-365",
       min=0, max=365),
    _f("venue.permit_retained_fraction", "rate", "fraction", "1",
       "Share of permit cost lost if cancelled, 0-1"),
    _f("venue.rental_total", "money", "USD", "0", "Total rental expense incl. any advance", min=0),
    _f("venue.rental_advance", "money", "USD", "0", "0 to rental total; cash-timing note only",
       min=0),
    _f("venue.rental_retained_fraction", "rate", "fraction", "1",
       "Share of rental lost if cancelled, 0-1"),
    _f("venue.security_deposit", "money", "USD", "0",
       "Refundable cash requirement; not an expense", min=0),
    _f("venue.security_deposit_forfeit_fraction", "rate", "fraction", "0",
       "Share of the deposit explicitly expected to be forfeited (becomes an expense)"),
    _f("venue.insurance_required", "bool", "-", "false", "Enables insurance cost and tasks"),
    _f("venue.insurance_cost", "money", "USD", "0", "Nonnegative; counted once", min=0),
    _f("venue.insurance_lead_days", "int", "days", "14 (illustrative planning rule)", "0-365",
       min=0, max=365),
    _f("venue.insurance_retained_fraction", "rate", "fraction", "1",
       "Share of insurance lost if cancelled, 0-1"),
    _f("attendance.low", "float", "registrations", "25", "0 <= low <= likely"),
    _f("attendance.likely", "float", "registrations", "40", "low <= likely <= high"),
    _f("attendance.high", "float", "registrations", "55", "likely <= high <= capacity"),
    _f("attendance.planned_peak", "float", "people", "null (use high registrations)",
       "Optional justified staffing peak, 0 to capacity", nullable=True, min=0),
    _f("no_show.low", "rate", "fraction", "0.10", "0 <= low <= mean"),
    _f("no_show.mean", "rate", "fraction", "0.20", "Strictly inside (low, high) unless all equal"),
    _f("no_show.high", "rate", "fraction", "0.30", "mean <= high <= 1"),
    _f("no_show.concentration", "float", "-", "6 (model-shape assumption)", "Positive", min=0),
    _f("processing.ticket_fee_rate", "rate", "fraction", "0",
       "User-entered processing fee; no payment integration"),
    _f("weather.cancellation_probability", "rate", "probability",
       "0 indoor; 0.25 outdoor; 0.20 hybrid (illustrative)", "Forced to 0 indoors"),
    _f("simulation.runs", "int", "trials", "10000", "10,000-100,000", "derived",
       min=MIN_RUNS, max=MAX_RUNS),
    _f("simulation.seed", "int", "-", "42", "Nonnegative 63-bit integer", "derived",
       min=0, max=MAX_SEED),
    _f("marketing.earliest_start", "date", "date", "Today in event timezone",
       "Past dates only in historical-plan mode"),
    _f("marketing.channels", "list_enum", "-", "email, flyers", "Subset of supported channels",
       choices=CHANNELS),
    _f("marketing.budget", "money", "USD", "0", "Fixed cost counted once; nothing is sent", min=0),
    _f("marketing.budget_retained_fraction", "rate", "fraction", "1",
       "Share of marketing spend lost if cancelled"),
)

RECORD_SPECS: dict[str, tuple[FieldSpec, ...]] = {
    "fixed_costs": (
        _f("id", "str", "-", "Generated stable ID", "Unique within plan", "derived"),
        _f("label", "str", "text", "New fixed cost", "1-120 characters", max_len=120),
        _f("category", "enum", "-", "other", "Listed category", choices=COST_CATEGORIES),
        _f("amount", "money", "USD", "0", "Nonnegative; equals triangular mean when uncertain",
           min=0),
        _f("retained_fraction", "rate", "fraction", "1", "Cost lost if cancelled, 0-1"),
        _f("uncertain", "bool", "-", "false", "If true, low/mode/high are sampled"),
        _f("low", "money", "USD", "= amount", "0 <= low <= mode", nullable=True, min=0),
        _f("mode", "money", "USD", "= amount", "low <= mode <= high", nullable=True, min=0),
        _f("high", "money", "USD", "= amount", "mode <= high", nullable=True, min=0),
    ),
    "variable_costs": (
        _f("id", "str", "-", "Generated stable ID", "Unique", "derived"),
        _f("label", "str", "text", "New variable cost", "1-120 characters", max_len=120),
        _f("low", "money", "USD per attendee", "2", "0 <= low <= mode", min=0),
        _f("mode", "money", "USD per attendee", "2", "low <= mode <= high", min=0),
        _f("high", "money", "USD per attendee", "2", "mode <= high", min=0),
        _f("retained_fraction", "rate", "fraction", "0", "Supplies cost kept if cancelled"),
    ),
    "ticket_tiers": (
        _f("id", "str", "-", "Generated stable ID", "Unique", "derived"),
        _f("label", "str", "text", "General", "1-120 characters", max_len=120),
        _f("preset", "enum", "-", "general", "Tier preset", choices=TIER_PRESETS),
        _f("price", "money", "USD", "15", "Nonnegative; 0 for free tiers", min=0),
        _f("allocation", "enum", "-", "weighted", "weighted or free_quota", choices=ALLOCATIONS),
        _f("weight", "rate", "share", "1", "Weighted tiers sum to 1"),
        _f("free_quota", "int", "registrations", "null", "Free-quota tiers only; price must be 0",
           nullable=True, min=0),
        _f("billing_basis", "enum", "-", "attended", "attended or registered (prepaid)",
           choices=BILLING_BASES),
        _f("no_show_low", "rate", "fraction", "null (inherit event)", "Override: all or none",
           nullable=True),
        _f("no_show_mean", "rate", "fraction", "null (inherit event)", "Override", nullable=True),
        _f("no_show_high", "rate", "fraction", "null (inherit event)", "Override", nullable=True),
        _f("no_show_concentration", "float", "-", "null (inherit event)", "Positive",
           nullable=True, min=0),
        _f("refund_fraction", "rate", "fraction", "1", "Share refunded if event cancelled"),
        _f("fee_refund_fraction", "rate", "fraction", "0",
           "Share of processing fee returned with a refund"),
    ),
    "additional_revenue": (
        _f("id", "str", "-", "Generated stable ID", "Unique", "derived"),
        _f("label", "str", "text", "New revenue line", "1-120 characters", max_len=120),
        _f("unit_price", "money", "USD", "0", "Nonnegative", min=0),
        _f("quantity_basis", "enum", "-", "fixed", "fixed or per_attendee", choices=QUANTITY_BASES),
        _f("quantity", "float", "units", "1", "Nonnegative (fixed basis)", min=0),
        _f("uptake_rate", "rate", "fraction", "1", "Share of attendees buying (per attendee)"),
        _f("units_per_buyer", "float", "units", "1", "Nonnegative", min=0),
        _f("fee_rate", "rate", "fraction", "0", "Processing fee on this line"),
        _f("prepaid", "bool", "-", "false", "Prepaid lines must use fixed quantity"),
        _f("refund_fraction", "rate", "fraction", "1", "Share refunded if cancelled"),
        _f("fee_refund_fraction", "rate", "fraction", "0", "Share of fee returned with refund"),
    ),
    "staffing": (
        _f("id", "str", "-", "Generated stable ID", "Unique", "derived"),
        _f("role", "str", "role label", "New role", "1-80 characters; a role, not a person",
           max_len=80),
        _f("count", "int", "people", "1", "Nonnegative integer", min=0, max=10_000),
        _f("hours", "float", "hours", "Event duration", "Nonnegative", min=0, max=24 * 7),
        _f("pay_basis", "enum", "-", "flat", "flat or hourly", choices=PAY_BASES),
        _f("rate", "money", "USD", "0 (unconfirmed estimate)",
           "Nonnegative; flat fee per person or hourly rate", min=0),
        _f("volunteer", "bool", "-", "false", "Volunteer rows cost 0"),
        _f("required_certifications", "list_enum", "-", "[]", "Listed credentials",
           choices=CERTIFICATIONS),
        _f("confirmed_certifications", "list_enum", "-", "[]", "Listed credentials",
           choices=CERTIFICATIONS),
        _f("coverage_ratio", "float", "attendees per person", "null", "Positive or empty",
           nullable=True, min=0),
        _f("retained_fraction", "rate", "fraction", "1", "Pay owed if cancelled"),
    ),
    "marketing_activities": (
        _f("id", "str", "-", "Generated stable ID", "Unique", "derived"),
        _f("name", "str", "text", "New marketing activity", "1-120 characters", max_len=120),
        _f("offset_days", "int", "days from event", "0", "-365 to 60", min=-365, max=60),
        _f("channels", "list_enum", "-", "Event's selected channels", "Listed channels",
           choices=CHANNELS),
        _f("owner_role", "str", "role label", "Organizer", "1-80 characters", max_len=80),
        _f("status", "enum", "-", "not_started", "Task status", choices=TASK_STATUSES),
    ),
}

# Record groups that are optional (null means "use generated templates").
NULLABLE_RECORD_GROUPS = ("marketing_activities",)

SPEC_BY_PATH = {s.path: s for s in SCALAR_SPECS}
TOP_LEVEL_KEYS = (
    {p.split(".")[0] for p in SPEC_BY_PATH} | set(RECORD_SPECS) | {"provenance"}
)


# ---------------------------------------------------------------------- dataclasses


@dataclass(frozen=True)
class EventInput:
    name: str
    event_type: str
    setting: str
    date: dt.date
    start_time: dt.time
    end_time: dt.time
    timezone: str
    session_count: int
    historical_ack: bool

    @property
    def duration_hours(self) -> float:
        start = dt.datetime.combine(self.date, self.start_time)
        end = dt.datetime.combine(self.date, self.end_time)
        return (end - start).total_seconds() / 3600


@dataclass(frozen=True)
class RainInput:
    has_rain_plan: bool
    alternate_date: dt.date | None
    alternate_venue: str | None


@dataclass(frozen=True)
class GoalsInput:
    primary_goal: str
    target_attendance: int
    target_net_income: float
    spending_limit: float | None


@dataclass(frozen=True)
class VenueInput:
    name: str
    capacity: int
    permit_required: bool
    permit_cost: float
    permit_lead_days: int
    permit_retained_fraction: float
    rental_total: float
    rental_advance: float
    rental_retained_fraction: float
    security_deposit: float
    security_deposit_forfeit_fraction: float
    insurance_required: bool
    insurance_cost: float
    insurance_lead_days: int
    insurance_retained_fraction: float


@dataclass(frozen=True)
class AttendanceInput:
    low: float
    likely: float
    high: float
    planned_peak: float | None


@dataclass(frozen=True)
class NoShowInput:
    low: float
    mean: float
    high: float
    concentration: float


@dataclass(frozen=True)
class ProcessingInput:
    ticket_fee_rate: float


@dataclass(frozen=True)
class WeatherInput:
    cancellation_probability: float


@dataclass(frozen=True)
class SimulationInput:
    runs: int
    seed: int


@dataclass(frozen=True)
class MarketingInput:
    earliest_start: dt.date
    channels: tuple[str, ...]
    budget: float
    budget_retained_fraction: float


@dataclass(frozen=True)
class FixedCost:
    id: str
    label: str
    category: str
    amount: float
    retained_fraction: float
    uncertain: bool
    low: float
    mode: float
    high: float

    @property
    def mean(self) -> float:
        return (self.low + self.mode + self.high) / 3 if self.uncertain else self.amount


@dataclass(frozen=True)
class VariableCost:
    id: str
    label: str
    low: float
    mode: float
    high: float
    retained_fraction: float

    @property
    def mean(self) -> float:
        return (self.low + self.mode + self.high) / 3


@dataclass(frozen=True)
class TicketTier:
    id: str
    label: str
    preset: str
    price: float
    allocation: str
    weight: float
    free_quota: int | None
    billing_basis: str
    no_show_low: float | None
    no_show_mean: float | None
    no_show_high: float | None
    no_show_concentration: float | None
    refund_fraction: float
    fee_refund_fraction: float

    @property
    def has_no_show_override(self) -> bool:
        return self.no_show_mean is not None


@dataclass(frozen=True)
class AdditionalRevenue:
    id: str
    label: str
    unit_price: float
    quantity_basis: str
    quantity: float
    uptake_rate: float
    units_per_buyer: float
    fee_rate: float
    prepaid: bool
    refund_fraction: float
    fee_refund_fraction: float


@dataclass(frozen=True)
class StaffRole:
    id: str
    role: str
    count: int
    hours: float
    pay_basis: str
    rate: float
    volunteer: bool
    required_certifications: tuple[str, ...]
    confirmed_certifications: tuple[str, ...]
    coverage_ratio: float | None
    retained_fraction: float


@dataclass(frozen=True)
class MarketingActivity:
    id: str
    name: str
    offset_days: int
    channels: tuple[str, ...]
    owner_role: str
    status: str


RECORD_CLASSES = {
    "fixed_costs": FixedCost,
    "variable_costs": VariableCost,
    "ticket_tiers": TicketTier,
    "additional_revenue": AdditionalRevenue,
    "staffing": StaffRole,
    "marketing_activities": MarketingActivity,
}


@dataclass(frozen=True)
class PlanInput:
    schema_version: str
    currency: str
    event: EventInput
    rain: RainInput
    goals: GoalsInput
    venue: VenueInput
    attendance: AttendanceInput
    no_show: NoShowInput
    processing: ProcessingInput
    weather: WeatherInput
    simulation: SimulationInput
    marketing: MarketingInput
    fixed_costs: tuple[FixedCost, ...]
    variable_costs: tuple[VariableCost, ...]
    ticket_tiers: tuple[TicketTier, ...]
    additional_revenue: tuple[AdditionalRevenue, ...]
    staffing: tuple[StaffRole, ...]
    marketing_activities: tuple[MarketingActivity, ...] | None
    provenance: dict = None  # path -> provenance record; excluded from hashing semantics

    def to_dict(self) -> dict:
        return to_jsonable(self)


GROUP_CLASSES = {
    "event": EventInput, "rain": RainInput, "goals": GoalsInput, "venue": VenueInput,
    "attendance": AttendanceInput, "no_show": NoShowInput, "processing": ProcessingInput,
    "weather": WeatherInput, "simulation": SimulationInput, "marketing": MarketingInput,
}


def to_jsonable(obj: Any) -> Any:
    """Convert dataclasses, dates, and tuples into JSON-compatible structures."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_jsonable(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, (dt.date, dt.time)):
        return obj.isoformat(timespec="minutes") if isinstance(obj, dt.time) else obj.isoformat()
    return obj


# ------------------------------------------------------------------------- defaults


def record_defaults(group: str, *, duration_hours: float = 1.25,
                    channels: tuple[str, ...] = ("email", "flyers")) -> dict:
    """Default values for a new row in a repeating-record group."""
    if group == "fixed_costs":
        return {"id": new_id("fc"), "label": "New fixed cost", "category": "other", "amount": 0.0,
                "retained_fraction": 1.0, "uncertain": False, "low": None, "mode": None,
                "high": None}
    if group == "variable_costs":
        return {"id": new_id("vc"), "label": "New variable cost", "low": 2.0, "mode": 2.0,
                "high": 2.0, "retained_fraction": 0.0}
    if group == "ticket_tiers":
        return {"id": new_id("tier"), "label": "General", "preset": "general", "price": 15.0,
                "allocation": "weighted", "weight": 1.0, "free_quota": None,
                "billing_basis": "attended", "no_show_low": None, "no_show_mean": None,
                "no_show_high": None, "no_show_concentration": None, "refund_fraction": 1.0,
                "fee_refund_fraction": 0.0}
    if group == "additional_revenue":
        return {"id": new_id("rev"), "label": "New revenue line", "unit_price": 0.0,
                "quantity_basis": "fixed", "quantity": 1.0, "uptake_rate": 1.0,
                "units_per_buyer": 1.0, "fee_rate": 0.0, "prepaid": False,
                "refund_fraction": 1.0, "fee_refund_fraction": 0.0}
    if group == "staffing":
        return {"id": new_id("staff"), "role": "New role", "count": 1,
                "hours": round(duration_hours, 2), "pay_basis": "flat", "rate": 0.0,
                "volunteer": False, "required_certifications": [],
                "confirmed_certifications": [], "coverage_ratio": None,
                "retained_fraction": 1.0}
    if group == "marketing_activities":
        return {"id": new_id("mkt"), "name": "New marketing activity", "offset_days": 0,
                "channels": list(channels), "owner_role": "Organizer", "status": "not_started"}
    raise KeyError(group)


TIER_PRESET_ROWS = {
    "general": {"label": "General", "price": 15.0},
    "early_bird": {"label": "Early bird", "price": 10.0},
    "sliding_scale": {"label": "Sliding scale", "price": 8.0},
    "free": {"label": "Free place", "price": 0.0},
}


def tier_from_preset(preset: str) -> dict:
    row = record_defaults("ticket_tiers")
    row.update(TIER_PRESET_ROWS.get(preset, {}))
    row["preset"] = preset
    row["weight"] = 0.0
    return row


def default_plan(today: dt.date | None = None) -> dict:
    """Factory-default raw plan. Validates without user typing."""
    today = today or today_in(DEFAULT_TZ)
    return {
        "schema_version": SCHEMA_VERSION,
        "currency": CURRENCY,
        "event": {"name": "My wellness event", "event_type": "single_class", "setting": "indoor",
                  "date": (today + dt.timedelta(days=42)).isoformat(), "start_time": "10:00",
                  "end_time": "11:15", "timezone": DEFAULT_TZ, "session_count": 1,
                  "historical_ack": False},
        "rain": {"has_rain_plan": False, "alternate_date": None, "alternate_venue": None},
        "goals": {"primary_goal": "community_reach", "target_attendance": 40,
                  "target_net_income": 0.0, "spending_limit": None},
        "venue": {"name": "Venue to confirm", "capacity": 60, "permit_required": False,
                  "permit_cost": 0.0, "permit_lead_days": 30, "permit_retained_fraction": 1.0,
                  "rental_total": 0.0, "rental_advance": 0.0, "rental_retained_fraction": 1.0,
                  "security_deposit": 0.0, "security_deposit_forfeit_fraction": 0.0,
                  "insurance_required": False, "insurance_cost": 0.0, "insurance_lead_days": 14,
                  "insurance_retained_fraction": 1.0},
        "attendance": {"low": 25.0, "likely": 40.0, "high": 55.0, "planned_peak": None},
        "no_show": {"low": 0.10, "mean": 0.20, "high": 0.30, "concentration": 6.0},
        "processing": {"ticket_fee_rate": 0.0},
        "weather": {"cancellation_probability": 0.0},
        "simulation": {"runs": 10_000, "seed": 42},
        "marketing": {"earliest_start": today.isoformat(), "channels": ["email", "flyers"],
                      "budget": 0.0, "budget_retained_fraction": 1.0},
        "fixed_costs": [
            {**record_defaults("fixed_costs"), "id": "fc-equipment", "label": "Equipment",
             "category": "equipment"},
            {**record_defaults("fixed_costs"), "id": "fc-signage", "label": "Signage",
             "category": "signage"},
            {**record_defaults("fixed_costs"), "id": "fc-printing", "label": "Printing",
             "category": "printing"},
        ],
        "variable_costs": [{**record_defaults("variable_costs"), "id": "vc-supplies",
                            "label": "Supplies per attendee"}],
        "ticket_tiers": [{**record_defaults("ticket_tiers"), "id": "tier-general"}],
        "additional_revenue": [],
        "staffing": [
            {**record_defaults("staffing", duration_hours=1.25), "id": "staff-instructor",
             "role": "Lead instructor", "required_certifications": [],
             "confirmed_certifications": []},
            {**record_defaults("staffing", duration_hours=1.25), "id": "staff-checkin",
             "role": "Check-in", "volunteer": True, "coverage_ratio": 30.0},
        ],
        "marketing_activities": None,
        "provenance": {},
    }


def get_path(d: dict, path: str, default: Any = None) -> Any:
    cur: Any = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def set_path(d: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    cur = d
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value


def spec_inventory() -> list[dict]:
    """Flattened machine-readable schema used for docs and the completeness test."""
    rows = [{"group": "scalar", **asdict(s)} for s in SCALAR_SPECS]
    for group, specs in RECORD_SPECS.items():
        rows += [{"group": group, **asdict(s)} for s in specs]
    for row in rows:
        row["choices"] = list(row["choices"])
    return rows
