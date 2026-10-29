# Input schema (version 1.0)

Generated from `wellnesspop/schema.py` by `scripts/generate_schema_doc.py`. Rates are fractions (0.2 = 20%); money is USD; dates are ISO (YYYY-MM-DD).


## Scalar fields

| Field | Type | Unit | Default rule | Validation | Provenance | Nullable |
|---|---|---|---|---|---|---|
| `schema_version` | str | - | 1.0 | Must equal 1.0 | derived | no |
| `currency` | enum (USD) | - | USD | USD only in MVP | derived | no |
| `event.name` | str | text | My wellness event | 1-120 characters; no contact details | illustrative | no |
| `event.event_type` | enum (single_class, one_day_fair) | - | single_class | single_class or one_day_fair | brief | no |
| `event.setting` | enum (indoor, outdoor, hybrid) | - | indoor | indoor, outdoor or hybrid | illustrative | no |
| `event.date` | date | date | Today in event timezone + 42 days | Past dates require historical-plan acknowledgment | illustrative | no |
| `event.start_time` | time | local time | 10:00 | Before end time | illustrative | no |
| `event.end_time` | time | local time | 11:15 | After start time, same day | illustrative | no |
| `event.timezone` | tz | IANA zone | America/Chicago | Valid IANA timezone | brief | no |
| `event.session_count` | int | sessions | 1 | Positive integer | illustrative | no |
| `event.historical_ack` | bool | - | false | Must be true to plan an event or marketing start in the past | derived | no |
| `rain.has_rain_plan` | bool | - | false | Warn on outdoor/hybrid without a plan | illustrative | no |
| `rain.alternate_date` | date | date | null | After event date; required (or venue) when rain plan enabled | illustrative | yes |
| `rain.alternate_venue` | str | text | null | Descriptive venue name only, 0-120 chars | illustrative | yes |
| `goals.primary_goal` | enum (net_revenue, community_reach, paid_program_pilot) | - | community_reach | One of the listed goals | illustrative | no |
| `goals.target_attendance` | int | people on site | 40 | 0 to venue capacity | illustrative | no |
| `goals.target_net_income` | signed_money | USD | 0 | May be negative for subsidized events | illustrative | no |
| `goals.spending_limit` | money | USD | null (not supplied) | Nonnegative or empty | illustrative | yes |
| `venue.name` | str | text | Venue to confirm | 1-120 characters | illustrative | no |
| `venue.capacity` | int | people | 60 | 1-100,000 (product limit, not a legal standard) | illustrative | no |
| `venue.permit_required` | bool | - | false | Enables permit cost and tasks | illustrative | no |
| `venue.permit_cost` | money | USD | 0 | Nonnegative; counted once in fixed ledger | illustrative | no |
| `venue.permit_lead_days` | int | days | 30 (illustrative, unverified) | 0-365 | illustrative | no |
| `venue.permit_retained_fraction` | rate | fraction | 1 | Share of permit cost lost if cancelled, 0-1 | illustrative | no |
| `venue.rental_total` | money | USD | 0 | Total rental expense incl. any advance | illustrative | no |
| `venue.rental_advance` | money | USD | 0 | 0 to rental total; cash-timing note only | illustrative | no |
| `venue.rental_retained_fraction` | rate | fraction | 1 | Share of rental lost if cancelled, 0-1 | illustrative | no |
| `venue.security_deposit` | money | USD | 0 | Refundable cash requirement; not an expense | illustrative | no |
| `venue.security_deposit_forfeit_fraction` | rate | fraction | 0 | Share of the deposit explicitly expected to be forfeited (becomes an expense) | illustrative | no |
| `venue.insurance_required` | bool | - | false | Enables insurance cost and tasks | illustrative | no |
| `venue.insurance_cost` | money | USD | 0 | Nonnegative; counted once | illustrative | no |
| `venue.insurance_lead_days` | int | days | 14 (illustrative planning rule) | 0-365 | illustrative | no |
| `venue.insurance_retained_fraction` | rate | fraction | 1 | Share of insurance lost if cancelled, 0-1 | illustrative | no |
| `attendance.low` | float | registrations | 25 | 0 <= low <= likely | illustrative | no |
| `attendance.likely` | float | registrations | 40 | low <= likely <= high | illustrative | no |
| `attendance.high` | float | registrations | 55 | likely <= high <= capacity | illustrative | no |
| `attendance.planned_peak` | float | people | null (use high registrations) | Optional justified staffing peak, 0 to capacity | illustrative | yes |
| `no_show.low` | rate | fraction | 0.10 | 0 <= low <= mean | illustrative | no |
| `no_show.mean` | rate | fraction | 0.20 | Strictly inside (low, high) unless all equal | illustrative | no |
| `no_show.high` | rate | fraction | 0.30 | mean <= high <= 1 | illustrative | no |
| `no_show.concentration` | float | - | 6 (model-shape assumption) | Positive | illustrative | no |
| `processing.ticket_fee_rate` | rate | fraction | 0 | User-entered processing fee; no payment integration | illustrative | no |
| `weather.cancellation_probability` | rate | probability | 0 indoor; 0.25 outdoor; 0.20 hybrid (illustrative) | Forced to 0 indoors | illustrative | no |
| `simulation.runs` | int | trials | 10000 | 10,000-100,000 | derived | no |
| `simulation.seed` | int | - | 42 | Nonnegative 63-bit integer | derived | no |
| `marketing.earliest_start` | date | date | Today in event timezone | Past dates only in historical-plan mode | illustrative | no |
| `marketing.channels` | list_enum (instagram, email, flyers, partner_newsletter, eventbrite) | - | email, flyers | Subset of supported channels | illustrative | no |
| `marketing.budget` | money | USD | 0 | Fixed cost counted once; nothing is sent | illustrative | no |
| `marketing.budget_retained_fraction` | rate | fraction | 1 | Share of marketing spend lost if cancelled | illustrative | no |

