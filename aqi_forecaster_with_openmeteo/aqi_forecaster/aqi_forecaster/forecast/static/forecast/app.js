(() => {
  const cfg = JSON.parse(document.getElementById("config").textContent);
  const { fields: FIELDS, bands: BANDS, states: STATES } = cfg;
  const $ = (s) => document.querySelector(s);

  const PRESETS = {
    monsoon: { "PM2.5": 18, PM10: 40, NO2: 15, SO2: 6, CO: 0.6, O3: 30, Temperature: 27, Humidity: 90, WindSpeed: 6, Rainfall: 25 },
    typical: Object.fromEntries(FIELDS.map((f) => [f.name, f.default])),
    smog:    { "PM2.5": 260, PM10: 420, NO2: 80, SO2: 20, CO: 3.5, O3: 25, Temperature: 12, Humidity: 70, WindSpeed: 1, Rainfall: 0 },
  };

  const csrf = () => (document.cookie.split("; ").find((c) => c.startsWith("csrftoken=")) || "").split("=")[1];
  async function api(path, body) {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `Request failed (${res.status}).`);
    return data;
  }
  async function getJSON(path) {
    const res = await fetch(path, { headers: { Accept: "application/json" } });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `Request failed (${res.status}).`);
    return data;
  }

  // ---- state ----------------------------------------------------------
  const stateSel = $("#state");
  STATES.forEach((s, i) => stateSel.add(new Option(s.name, i)));
  stateSel.value = STATES.findIndex((s) => s.name === "Delhi");
  const state = () => STATES[stateSel.value];

  // ---- condition fields ------------------------------------------------
  const fieldsEl = $("#fields");
  FIELDS.forEach((f) => {
    fieldsEl.insertAdjacentHTML("beforeend",
      `<label class="field"><span class="fl">${f.label}</span><span class="in">
        <input type="number" name="${f.name}" value="${f.default}" min="${f.min}" max="${f.max}" step="${f.step}" inputmode="decimal" required>
        <em>${f.unit}</em></span></label>`);
  });
  const input = (name) => fieldsEl.querySelector(`input[name="${name}"]`);
  const readForm = () => Object.fromEntries(FIELDS.map((f) => [f.name, input(f.name).value]));

  // ---- ruler -----------------------------------------------------------
  const bar = $("#bar"), names = $("#bandNames"), marker = $("#marker");
  BANDS.forEach((b) => {
    const w = b.max - b.min;
    bar.insertAdjacentHTML("beforeend", `<i style="flex:${w};background:${b.color}"></i>`);
    names.insertAdjacentHTML("beforeend", `<span style="flex:${w}" title="${b.min}–${b.max}">${b.name}</span>`);
  });
  const errEl = $("#error");
  function showResult(r) {
    errEl.hidden = true;
    marker.style.left = `${(Math.min(r.aqi, 500) / 500) * 100}%`;
    $("#aqiNum").textContent = r.aqi;
    $("#catName").textContent = r.category;
    $("#advice").textContent = r.advice;
    document.documentElement.style.setProperty("--cat", r.color);
  }
  function showError(msg) { errEl.textContent = msg; errEl.hidden = false; $("#catName").textContent = "Unavailable"; }

  // ---- live prediction (XGBoost) ---------------------------------------
  let seq = 0, timer;
  async function predict() {
    const mine = ++seq;
    try {
      const r = await api("/api/predict/", readForm());
      if (mine === seq) showResult(r);
    } catch (e) {
      if (mine === seq) showError("Could not get a prediction: " + e.message);
    }
  }
  fieldsEl.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(predict, 350);
    $("#liveStatus").textContent = "Conditions edited by hand.";
  });
  document.querySelectorAll("[data-preset]").forEach((b) =>
    b.addEventListener("click", () => {
      Object.entries(PRESETS[b.dataset.preset]).forEach(([k, v]) => (input(k).value = v));
      $("#liveStatus").textContent = "Example conditions.";
      predict();
    }));

  // ---- last 24 hours from Open-Meteo -----------------------------------
  let live = null;        // { state, rows, ... } from /api/live/
  let liveChart, liveSeq = 0;
  const bandOf = (aqi) => BANDS.find((b) => aqi <= b.max) || BANDS[BANDS.length - 1];
  const hourLabel = (iso) => {
    const d = new Date(iso);
    return d.toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", hour12: true });
  };
  const liveErr = $("#liveError"), refreshBtn = $("#refreshLive");

  function renderLive(d) {
    $("#liveResult").hidden = false;
    $("#liveMeta").textContent =
      `${d.state} (${d.location}), ${hourLabel(d.from)} to ${hourLabel(d.to)}, India time. ` +
      `Source: ${d.source}.`;

    const cols = FIELDS.map((f) => f.name);
    $("#liveTable").innerHTML =
      `<thead><tr><th>Hour</th><th>Est. AQI</th>${FIELDS.map((f) => `<th>${f.label}<br><small>${f.unit}</small></th>`).join("")}</tr></thead><tbody>${
        [...d.rows].reverse().map((r) => {
          const color = r.aqi == null ? "" : bandOf(r.aqi).color;
          return `<tr><td>${hourLabel(r.time)}</td><td><span class="dot" style="--c:${color}"></span>${r.aqi ?? "–"}</td>${
            cols.map((c) => `<td>${r[c]}</td>`).join("")}</tr>`;
        }).join("")
      }</tbody>`;

    if (liveChart) liveChart.destroy();
    const hasAqi = d.rows.every((r) => r.aqi != null);
    const key = hasAqi ? "aqi" : "PM2.5";
    liveChart = new Chart($("#liveChart"), {
      type: "line",
      data: {
        labels: d.rows.map((r) => new Date(r.time).toLocaleTimeString("en-IN", { hour: "numeric", hour12: true })),
        datasets: [{
          label: hasAqi ? "Estimated AQI" : "PM2.5 (µg/m³)",
          data: d.rows.map((r) => r[key]), borderColor: "#1B2A33", borderWidth: 2, tension: 0.3, pointRadius: 4,
          pointBackgroundColor: d.rows.map((r) => (hasAqi ? bandOf(r.aqi).color : "#1B2A33")),
          pointBorderColor: "#1B2A33",
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false },
          tooltip: { callbacks: { title: (c) => hourLabel(d.rows[c[0].dataIndex].time) } } },
        scales: { y: { beginAtZero: true, grid: { display: false } }, x: { grid: { display: false } } },
      },
      plugins: hasAqi ? [bandPlugin] : [],
    });
  }

  async function loadLive() {
    const mine = ++liveSeq;
    const s = state();
    liveErr.hidden = true;
    refreshBtn.disabled = true;
    $("#liveStatus").textContent = `Loading the last 24 hours for ${s.name}…`;
    try {
      const d = await getJSON(`/api/live/?state=${encodeURIComponent(s.name)}`);
      if (mine !== liveSeq) return;
      live = d;
      // newest hour -> Conditions form -> big AQI reading
      Object.entries(d.latest).forEach(([k, v]) => { if (input(k)) input(k).value = v; });
      $("#liveStatus").textContent =
        `Live: ${d.state} (${d.location}), latest hour ${hourLabel(d.to)}. Edit any value to explore "what if".`;
      renderLive(d);
      predict();
    } catch (e) {
      if (mine !== liveSeq) return;
      live = null;
      liveErr.textContent = e.message;
      liveErr.hidden = false;
      $("#liveResult").hidden = true;
      $("#liveStatus").textContent = `Could not load live data for ${s.name}.`;
    } finally {
      if (mine === liveSeq) refreshBtn.disabled = false;
    }
  }
  stateSel.addEventListener("change", loadLive);
  refreshBtn.addEventListener("click", loadLive);

  // ---- history source ---------------------------------------------------
  const csvBox = $("#csvBox"), csvFile = $("#csvFile");
  const srcValue = () => document.querySelector('input[name="src"]:checked').value;
  document.querySelectorAll('input[name="src"]').forEach((r) =>
    r.addEventListener("change", () => (csvBox.hidden = srcValue() !== "csv")));
  function parseCSV(text) {
    const lines = text.replace(/^﻿/, "").trim().split(/\r?\n/).filter(Boolean);
    const head = lines[0].split(",").map((s) => s.trim());
    return lines.slice(1).map((l) => {
      const cells = l.split(",");
      return Object.fromEntries(head.map((h, i) => [h, (cells[i] || "").trim()]));
    });
  }
  $("#csvTemplate").addEventListener("click", () => {
    const s = state(), cols = ["Latitude", "Longitude", ...FIELDS.map((f) => f.name)];
    const row = [s.lat, s.lon, ...FIELDS.map((f) => input(f.name).value)].join(",");
    const csv = [cols.join(","), ...Array(24).fill(row)].join("\n");
    const a = Object.assign(document.createElement("a"), {
      href: URL.createObjectURL(new Blob([csv], { type: "text/csv" })), download: "aqi_last_24_readings.csv",
    });
    a.click(); URL.revokeObjectURL(a.href);
  });

  // ---- 7-day forecast (LSTM) --------------------------------------------
  let chart;
  const bandPlugin = {
    id: "bands",
    beforeDraw(c) {
      const { ctx, chartArea: a, scales: { y } } = c;
      BANDS.forEach((b) => {
        if (b.min >= y.max || b.max <= y.min) return;
        const top = y.getPixelForValue(Math.min(b.max, y.max));
        const bottom = y.getPixelForValue(Math.max(b.min, y.min));
        ctx.fillStyle = b.color + "2B";
        ctx.fillRect(a.left, top, a.right - a.left, bottom - top);
      });
    },
  };
  const dayLabel = (iso) => new Date(iso + "T00:00:00").toLocaleDateString("en-IN", { weekday: "short", day: "numeric" });

  function renderWeek(r) {
    $("#weekEmpty").hidden = true;
    $("#weekResult").hidden = false;
    const { label, slope } = r.trend;
    $("#trend").textContent = label === "stable"
      ? "Air quality looks steady through the week."
      : `Air quality is likely to ${label === "rising" ? "worsen" : "improve"}, by about ${Math.abs(slope)} AQI points a day.`;

    const noteEl = $("#scaleNote");
    noteEl.textContent = r.note || "";
    noteEl.hidden = !r.note;

    $("#days").innerHTML = r.days.map((d) =>
      `<li style="--c:${d.color}"><span class="d">${dayLabel(d.date)}</span><span class="n">${d.aqi}</span><span class="c">${d.category}</span></li>`).join("");

    if (chart) chart.destroy();
    chart = new Chart($("#chart"), {
      type: "line",
      data: {
        labels: r.days.map((d) => dayLabel(d.date)),
        datasets: [{
          data: r.days.map((d) => d.aqi), borderColor: "#1B2A33", borderWidth: 2, tension: 0.3,
          pointRadius: 7, pointBackgroundColor: r.days.map((d) => d.color), pointBorderColor: "#1B2A33", pointBorderWidth: 2,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false },
          tooltip: { callbacks: { label: (c) => `AQI ${c.parsed.y}, ${r.days[c.dataIndex].category}` } } },
        scales: { y: { beginAtZero: true, grid: { display: false } }, x: { grid: { display: false } } },
      },
      plugins: [bandPlugin],
    });
  }

  const goBtn = $("#goForecast");
  goBtn.addEventListener("click", async () => {
    goBtn.disabled = true;
    goBtn.textContent = "Forecasting…";
    try {
      const s = state();
      const body = { Latitude: s.lat, Longitude: s.lon, state: s.name, conditions: readForm() };
      const src = srcValue();
      if (src === "csv") {
        if (!csvFile.files[0]) throw new Error("Choose a CSV file with your last 24 readings.");
        body.history = parseCSV(await csvFile.files[0].text());
      } else if (src === "live") {
        if (!live || live.state !== s.name) await loadLive();
        if (!live) throw new Error("Live data for this state is not available right now. Pick “Hold the conditions above steady” or try again.");
        body.history = live.rows;
      } else {
        delete body.state; // steady: do not let the server fetch history
      }
      $("#weekError").hidden = true;
      renderWeek(await api("/api/forecast/", body));
    } catch (e) {
      const w = $("#weekError");
      w.textContent = e.message;
      w.hidden = false;
      $("#weekResult").hidden = true;
    } finally {
      goBtn.disabled = false;
      goBtn.textContent = "Forecast the week";
    }
  });

  loadLive();
})();
