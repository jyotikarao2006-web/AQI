"""Shared constants: input fields, Indian (CPCB) AQI bands, city presets and Indian states."""

# name must match the training column names exactly.
FIELDS = [
    {"name": "PM2.5", "label": "PM2.5", "unit": "µg/m³", "default": 85, "min": 0, "max": 2000, "step": 1},
    {"name": "PM10", "label": "PM10", "unit": "µg/m³", "default": 160, "min": 0, "max": 4000, "step": 1},
    {"name": "NO2", "label": "Nitrogen dioxide", "unit": "µg/m³", "default": 40, "min": 0, "max": 800, "step": 1},
    {"name": "SO2", "label": "Sulphur dioxide", "unit": "µg/m³", "default": 12, "min": 0, "max": 100, "step": 1},
    {"name": "CO", "label": "Carbon monoxide", "unit": "mg/m³", "default": 1.2, "min": 0, "max": 35, "step": 0.1},
    {"name": "O3", "label": "Ozone", "unit": "µg/m³", "default": 45, "min": 0, "max": 250, "step": 1},
    {"name": "Temperature", "label": "Temperature", "unit": "°C", "default": 30, "min": -30, "max": 55, "step": 0.5},
    {"name": "Humidity", "label": "Humidity", "unit": "%", "default": 60, "min": 0, "max": 100, "step": 1},
    {"name": "WindSpeed", "label": "Wind speed", "unit": "m/s", "default": 3, "min": 0, "max": 40, "step": 0.1},
    {"name": "Rainfall", "label": "Rainfall", "unit": "mm", "default": 0, "min": 0, "max": 300, "step": 0.5},
]
FEATURES = [f["name"] for f in FIELDS]
RANGES = {f["name"]: (f["min"], f["max"]) for f in FIELDS}
LSTM_FEATURES = ["Latitude", "Longitude"] + FEATURES  # order the scaler was fitted on
RANGES["Latitude"] = (5, 40)
RANGES["Longitude"] = (65, 100)

# CPCB National Air Quality Index bands.
BANDS = [
    {"min": 0, "max": 50, "name": "Good", "color": "#00965E",
     "advice": "Air is clean. Enjoy time outdoors."},
    {"min": 50, "max": 100, "name": "Satisfactory", "color": "#8DB600",
     "advice": "Fine for most people. Unusually sensitive people may notice mild discomfort."},
    {"min": 100, "max": 200, "name": "Moderate", "color": "#E8B400",
     "advice": "People with asthma, heart or lung conditions may feel breathing discomfort. Go easy on long outdoor exercise."},
    {"min": 200, "max": 300, "name": "Poor", "color": "#E8801C",
     "advice": "Prolonged exposure can cause discomfort for most people. Shorten outdoor activity and consider a mask."},
    {"min": 300, "max": 400, "name": "Very poor", "color": "#D2382E",
     "advice": "Breathing illness is likely on long exposure. Avoid outdoor exertion; keep windows closed."},
    {"min": 400, "max": 500, "name": "Severe", "color": "#7B1230",
     "advice": "Affects everyone and seriously affects people with existing illness. Stay indoors."},
]

CITIES = [
    {"name": "Mumbai", "lat": 19.076, "lon": 72.878},
    {"name": "Delhi", "lat": 28.614, "lon": 77.209},
    {"name": "Bengaluru", "lat": 12.972, "lon": 77.595},
    {"name": "Kolkata", "lat": 22.573, "lon": 88.364},
    {"name": "Chennai", "lat": 13.083, "lon": 80.271},
    {"name": "Hyderabad", "lat": 17.385, "lon": 78.487},
    {"name": "Pune", "lat": 18.520, "lon": 73.857},
    {"name": "Ahmedabad", "lat": 23.023, "lon": 72.572},
]

