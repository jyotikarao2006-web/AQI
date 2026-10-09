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
| Last 24 hours for an Indian state (Open-Meteo) | XGBoost per hour | `GET /api/live/?state=Maharashtra` |
| File check | n/a | `GET /api/health/` |

## Live data from Open-Meteo

Pick a state or union territory in the header. The backend (`forecast/openmeteo.py`) calls the free,
key-less [Open-Meteo](https://open-meteo.com/) air-quality and weather APIs for that state's capital and
returns the last 24 hourly rows (India time). The page then:

- fills the Conditions form with the newest hour and shows its AQI,
- shows a 24-hour chart and table (estimated AQI per hour from the XGBoost model),
- feeds the 24 rows to the LSTM as its history window ("Use the last 24 hours loaded for the selected state").

Notes: values are Open-Meteo model data (CAMS air quality), not CPCB ground stations; CO is converted from
µg/m³ to mg/m³; wind is requested in m/s; results are cached for 10 minutes per location; the server needs
outbound internet access to `air-quality-api.open-meteo.com` and `api.open-meteo.com`.
`POST /api/forecast/` also accepts `{"state": "Goa"}` and fetches the 24 hours itself.
Open-Meteo's free tier is for non-commercial use; check their terms before deploying commercially.

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
