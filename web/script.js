// SmartHVAC Studio — Direct Tunnel Architecture
// Connects directly to Google Colab via Ngrok/FastAPI

// ----------------------------
// Backend URL Management
// ----------------------------
function getBackendUrl() {
  let url = localStorage.getItem("smarthvac_backend_url");
  if (!url) {
    url = "http://127.0.0.1:8000"; // Default fallback
  }
  // ensure no trailing slash
  return url.replace(/\/$/, "");
}

function setBackendUrl(url) {
  localStorage.setItem("smarthvac_backend_url", url);
  console.log("[Backend] URL updated to:", url);
}

// ----------------------------
// Weather Index (Global)
// ----------------------------
let weatherIndex = []; 

function loadWeatherIndex() {
  fetch('../data/weather_index.json')
    .then(res => res.json())
    .then(data => {
      weatherIndex = data;
      console.log(`[Weather] Loaded ${data.length} stations.`);
      populateWeatherDatalist();
    })
    .catch(err => console.warn('[Weather] Could not load index:', err));
}

function populateWeatherDatalist() {
  const datalist = document.getElementById('weatherDatalist');
  if (!datalist) return;
  datalist.innerHTML = '';
  weatherIndex.forEach(entry => {
    const opt = document.createElement('option');
    opt.value = entry.title;
    datalist.appendChild(opt);
  });

  const searchInput = document.getElementById('weatherSearch');
  if (searchInput) {
    searchInput.addEventListener('change', () => {
      const selected = weatherIndex.find(e => e.title === searchInput.value);
      const hiddenUrl = document.getElementById('weatherEpwUrl');
      if (selected && hiddenUrl) {
        hiddenUrl.value = selected.epw_url;
      } else if (hiddenUrl) {
        hiddenUrl.value = ''; 
      }
    });
  }
}

// ----------------------------
// Connection Testing
// ----------------------------
function testBackendConnection(silent = false) {
  const url = getBackendUrl();
  const statusMsg = document.getElementById("statusMsg");
  
  if (!silent && statusMsg) {
    statusMsg.innerText = "Checking connection...";
    statusMsg.style.color = "blue";
  }

  fetch(`${url}/api/ping`, {
    headers: { 'ngrok-skip-browser-warning': 'true' }
  })
    .then(res => {
      if(!res.ok) throw new Error("Network response was not ok");
      return res.json();
    })
    .then(data => {
      if (!silent) {
        if(statusMsg) {
          statusMsg.innerText = "Connection successful! " + data.message;
          statusMsg.style.color = "green";
        } else {
          alert("Connection successful! " + data.message);
        }
      }
    })
    .catch(err => {
      console.error("Backend connection error:", err);
      if (!silent) {
        if(statusMsg) {
          statusMsg.innerText = "Connection failed. Please check your Backend URL.";
          statusMsg.style.color = "red";
        } else {
          alert("Connection failed. Please check your Backend URL.");
        }
      }
    });
}

function toggleSidebar() {
  const container = document.querySelector('.dashboard-container');
  const sidebar = document.querySelector('.sidebar');
  if (container && sidebar) {
    container.classList.toggle('sidebar-collapsed');
    sidebar.classList.toggle('collapsed');
  }
}

// ----------------------------
// Local Job Management
// ----------------------------
function getLocalJobs() {
  const jobs = localStorage.getItem("smarthvac_jobs");
  return jobs ? JSON.parse(jobs) : [];
}

function saveLocalJob(jobData) {
  let jobs = getLocalJobs();
  // Update if exists, else prepend
  const idx = jobs.findIndex(j => j.id === jobData.id);
  if (idx >= 0) {
    jobs[idx] = jobData;
  } else {
    jobs.unshift(jobData); // newest first
  }
  localStorage.setItem("smarthvac_jobs", JSON.stringify(jobs));
}

