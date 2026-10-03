"""Model loading and inference. Models load lazily, once per process."""
import logging
import threading
import warnings

import joblib
import numpy as np
import pandas as pd
from django.conf import settings

from .aqi import FEATURES, LSTM_FEATURES
from .xgb_numpy import TreeEnsemble

log = logging.getLogger(__name__)

WINDOW = 24  # timesteps the LSTM was trained on
_lock = threading.Lock()
_cache = {}


def _get(name, loader):
    with _lock:
        if name not in _cache:
            _cache[name] = loader()
        return _cache[name]


def _path(filename):
    return settings.MODEL_DIR / filename


def xgb_model():
    """Returns (kind, model). Tries xgboost on the portable JSON first, then a pure-numpy
    evaluator of the same JSON, then the original pickle."""
    def load():
        j = _path("aqi_xgboost_model.json")
        if j.exists():
            try:
                import xgboost as xgb
                booster = xgb.Booster()
                booster.load_model(str(j))
                return "booster", booster
            except Exception:
                log.warning("xgboost could not load %s; using the numpy evaluator", j.name, exc_info=True)
            return "numpy", TreeEnsemble(j)
        return "sklearn", joblib.load(_path("aqi_xgboost_model.pkl"))
    return _get("xgb", load)


def x_scaler():
    return _get("x_scaler", lambda: joblib.load(_path("lstm_X_scaler.pkl")))


def y_scaler():
    """Optional: drop lstm_y_scaler.pkl into ml_models/ if you scaled AQI in training."""
    def load():
        p = _path("lstm_y_scaler.pkl")
        return joblib.load(p) if p.exists() else None
    return _get("y_scaler", load)


def lstm_model():
    def load():
        import keras
        return keras.models.load_model(_path("aqi_lstm_model.keras"), compile=False)
    return _get("lstm", load)


# --- XGBoost ---------------------------------------------------------------
def predict_xgb(values: dict) -> float:
    row = pd.DataFrame([[values[f] for f in FEATURES]], columns=FEATURES)
    kind, model = xgb_model()
    if kind == "booster":
        import xgboost as xgb
        return float(model.predict(xgb.DMatrix(row))[0])
    if kind == "numpy":
        return float(model.predict(row.to_numpy())[0])
    return float(model.predict(row)[0])


# --- LSTM ------------------------------------------------------------------
def _predict_window(window: pd.DataFrame):
    """window: WINDOW rows x 12 columns -> (WINDOW AQI values, scale mode).

    scale mode: "scaler" (lstm_y_scaler.pkl used), "assumed-range" (LSTM_OUTPUT_RANGE used), "raw".
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        scaled = x_scaler().transform(window[LSTM_FEATURES])
    x = np.clip(scaled, 0.0, 1.0).astype("float32")[None, :, :]
    out = np.asarray(lstm_model().predict(x, verbose=0)).reshape(-1)
    ys = y_scaler()
    if ys is not None:
        return ys.inverse_transform(out.reshape(-1, 1)).ravel(), "scaler"
    if np.nanmax(np.abs(out)) <= 1.5:  # output is still in scaled units
        rng = getattr(settings, "LSTM_OUTPUT_RANGE", None)
        if not rng:
            raise RuntimeError(
                "The LSTM output looks scaled (values between 0 and 1). Put your target scaler at "
                "ml_models/lstm_y_scaler.pkl, or set LSTM_OUTPUT_RANGE = (min_aqi, max_aqi) in config/settings.py."
            )
        lo, hi = rng
        return out * (hi - lo) + lo, "assumed-range"
    return out, "raw"


def forecast_week(window: pd.DataFrame, outlook=None, horizon: int = 7):
    """Roll the 24-step window forward one step per day.

    Future conditions are unknown, so each new day repeats the last row
    (persistence) unless the caller supplies an `outlook` entry for that day.
    Returns (aqi_for_current_window, [aqi per forecast day], scale_mode).
    """
    outlook = outlook or []
    next_step = getattr(settings, "LSTM_TARGET_IS_NEXT_STEP", False)
    w = window[LSTM_FEATURES].astype(float).reset_index(drop=True)
    first, mode = _predict_window(w)
    preds = []

    def advance(i):
        nonlocal w
        row = w.iloc[-1].copy()
        if i < len(outlook):
            for k, v in outlook[i].items():
                row[k] = v
        w = pd.concat([w.iloc[1:], row.to_frame().T], ignore_index=True)

    for i in range(horizon):
        if next_step:
            out, mode = _predict_window(w)
            preds.append(float(out[-1]))
            advance(i)
        else:
            advance(i)
            out, mode = _predict_window(w)
            preds.append(float(out[-1]))
    return first, preds, mode
