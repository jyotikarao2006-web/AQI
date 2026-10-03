(() => {
  const cfg = JSON.parse(document.getElementById("config").textContent);
  const { fields: FIELDS, bands: BANDS, cities: CITIES } = cfg;
  const $ = (s) => document.querySelector(s);

  const PRESETS = {
    monsoon: { "PM2.5": 18, PM10: 40, NO2: 15, SO2: 6, CO: 0.6, O3: 30, Temperature: 27, Humidity: 90, WindSpeed: 6, Rainfall: 25 },
    typical: Object.fromEntries(FIELDS.map((f) => [f.name, f.default])),
    smog:    { "PM2.5": 260, PM10: 420, NO2: 80, SO2: 20, CO: 3.5, O3: 25, Temperature: 12, Humidity: 70, WindSpeed: 1, Rainfall: 0 },
  };
  const OUTLOOK_FIELDS = ["Temperature", "Humidity", "WindSpeed", "Rainfall"];

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

  // ---- city -----------------------------------------------------------
  const citySel = $("#city");
  CITIES.forEach((c, i) => citySel.add(new Option(c.name, i)));
  const city = () => CITIES[citySel.value];

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
  fieldsEl.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(predict, 350); });
  document.querySelectorAll("[data-preset]").forEach((b) =>
    b.addEventListener("click", () => {
      Object.entries(PRESETS[b.dataset.preset]).forEach(([k, v]) => (input(k).value = v));
      predict();
    }));

  // ---- weather outlook table -------------------------------------------
  const table = $("#outlookTable");
  const labelOf = (n) => FIELDS.find((f) => f.name === n);
  table.innerHTML = `<thead><tr><th>Day</th>${OUTLOOK_FIELDS.map((n) => `<th>${labelOf(n).label} (${labelOf(n).unit})</th>`).join("")}</tr></thead><tbody>${
    [...Array(7)].map((_, d) => `<tr><th>Day ${d + 1}</th>${OUTLOOK_FIELDS.map((n) =>
      `<td><input type="number" data-day="${d}" data-name="${n}" step="${labelOf(n).step}" aria-label="${labelOf(n).label}, day ${d + 1}"></td>`).join("")}</tr>`).join("")
  }</tbody>`;
  const outlookEl = $("#outlook");
  outlookEl.addEventListener("toggle", () => {
    if (!outlookEl.open) return;
    table.querySelectorAll("input").forEach((i) => { if (i.value === "") i.value = input(i.dataset.name).value; });
  });
  const readOutlook = () => [...Array(7)].map((_, d) => {
    const row = {};
    table.querySelectorAll(`input[data-day="${d}"]`).forEach((i) => { if (i.value !== "") row[i.dataset.name] = i.value; });
    return row;
  });

  // ---- history source ---------------------------------------------------
  const csvBox = $("#csvBox"), csvFile = $("#csvFile");
  document.querySelectorAll('input[name="src"]').forEach((r) =>
    r.addEventListener("change", () => (csvBox.hidden = document.querySelector('input[name="src"]:checked').value !== "csv")));
  function parseCSV(text) {
    const lines = text.replace(/^\uFEFF/, "").trim().split(/\r?\n/).filter(Boolean);
    const head = lines[0].split(",").map((s) => s.trim());
    return lines.slice(1).map((l) => {
      const cells = l.split(",");
      return Object.fromEntries(head.map((h, i) => [h, (cells[i] || "").trim()]));
    });
  }
  $("#csvTemplate").addEventListener("click", () => {
    const c = city(), cols = ["Latitude", "Longitude", ...FIELDS.map((f) => f.name)];
    const row = [c.lat, c.lon, ...FIELDS.map((f) => input(f.name).value)].join(",");
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
      const c = city();
      const body = { Latitude: c.lat, Longitude: c.lon, conditions: readForm() };
      if (document.querySelector('input[name="src"]:checked').value === "csv") {
        if (!csvFile.files[0]) throw new Error("Choose a CSV file with your last 24 readings.");
        body.history = parseCSV(await csvFile.files[0].text());
      }
      if (outlookEl.open) body.outlook = readOutlook();
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

  predict();
})();