// ----------------------------
// Create a new Job (POST)
// ----------------------------
function submitDescription() {
  const input = document.getElementById("description");
  if (!input || input.value.trim() === "") {
    alert("Please enter a description.");
    return;
  }

  const backendUrl = getBackendUrl();
  const statusMsg = document.getElementById("statusMsg");

  if(statusMsg) {
    statusMsg.innerText = "Submitting job...";
    statusMsg.style.color = "blue";
  }

  const payload = {
    prompt: input.value,
    settings: {
      ...JSON.parse(localStorage.getItem("smartHVAC_config") || "{}"),
      run_type: document.getElementById("simType") ? document.getElementById("simType").value : "design_day",
      weather_file: "USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw", 
      epw_url: document.getElementById("weatherEpwUrl") ? document.getElementById("weatherEpwUrl").value : "",
      model_type: document.getElementById("aiModel") ? document.getElementById("aiModel").value : "ollama"
    }
  };

  fetch(`${backendUrl}/api/simulate`, {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'ngrok-skip-browser-warning': 'true'
    },
    body: JSON.stringify(payload)
  })
  .then(res => {
    if(!res.ok) throw new Error("Failed to submit job.");
    return res.json();
  })
  .then(data => {
    const jobId = data.job_id;
    if(statusMsg) {
      statusMsg.innerText = `Job submitted! ID: ${jobId}. Simulation running...`;
      statusMsg.style.color = "orange";
    }
    
    input.value = "";
    
    // Save to local list
    const jobData = {
      id: jobId,
      status: "running",
      prompt: payload.prompt,
      createdAt: new Date().getTime()
    };
    saveLocalJob(jobData);
    if (typeof loadJobs === "function") loadJobs();

    // Start polling for this job
    startPolling(jobId);
  })
  .catch(err => {
    if(statusMsg) {
      statusMsg.innerText = "Error: " + err.message;
      statusMsg.style.color = "red";
    }
  });
}

// ----------------------------
// Status Polling
// ----------------------------
const activePolls = {};

function startPolling(jobId) {
  if (activePolls[jobId]) return;

  const backendUrl = getBackendUrl();
  
  activePolls[jobId] = setInterval(() => {
    fetch(`${backendUrl}/api/status/${jobId}`, {
      headers: { 'ngrok-skip-browser-warning': 'true' }
    })
      .then(res => res.json())
      .then(data => {
        if (data.status === "done" || data.status === "error") {
          clearInterval(activePolls[jobId]);
          delete activePolls[jobId];
          
          // Update local storage
          const jobData = {
            id: jobId,
            status: data.status,
            prompt: data.prompt,
            createdAt: data.created_at * 1000,
            result: data.result,
            error_message: data.error_message
          };
          saveLocalJob(jobData);
          if (typeof loadJobs === "function") loadJobs();
          
          const statusMsg = document.getElementById("statusMsg");
          if(statusMsg) {
            statusMsg.innerText = data.status === "done" ? "Simulation Complete!" : "Simulation Failed.";
            statusMsg.style.color = data.status === "done" ? "green" : "red";
          }
        }
      })
      .catch(err => console.error(`[Polling] Error for ${jobId}:`, err));
  }, 3000); // Poll every 3 seconds
}

// ----------------------------
// Load all Jobs (UI)
// ----------------------------
function loadJobs() {
  const tableBody = document.getElementById("runsTable");
  if (!tableBody) return;

  tableBody.innerHTML = "";
  const jobs = getLocalJobs().slice(0, 5); // Show last 5

  jobs.forEach(data => {
    const row = document.createElement("tr");

    let statusColor = "black";
    if (data.status === "running") statusColor = "orange";
    if (data.status === "done") statusColor = "green";
    if (data.status === "error") statusColor = "red";

    const dateStr = new Date(data.createdAt).toLocaleString();

    row.innerHTML = `
      <td style="padding: 0.75rem; border-bottom: 1px solid var(--border-subtle);">${data.prompt ? data.prompt.substring(0, 40) + "..." : "No description"}</td>
      <td style="padding: 0.75rem; border-bottom: 1px solid var(--border-subtle); color: ${statusColor}; font-weight: bold;">${data.status}</td>
      <td style="padding: 0.75rem; border-bottom: 1px solid var(--border-subtle); color: var(--text-secondary); font-size: 0.85rem;">${dateStr}</td>
    `;

    row.onclick = () => showJobDetails(data.id, data);
    row.style.cursor = "pointer";
    row.onmouseover = () => row.style.backgroundColor = "var(--bg-app)";
    row.onmouseout = () => row.style.backgroundColor = "transparent";

    tableBody.appendChild(row);

    // If job is still running, make sure we are polling it
    if (data.status === "running") {
      startPolling(data.id);
    }
  });
}

