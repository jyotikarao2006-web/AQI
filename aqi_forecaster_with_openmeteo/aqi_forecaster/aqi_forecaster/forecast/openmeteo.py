"""Live data from Open-Meteo (https://open-meteo.com/): the last 24 hours for a location.

Two free, key-less endpoints are combined:
  * Air quality API  -> PM2.5, PM10, NO2, SO2, CO, O3   (CAMS model, ug/m3)
  * Forecast API     -> temperature, humidity, wind, precipitation (past_days=1)

Both are asked for yesterday + today in India time (Asia/Kolkata); we keep the 24 hourly
rows that end at the current hour. Column names and units are converted to what the
trained models expect (see FIELDS in aqi.py).
"""
import datetime as dt
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import pandas as pd

from .aqi import FEATURES, RANGES

log = logging.getLogger(__name__)

AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
TZ_NAME = "Asia/Kolkata"
IST = ZoneInfo(TZ_NAME)
HOURS = 24
TIMEOUT = 15          # seconds per request
CACHE_SECONDS = 600   # Open-Meteo updates hourly; no need to call more often than this

# Open-Meteo variable -> our column name
AIR_VARS = {
    "pm2_5": "PM2.5",
    "pm10": "PM10",
    "nitrogen_dioxide": "NO2",
    "sulphur_dioxide": "SO2",
    "carbon_monoxide": "CO",
    "ozone": "O3",
}
WEATHER_VARS = {
    "temperature_2m": "Temperature",
    "relative_humidity_2m": "Humidity",
    "wind_speed_10m": "WindSpeed",
    "precipitation": "Rainfall",
}

_cache = {}
_cache_lock = threading.Lock()


class OpenMeteoError(RuntimeError):
    """Open-Meteo could not be reached or returned something unusable."""


def _get_json(url, params):
    full = f"{url}?{urlencode(params)}"
    req = Request(full, headers={"User-Agent": "aqi-forecaster/1.0", "Accept": "application/json"})
    try:
        with urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        try:
            reason = json.loads(e.read().decode("utf-8")).get("reason")
        except Exception:
            reason = None
        raise OpenMeteoError(f"Open-Meteo returned an error ({e.code}){': ' + reason if reason else ''}.") from e
    except (URLError, TimeoutError, OSError) as e:
        raise OpenMeteoError("Could not reach Open-Meteo. Check your internet connection and try again.") from e
    except ValueError as e:
        raise OpenMeteoError("Open-Meteo sent a response that could not be read.") from e


def _frame(payload, mapping):
    hourly = (payload or {}).get("hourly") or {}
    if "time" not in hourly:
        raise OpenMeteoError("Open-Meteo response had no hourly data.")
    df = pd.DataFrame({"time": pd.to_datetime(hourly["time"])})
    for src, dst in mapping.items():
        df[dst] = pd.to_numeric(pd.Series(hourly.get(src, [None] * len(df))), errors="coerce")
    return df.set_index("time")


def _now_ist():
    return dt.datetime.now(IST).replace(tzinfo=None)  # Open-Meteo times are naive local (IST)


def fetch_last_24h(lat, lon, now=None):
    """Returns a list of 24 dicts (oldest first):
        {"time": "2026-10-09T17:00", "PM2.5": .., ..., "Rainfall": ..}
    Raises OpenMeteoError on any network / data problem."""
    key = (round(lat, 3), round(lon, 3))
    with _cache_lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < CACHE_SECONDS and now is None:
            return [dict(r) for r in hit[1]]

    common = {"latitude": lat, "longitude": lon, "past_days": 1, "forecast_days": 1, "timezone": TZ_NAME}
    air_params = {**common, "hourly": ",".join(AIR_VARS)}
    wx_params = {**common, "hourly": ",".join(WEATHER_VARS), "wind_speed_unit": "ms"}
    with ThreadPoolExecutor(max_workers=2) as pool:
        f_air = pool.submit(_get_json, AIR_URL, air_params)
        f_wx = pool.submit(_get_json, WEATHER_URL, wx_params)
        air, wx = f_air.result(), f_wx.result()

    df = _frame(air, AIR_VARS).join(_frame(wx, WEATHER_VARS), how="inner")
    df["CO"] = df["CO"] / 1000.0  # ug/m3 -> mg/m3 (the models use mg/m3)

    # keep only hours that have already happened, then the latest 24 of them
    current_hour = (now or _now_ist()).replace(minute=0, second=0, microsecond=0)
    df = df[df.index <= current_hour].sort_index().tail(HOURS)
    if len(df) < HOURS:
        raise OpenMeteoError(f"Open-Meteo only returned {len(df)} hours of data for this location.")

    df = df[FEATURES]
    empty = [c for c in FEATURES if df[c].isna().all()]
    if empty:
        raise OpenMeteoError(f"Open-Meteo has no recent {', '.join(empty)} data for this location.")
    # Fill the odd missing hour (most often the newest air-quality hour) from its neighbours.
    df = df.interpolate(limit_direction="both")
    for col in FEATURES:  # stay inside the ranges the model and validators accept
        lo, hi = RANGES[col]
        df[col] = df[col].clip(lo, hi)

    rows = []
    for ts, r in df.iterrows():
        row = {"time": ts.strftime("%Y-%m-%dT%H:%M")}
        row.update({c: round(float(r[c]), 2) for c in FEATURES})
        rows.append(row)

    if now is None:
        with _cache_lock:
            _cache[key] = (time.time(), rows)
    return [dict(r) for r in rows]