# Indian states and union territories, located at their capital. Used to fetch live data
# from Open-Meteo. Sorted A-Z; the UI lets the user pick one.
STATES = [
    {"name": "Andaman and Nicobar Islands", "capital": "Port Blair", "lat": 11.623, "lon": 92.727},
    {"name": "Andhra Pradesh", "capital": "Amaravati", "lat": 16.573, "lon": 80.358},
    {"name": "Arunachal Pradesh", "capital": "Itanagar", "lat": 27.084, "lon": 93.605},
    {"name": "Assam", "capital": "Dispur", "lat": 26.144, "lon": 91.790},
    {"name": "Bihar", "capital": "Patna", "lat": 25.594, "lon": 85.138},
    {"name": "Chandigarh", "capital": "Chandigarh", "lat": 30.733, "lon": 76.779},
    {"name": "Chhattisgarh", "capital": "Raipur", "lat": 21.251, "lon": 81.630},
    {"name": "Dadra and Nagar Haveli and Daman and Diu", "capital": "Daman", "lat": 20.397, "lon": 72.832},
    {"name": "Delhi", "capital": "New Delhi", "lat": 28.614, "lon": 77.209},
    {"name": "Goa", "capital": "Panaji", "lat": 15.490, "lon": 73.828},
    {"name": "Gujarat", "capital": "Gandhinagar", "lat": 23.215, "lon": 72.637},
    {"name": "Haryana", "capital": "Chandigarh", "lat": 30.733, "lon": 76.779},
    {"name": "Himachal Pradesh", "capital": "Shimla", "lat": 31.105, "lon": 77.173},
    {"name": "Jammu and Kashmir", "capital": "Srinagar", "lat": 34.084, "lon": 74.797},
    {"name": "Jharkhand", "capital": "Ranchi", "lat": 23.344, "lon": 85.310},
    {"name": "Karnataka", "capital": "Bengaluru", "lat": 12.972, "lon": 77.595},
    {"name": "Kerala", "capital": "Thiruvananthapuram", "lat": 8.524, "lon": 76.936},
    {"name": "Ladakh", "capital": "Leh", "lat": 34.153, "lon": 77.577},
    {"name": "Lakshadweep", "capital": "Kavaratti", "lat": 10.567, "lon": 72.642},
    {"name": "Madhya Pradesh", "capital": "Bhopal", "lat": 23.260, "lon": 77.413},
    {"name": "Maharashtra", "capital": "Mumbai", "lat": 19.076, "lon": 72.878},
    {"name": "Manipur", "capital": "Imphal", "lat": 24.817, "lon": 93.937},
    {"name": "Meghalaya", "capital": "Shillong", "lat": 25.578, "lon": 91.893},
    {"name": "Mizoram", "capital": "Aizawl", "lat": 23.727, "lon": 92.718},
    {"name": "Nagaland", "capital": "Kohima", "lat": 25.667, "lon": 94.108},
    {"name": "Odisha", "capital": "Bhubaneswar", "lat": 20.296, "lon": 85.825},
    {"name": "Puducherry", "capital": "Puducherry", "lat": 11.934, "lon": 79.830},
    {"name": "Punjab", "capital": "Chandigarh", "lat": 30.733, "lon": 76.779},
    {"name": "Rajasthan", "capital": "Jaipur", "lat": 26.912, "lon": 75.787},
    {"name": "Sikkim", "capital": "Gangtok", "lat": 27.339, "lon": 88.610},
    {"name": "Tamil Nadu", "capital": "Chennai", "lat": 13.083, "lon": 80.271},
    {"name": "Telangana", "capital": "Hyderabad", "lat": 17.385, "lon": 78.487},
    {"name": "Tripura", "capital": "Agartala", "lat": 23.831, "lon": 91.286},
    {"name": "Uttar Pradesh", "capital": "Lucknow", "lat": 26.847, "lon": 80.947},
    {"name": "Uttarakhand", "capital": "Dehradun", "lat": 30.317, "lon": 78.032},
    {"name": "West Bengal", "capital": "Kolkata", "lat": 22.573, "lon": 88.364},
]
STATES_BY_NAME = {s["name"].lower(): s for s in STATES}


def band_for(aqi: float) -> dict:
    aqi = max(0.0, min(float(aqi), 500.0))
    for b in BANDS:
        if aqi <= b["max"]:
            return b
    return BANDS[-1]