// ----------------------------
// Show Job Details & Results
// ----------------------------
function showJobDetails(jobId, data) {
  const placeholder = document.getElementById("detailPlaceholder");
  const content = document.getElementById("detailContent");
  if (placeholder) placeholder.style.display = 'none';
  if (content) content.style.display = 'grid';

  const elDesc = document.getElementById("detailDescription");
  const elStatus = document.getElementById("detailStatus");
  const elTime = document.getElementById("detailTime");

  if (elDesc) elDesc.innerText = data.prompt;
  if (elStatus) {
    elStatus.innerText = data.status;
    if (data.status === "running") elStatus.style.color = "var(--warning)";
    else if (data.status === "done") elStatus.style.color = "var(--success)";
    else if (data.status === "error") elStatus.style.color = "var(--error)";
  }
  if (elTime) elTime.innerText = new Date(data.createdAt).toLocaleString();

  // Handle Buttons
  const actionContainer = document.getElementById("actionButtonsContainer");
  const btnView = document.getElementById("btnViewIDF");
  const btnSummary = document.getElementById("btnViewIDFSummary");
  const btn3D = document.getElementById("btnView3D");
  
  if (actionContainer && btnView && btnSummary) {
    if (data.status === "done" && data.result) {
      actionContainer.style.display = "flex";
      btnView.onclick = () => {
         const w = window.open();
         w.document.write(`<pre>${data.result.idf.replace(/</g, "&lt;")}</pre>`);
      };
      btnSummary.onclick = () => {
         if (data.result.files && data.result.files.summary) {
             window.open(getBackendUrl() + data.result.files.summary, "_blank");
         } else {
             alert("Summary not available.");
         }
      };
      if (btn3D) {
        btn3D.onclick = () => {
           if (data.result.files && data.result.files.geometry) {
               window.open(getBackendUrl() + data.result.files.geometry, "_blank");
           } else {
               alert("3D Geometry not available.");
           }
        };
      }
    } else {
      actionContainer.style.display = "none";
    }
  }

  // Handle Results Visualization
  const plots = [
    { key: "plot", imgId: "zonePlot", msgId: "zonePlotMsg", fallbackText: "Zone Temperature" },
    { key: "plot_ekf", imgId: "ekfPlot", msgId: "ekfPlotMsg", fallbackText: "Mass Flow Rate" },
    { key: "plot_weather", imgId: "weatherPlot", msgId: "weatherPlotMsg", fallbackText: "Weather Data" },
    { key: "plot_energy", imgId: "energyPlot", msgId: "energyPlotMsg", fallbackText: "Energy Consumption" }
  ];

  plots.forEach(plotDef => {
    const imgInfo = document.getElementById(plotDef.imgId);
    const msgInfo = document.getElementById(plotDef.msgId);
    if (!imgInfo || !msgInfo) return;

    if (data.status === "done" && data.result && data.result.files) {
      const plotPath = data.result.files[plotDef.key];
      if (plotPath) {
        imgInfo.src = getBackendUrl() + plotPath;
        msgInfo.innerText = "";
        imgInfo.style.display = "block";
      } else {
        imgInfo.style.display = "none";
        msgInfo.innerText = `${plotDef.fallbackText} not available.`;
      }
    } else if (data.status === "error") {
      imgInfo.style.display = "none";
      msgInfo.innerText = data.error_message || "Job failed.";
      msgInfo.style.color = "var(--error)";
    } else {
      imgInfo.style.display = "none";
      msgInfo.innerText = "Simulation in progress...";
      msgInfo.style.color = "var(--text-secondary)";
    }
  });

  // Multi-zone chart
  if (data.status === "done" && data.result && data.result.csv_data) {
    loadAndPlotZoneTemperatures(data.result.csv_data);
  }
}

// ----------------------------
// Multi-Zone Temperature Chart
// ----------------------------
const ZONE_CHART_COLORS = [
  'rgba(54,  162, 235, 1)', 'rgba(255, 159,  64, 1)', 'rgba( 75, 192, 100, 1)',
  'rgba(255,  99, 132, 1)', 'rgba(153, 102, 255, 1)', 'rgba(255, 205,  86, 1)'
];

