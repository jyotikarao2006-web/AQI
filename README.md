# AQI forecaster (Django)

Django backend + single-page frontend on top of your trained models.

## Run

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py runserver
```
Open http://127.0.0.1:8000

## What it does

| Piece | Model | Endpoint |
|---|---|---|
| Live AQI estimate while you edit conditions | XGBoost (10 inputs) | `POST /api/predict/` |
| 7-day outlook + trend | LSTM (24 steps x 12 features) | `POST /api/forecast/` |
| File check | n/a | `GET /api/health/` |

## Things to check against your training notebook

1. **XGBoost has no lag features.** The saved model takes 10 same-day inputs (pollutants + weather).
   It estimates AQI for the conditions you give it. For "tomorrow", feed it tomorrow's expected conditions,
   or retrain with lag features (yesterday's AQI, 7-day mean) and update `FEATURES` in `forecast/aqi.py`.
2. **LSTM target alignment.** `LSTM_TARGET_IS_NEXT_STEP` in `config/settings.py` must match how you built `y`
   (output at step t = AQI at t, or AQI at t+1).
3. **LSTM output scale.** If `ml_models/lstm_y_scaler.pkl` exists it is used. Otherwise, if the output looks scaled (0-1),
   it is mapped onto `LSTM_OUTPUT_RANGE` (default 0-500) and the page shows a note saying so.
4. **7-day forecast is a rolling scenario.** The LSTM predicts AQI, not future weather or pollutants, so each new
   day repeats the last known conditions unless you provide a weather outlook in the UI.
5. Timestep size (hours vs days) is not stored in the model; the UI assumes one step = one day.

## Deploying
Set `DJANGO_DEBUG=0`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`; serve with gunicorn and add WhiteNoise
(or nginx) for static files.
