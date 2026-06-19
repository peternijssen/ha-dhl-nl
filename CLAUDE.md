# Working in this repository

This is a Home Assistant custom integration for DHL eCommerce NL parcel
tracking. Distributed via HACS; not part of HA core.

## Always consult HA developer documentation

Home Assistant's integration patterns evolve continuously. **Do not rely
on memory of past patterns** — fetch the canonical page before changing
a topic area, and check the developer blog before introducing anything
you only "know" from training data.

| When you change | Fetch first |
|---|---|
| Entity properties, naming, lifecycle, attributes | https://developers.home-assistant.io/docs/core/entity/ |
| Sensor specifics (state/device classes, units) | https://developers.home-assistant.io/docs/core/entity/sensor |
| Config flow, options flow, reauth, reconfigure | https://developers.home-assistant.io/docs/config_entries_config_flow_handler |
| DataUpdateCoordinator pattern | https://developers.home-assistant.io/docs/integration_fetching_data |
| Quality scale rules | https://developers.home-assistant.io/docs/core/integration-quality-scale |
| Diagnostics | https://developers.home-assistant.io/docs/core/integration/diagnostics |
| Translations | https://developers.home-assistant.io/docs/internationalization/core |

Branding is handled by the local `brand/` folder (HACS reads `icon.png`
from it). The official `home-assistant/brands` repo is for HA Core
integrations and does not apply here.

### Recent developer-facing changes

Before introducing patterns you only know from training data, check:

- https://developers.home-assistant.io/blog — API deprecations, new
  patterns, breaking changes. Recent posts trump older recollection.
- https://github.com/home-assistant/architecture/discussions — design
  decisions in flight that have not made it into stable docs yet.

## What is already in place

The integration is aligned with the **silver** quality scale tier. Don't
re-propose these as improvements:

- `quality_scale: "silver"` in manifest, minimum HA version `2024.7.0`
- `ConfigEntry.runtime_data` (typed dataclass `DhlData`)
- `PARALLEL_UPDATES = 0` in `sensor.py`
- Coordinator takes `config_entry=entry` so `self.config_entry` is
  available on the base class
- Per-parcel sensors self-remove via `async_remove(force_remove=True)`
- Reauth flow uses `async_update_reload_and_abort` (one helper call
  instead of update + reload + abort)
- `aiohttp.ClientError` is intentionally not caught in the coordinator —
  `DataUpdateCoordinator` wraps it automatically
- Diagnostics handler in `diagnostics.py` with credential and PII
  redaction
- Tests cover config flow, sensor, coordinator (incl. event firing),
  diagnostics, and setup/unload lifecycle
- `_unrecorded_attributes` on every summary sensor — parcel/shipment
  lists are kept out of the recorder long-term tables
- `_attr_attribution = "Data provided by DHL"` per entity

### Adopted in 2.0.0 (do not refactor away)

- **`ParcelStatus` enum** in `const.py` — canonical
  carrier-agnostic statuses. `normalize_parcel` maps the raw DHL
  status/category via `map_parcel_status` and reports `ParcelStatus.UNKNOWN`
  (with one-shot info log) for anything not yet in the map. The original
  DHL status string lives on the parcel's `raw_status` field; do not
  re-introduce it on `status`.
- **Events**: the coordinator fires `dhl_nl_parcel_registered` and
  `dhl_nl_parcel_status_changed` on the HA event bus. Events are
  suppressed on the very first refresh so we do not flood users with
  "registered" events for parcels that already existed.
- **`has_entity_name = True`** on every entity, with `translation_key`
  routing names through `strings.json` and the language files. Drop
  `_attr_name` is the rule — translations are the source of truth.
- **Translated unit-of-measurement** (`entity.sensor.<key>.unit_of_measurement`
  in strings/translations). `_attr_native_unit_of_measurement` is
  intentionally absent.
- **`icons.json`** holds all sensor icons via the `translation_key`. Do
  not re-introduce `_attr_icon` on the sensor classes.
- **Device name pattern**: `"DHL (<email>)"`. Sensors auto-prefix with
  this, yielding friendly names like
  `DHL (account@example.com) Incoming parcels`.

## Planned for the next major bump

- **Exception translations** (Gold-tier rule). `UpdateFailed(f"...")`
  still uses f-strings; the Gold push will move to `translation_key` +
  `translation_placeholders`.

## Deliberately skipped (no plan to change)

- **Slimming `extra_state_attributes`** on summary sensors. The full
  parcel list stays; `_unrecorded_attributes` handles the recorder side.
- **`async-dependency` / `inject-websession`** (Platinum). The DHL API
  client is already async and accepts an injected session — no further
  work needed there. Listed for completeness.

## Repo-specific quirks

- Each config entry uses its **own aiohttp `CookieJar`** (see
  `__init__.py`) so two DHL accounts don't overwrite each other's auth
  cookies. Do not refactor this to share the HA-managed session's jar.
- `_get_en_route_parcels` / `_get_pickup_parcels` filter on
  `ParcelStatus.AT_PICKUP_POINT`. The DHL-specific raw status that maps
  to that value is `NOTIFICATION_FOR_PARCELSHOP_COLLECTION_HAS_BEEN_SENT`
  — kept as `STATUS_AT_SERVICE_POINT` in `const.py` for the mapping
  table in `coordinator.py`.
- Network calls return raw JSON dicts; there is no DTO layer.

## Running tests

```
python -m pytest tests/ --cov=custom_components.dhl_nl
```

Coverage must stay **above 95%** (the silver `test-coverage` rule on
developers.home-assistant.io). Run before committing.