let _multiZoneChart = null;

function loadAndPlotZoneTemperatures(csvText) {
  const container = document.getElementById('multiZoneChartContainer');
  if (!csvText) return;

  const rows = csvText.trim().split('\n').map(r => r.split(','));
  if (rows.length < 2) return;

  const headers = rows[0].map(h => h.trim().replace(/"/g, ''));
  const timeCol = 0;
  
  const tempCols = [];
  headers.forEach((h, idx) => {
    if (h.toLowerCase().includes('zone air temperature')) {
      tempCols.push({ idx, label: h });
    }
  });

  if (tempCols.length === 0) {
    if (container) container.style.display = 'none';
    return;
  }

  const timeLabels = rows.slice(1).map(r => r[timeCol] ? r[timeCol].trim() : '');
  const datasets = tempCols.map((col, ci) => ({
    label: col.label,
    data: rows.slice(1).map(r => parseFloat(r[col.idx]) || null),
    borderColor: ZONE_CHART_COLORS[ci % ZONE_CHART_COLORS.length],
    backgroundColor: ZONE_CHART_COLORS[ci % ZONE_CHART_COLORS.length].replace(', 1)', ', 0.08)'),
    borderWidth: 2,
    pointRadius: 0,
    tension: 0.3,
    fill: false,
  }));

  if (!container) return;
  container.style.display = 'block';
  container.innerHTML = `
    <div style="padding: 0.75rem 0 0.5rem;">
      <h4 style="margin:0 0 0.5rem; color:var(--text-primary); font-size:0.95rem;">
        🌡️ Zone Air Temperature Comparison
      </h4>
      <canvas id="multiZoneCanvas" style="max-height:320px;"></canvas>
    </div>`;

  const ctx = document.getElementById('multiZoneCanvas').getContext('2d');
  if (_multiZoneChart) {
    _multiZoneChart.destroy();
    _multiZoneChart = null;
  }

  const renderChart = () => {
    _multiZoneChart = new Chart(ctx, {
      type: 'line',
      data: { labels: timeLabels, datasets },
      options: {
        responsive: true,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { position: 'top', labels: { boxWidth: 12, font: { size: 11 } } }
        },
        scales: {
          x: { ticks: { maxRotation: 45, maxTicksLimit: 12 }, title: { display: true, text: 'Time' } },
          y: { title: { display: true, text: 'Temperature (°C)' } }
        }
      }
    });
  };

  if (typeof Chart !== 'undefined') {
    renderChart();
  } else {
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js';
    script.onload = renderChart;
    document.head.appendChild(script);
  }
}

// ----------------------------
// Auto-Init on Page Load
// ----------------------------
window.addEventListener("load", () => {
  if (document.getElementById("runsTable")) {
    loadJobs();
  }
  if (document.getElementById("weatherSearch")) {
    loadWeatherIndex();
  }
  
  // Inject backend URL input into the header if it doesn't exist
  if (!document.getElementById("backendUrlInput")) {
      const header = document.querySelector(".page-header");
      if (header) {
          const div = document.createElement("div");
          div.style = "margin-top: 10px; display: flex; gap: 10px; align-items: center;";
          div.innerHTML = `
            <label style="font-weight: bold; color: var(--text-secondary);">Backend URL:</label>
            <input type="text" id="backendUrlInput" value="${getBackendUrl()}" style="padding: 5px; border-radius: 4px; border: 1px solid #ccc; width: 300px;" placeholder="https://xyz.ngrok-free.app">
            <button onclick="setBackendUrl(document.getElementById('backendUrlInput').value); testBackendConnection()" style="padding: 5px 10px; border-radius: 4px; cursor:pointer; background: var(--primary); color: white; border: none;">Connect</button>
            <span id="statusMsg" style="font-size: 0.9em; font-weight: bold; margin-left: 10px;"></span>
          `;
          header.appendChild(div);
      }
  }
});

window.submitDescription = submitDescription;
window.loadRuns = loadJobs;
window.toggleSidebar = toggleSidebar;
window.testBackendConnection = testBackendConnection;
window.setBackendUrl = setBackendUrl;
