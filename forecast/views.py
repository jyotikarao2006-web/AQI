import datetime as dt
import json
import logging
import math

import numpy as np
import pandas as pd
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from . import ml, openmeteo
from .aqi import (BANDS, CITIES, FEATURES, FIELDS, LSTM_FEATURES, RANGES, STATES, STATES_BY_NAME,
                  band_for)


log = logging.getLogger(__name__)


class BadInput(ValueError):
    pass


def _number(data, name, required=True):
    if name not in data or data[name] in (None, ""):
        if required:
            raise BadInput(f"Enter a value for {name}.")
        return None
    try:
        v = float(data[name])
    except (TypeError, ValueError):
        raise BadInput(f"{name} must be a number.")
    lo, hi = RANGES[name]
    if not math.isfinite(v) or not lo <= v <= hi:
        raise BadInput(f"{name} must be between {lo} and {hi}.")
    return v


def _body(request):
    try:
        data = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        raise BadInput("Request body must be valid JSON.")
    if not isinstance(data, dict):
        raise BadInput("Request body must be a JSON object.")
    return data


def _aqi_payload(raw):
    aqi = float(np.clip(raw, 0, 500))
    b = band_for(aqi)
    return {"aqi": round(aqi), "category": b["name"], "color": b["color"], "advice": b["advice"]}


def _fail(exc, status=400):
    return JsonResponse({"error": str(exc)}, status=status)


@ensure_csrf_cookie
def index(request):
    return render(request, "forecast/index.html", {
        "config": {"fields": FIELDS, "bands": BANDS, "cities": CITIES, "states": STATES},
    })


@require_GET
def health(request):
    files = {p.name: p.exists() for p in ml.settings.MODEL_DIR.iterdir()} if ml.settings.MODEL_DIR.exists() else {}
    return JsonResponse({"status": "ok", "model_files": files})


@require_GET
def live(request):
    """Last 24 hours of pollution + weather for an Indian state, from Open-Meteo.

    GET /api/live/?state=Maharashtra
    Returns the 24 hourly rows (oldest first), each with an estimated AQI from the XGBoost model,
    plus the newest row as `latest` so the page can fill in the Conditions form.
    """
    name = (request.GET.get("state") or "").strip()
    state = STATES_BY_NAME.get(name.lower())
    if not state:
        return _fail(BadInput("Choose a state or union territory of India."))
    try:
        rows = openmeteo.fetch_last_24h(state["lat"], state["lon"])
    except openmeteo.OpenMeteoError as e:
        log.warning("Open-Meteo failed for %s: %s", state["name"], e)
        return _fail(e, 502)
    except Exception as e:
        log.exception("live data failed")
        return _fail(f"Could not load live data: {e}", 500)

    # Per-hour AQI estimate. If the model is unavailable the raw readings are still returned.
    try:
        for r in rows:
            r["aqi"] = _aqi_payload(ml.predict_xgb({f: r[f] for f in FEATURES}))["aqi"]
    except Exception:
        log.warning("could not estimate AQI from live data", exc_info=True)
        for r in rows:
            r["aqi"] = None
    latest = rows[-1]
    return JsonResponse({
        "state": state["name"], "location": state["capital"],
        "latitude": state["lat"], "longitude": state["lon"],
        "from": rows[0]["time"], "to": latest["time"],
        "rows": rows,
        "latest": {f: latest[f] for f in FEATURES},
        "latest_aqi": _aqi_payload(latest["aqi"]) if latest["aqi"] is not None else None,
        "source": "Open-Meteo (CAMS air-quality model and weather model; not ground-station readings)",
    })


@require_POST
def predict(request):
    """Single AQI estimate from the 10 pollutant + weather inputs (XGBoost)."""
    try:
        data = _body(request)
        values = {f: _number(data, f) for f in FEATURES}
        return JsonResponse(_aqi_payload(ml.predict_xgb(values)))
    except BadInput as e:
        return _fail(e)
    except Exception as e:  # model files missing, library mismatch, etc.
        log.exception("predict failed")
        return _fail(f"Prediction failed: {e}", 500)


@require_POST
def forecast(request):
    """7-day outlook from a 24-step window (LSTM)."""
    try:
        data = _body(request)
        history = data.get("history")
        state = STATES_BY_NAME.get(str(data.get("state") or "").strip().lower())
        if state and not history:  # "use the last 24 hours for this state" without sending rows
            try:
                history = openmeteo.fetch_last_24h(state["lat"], state["lon"])
            except openmeteo.OpenMeteoError as e:
                return _fail(e, 502)
        if state:
            data.setdefault("Latitude", state["lat"])
            data.setdefault("Longitude", state["lon"])
        lat = _number(data, "Latitude")
        lon = _number(data, "Longitude")

        if history:
            if not isinstance(history, list) or len(history) < ml.WINDOW:
                raise BadInput(f"History needs at least {ml.WINDOW} rows.")
            rows = []
            for r in history[-ml.WINDOW:]:
                row = {f: _number(r, f) for f in FEATURES}
                row["Latitude"] = _number(r, "Latitude", False) or lat
                row["Longitude"] = _number(r, "Longitude", False) or lon
                rows.append(row)
        else:
            cond = data.get("conditions") or {}
            base = {f: _number(cond, f) for f in FEATURES}
            base.update(Latitude=lat, Longitude=lon)
            rows = [dict(base) for _ in range(ml.WINDOW)]
        window = pd.DataFrame(rows)[LSTM_FEATURES]

        outlook = []
        for day in (data.get("outlook") or [])[:7]:
            outlook.append({k: _number(day, k, False) for k in FEATURES if _number(day, k, False) is not None})

        _, preds, mode = ml.forecast_week(window, outlook)
        slope = float(np.polyfit(np.arange(len(preds)), preds, 1)[0])
        label = "stable" if abs(slope) < 2 else ("rising" if slope > 0 else "falling")

        today = dt.date.today()
        days = [{"date": (today + dt.timedelta(days=i + 1)).isoformat(), **_aqi_payload(p)}
                for i, p in enumerate(preds)]
        note = None
        if mode == "assumed-range":
            lo, hi = ml.settings.LSTM_OUTPUT_RANGE
            note = (f"No target scaler was found, so the LSTM output was mapped onto an AQI range of {lo} to {hi}. "
                    "Add ml_models/lstm_y_scaler.pkl for exact values.")
        return JsonResponse({"days": days, "trend": {"label": label, "slope": round(slope, 1)}})
    except BadInput as e:
        return _fail(e)
    except Exception as e:
        log.exception("forecast failed")
        return _fail(f"Forecast failed: {e}", 500)
