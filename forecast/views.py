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

from . import ml
from .aqi import BANDS, CITIES, FEATURES, FIELDS, LSTM_FEATURES, RANGES, band_for


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
        "config": {"fields": FIELDS, "bands": BANDS, "cities": CITIES},
    })


@require_GET
def health(request):
    files = {p.name: p.exists() for p in ml.settings.MODEL_DIR.iterdir()} if ml.settings.MODEL_DIR.exists() else {}
    return JsonResponse({"status": "ok", "model_files": files})


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
        lat = _number(data, "Latitude")
        lon = _number(data, "Longitude")

        history = data.get("history")
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
        return JsonResponse({"days": days, "trend": {"label": label, "slope": round(slope, 1)}, "note": note})
    except BadInput as e:
        return _fail(e)
    except Exception as e:
        log.exception("forecast failed")
        return _fail(f"Forecast failed: {e}", 500)