## Records: `fixed_costs`

| Field | Type | Unit | Default rule | Validation | Provenance | Nullable |
|---|---|---|---|---|---|---|
| `id` | str | - | Generated stable ID | Unique within plan | derived | no |
| `label` | str | text | New fixed cost | 1-120 characters | illustrative | no |
| `category` | enum (equipment, signage, printing, supplies, sound, tents, furniture, speaker, venue, insurance, other) | - | other | Listed category | illustrative | no |
| `amount` | money | USD | 0 | Nonnegative; equals triangular mean when uncertain | illustrative | no |
| `retained_fraction` | rate | fraction | 1 | Cost lost if cancelled, 0-1 | illustrative | no |
| `uncertain` | bool | - | false | If true, low/mode/high are sampled | illustrative | no |
| `low` | money | USD | = amount | 0 <= low <= mode | illustrative | yes |
| `mode` | money | USD | = amount | low <= mode <= high | illustrative | yes |
| `high` | money | USD | = amount | mode <= high | illustrative | yes |

## Records: `variable_costs`

| Field | Type | Unit | Default rule | Validation | Provenance | Nullable |
|---|---|---|---|---|---|---|
| `id` | str | - | Generated stable ID | Unique | derived | no |
| `label` | str | text | New variable cost | 1-120 characters | illustrative | no |
| `low` | money | USD per attendee | 2 | 0 <= low <= mode | illustrative | no |
| `mode` | money | USD per attendee | 2 | low <= mode <= high | illustrative | no |
| `high` | money | USD per attendee | 2 | mode <= high | illustrative | no |
| `retained_fraction` | rate | fraction | 0 | Supplies cost kept if cancelled | illustrative | no |

## Records: `ticket_tiers`

| Field | Type | Unit | Default rule | Validation | Provenance | Nullable |
|---|---|---|---|---|---|---|
| `id` | str | - | Generated stable ID | Unique | derived | no |
| `label` | str | text | General | 1-120 characters | illustrative | no |
| `preset` | enum (general, early_bird, sliding_scale, free, custom) | - | general | Tier preset | illustrative | no |
| `price` | money | USD | 15 | Nonnegative; 0 for free tiers | illustrative | no |
| `allocation` | enum (weighted, free_quota) | - | weighted | weighted or free_quota | illustrative | no |
| `weight` | rate | share | 1 | Weighted tiers sum to 1 | illustrative | no |
| `free_quota` | int | registrations | null | Free-quota tiers only; price must be 0 | illustrative | yes |
| `billing_basis` | enum (attended, registered) | - | attended | attended or registered (prepaid) | illustrative | no |
| `no_show_low` | rate | fraction | null (inherit event) | Override: all or none | illustrative | yes |
| `no_show_mean` | rate | fraction | null (inherit event) | Override | illustrative | yes |
| `no_show_high` | rate | fraction | null (inherit event) | Override | illustrative | yes |
| `no_show_concentration` | float | - | null (inherit event) | Positive | illustrative | yes |
| `refund_fraction` | rate | fraction | 1 | Share refunded if event cancelled | illustrative | no |
| `fee_refund_fraction` | rate | fraction | 0 | Share of processing fee returned with a refund | illustrative | no |

## Records: `additional_revenue`

| Field | Type | Unit | Default rule | Validation | Provenance | Nullable |
|---|---|---|---|---|---|---|
| `id` | str | - | Generated stable ID | Unique | derived | no |
| `label` | str | text | New revenue line | 1-120 characters | illustrative | no |
| `unit_price` | money | USD | 0 | Nonnegative | illustrative | no |
| `quantity_basis` | enum (fixed, per_attendee) | - | fixed | fixed or per_attendee | illustrative | no |
| `quantity` | float | units | 1 | Nonnegative (fixed basis) | illustrative | no |
| `uptake_rate` | rate | fraction | 1 | Share of attendees buying (per attendee) | illustrative | no |
| `units_per_buyer` | float | units | 1 | Nonnegative | illustrative | no |
| `fee_rate` | rate | fraction | 0 | Processing fee on this line | illustrative | no |
| `prepaid` | bool | - | false | Prepaid lines must use fixed quantity | illustrative | no |
| `refund_fraction` | rate | fraction | 1 | Share refunded if cancelled | illustrative | no |
| `fee_refund_fraction` | rate | fraction | 0 | Share of fee returned with refund | illustrative | no |

## Records: `staffing`

| Field | Type | Unit | Default rule | Validation | Provenance | Nullable |
|---|---|---|---|---|---|---|
| `id` | str | - | Generated stable ID | Unique | derived | no |
| `role` | str | role label | New role | 1-80 characters; a role, not a person | illustrative | no |
| `count` | int | people | 1 | Nonnegative integer | illustrative | no |
| `hours` | float | hours | Event duration | Nonnegative | illustrative | no |
| `pay_basis` | enum (flat, hourly) | - | flat | flat or hourly | illustrative | no |
| `rate` | money | USD | 0 (unconfirmed estimate) | Nonnegative; flat fee per person or hourly rate | illustrative | no |
| `volunteer` | bool | - | false | Volunteer rows cost 0 | illustrative | no |
| `required_certifications` | list_enum (cpr, first_aid, instructor_credential) | - | [] | Listed credentials | illustrative | no |
| `confirmed_certifications` | list_enum (cpr, first_aid, instructor_credential) | - | [] | Listed credentials | illustrative | no |
| `coverage_ratio` | float | attendees per person | null | Positive or empty | illustrative | yes |
| `retained_fraction` | rate | fraction | 1 | Pay owed if cancelled | illustrative | no |

## Records: `marketing_activities`

| Field | Type | Unit | Default rule | Validation | Provenance | Nullable |
|---|---|---|---|---|---|---|
| `id` | str | - | Generated stable ID | Unique | derived | no |
| `name` | str | text | New marketing activity | 1-120 characters | illustrative | no |
| `offset_days` | int | days from event | 0 | -365 to 60 | illustrative | no |
| `channels` | list_enum (instagram, email, flyers, partner_newsletter, eventbrite) | - | Event's selected channels | Listed channels | illustrative | no |
| `owner_role` | str | role label | Organizer | 1-80 characters | illustrative | no |
| `status` | enum (not_started, in_progress, complete, blocked) | - | not_started | Task status | illustrative | no |

Provenance conventions: `illustrative` for invented defaults, `brief` for Appendix B values, `derived` for calculated or system values, `user` once edited (the original provenance is kept in `original_source_kind`), `researched` for values with a documented source and retrieval date.
