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
  const row = document.getElementById("backendUrlRow");
  
  if (!silent && statusMsg) {
    statusMsg.innerText = "Checking connection...";
    statusMsg.style.color = "blue";
    if (row) row.style.backgroundColor = "transparent";
  }

  fetch(`${url}/api/ping`, {
    headers: { 'ngrok-skip-browser-warning': 'true' }
  })
    .then(res => {
      if(!res.ok) throw new Error("Network response was not ok");
      return res.json();
    })
    .then(data => {
      if (statusMsg) {
        statusMsg.innerText = "Connection successful! " + data.message;
        statusMsg.style.color = "green";
      } else if (!silent) {
        alert("Connection successful! " + data.message);
      }
      if (row) {
        row.style.backgroundColor = "#e6ffe6"; // light green
        row.style.borderColor = "green";
      }
    })
    .catch(err => {
      console.error("Backend connection error:", err);
      if (statusMsg) {
        statusMsg.innerText = "Connection failed. Please check your Backend URL.";
        statusMsg.style.color = "red";
      } else if (!silent) {
        alert("Connection failed. Please check your Backend URL.");
      }
      if (row) {
        row.style.backgroundColor = "#ffe6e6"; // light red
        row.style.borderColor = "red";
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
            
            if (data.status === "error") {
              // Instead of an uncopyable alert, create a copyable div and append it
              const errBox = document.createElement("pre");
              errBox.style.cssText = "color:red; background:#ffe6e6; border:1px solid red; padding:10px; margin-top:10px; font-size:12px; white-space:pre-wrap; max-height:400px; overflow-y:auto; overflow-x:hidden; user-select:text;";
              errBox.innerText = data.error_message;
              statusMsg.parentNode.appendChild(errBox);
              console.error(data.error_message);
            }
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

  // Handle Results Visualization (Frontend Plotly)
  const plotlyZoneTemp = document.getElementById("plotlyZoneTemp");
  const plotlyZoneEnergy = document.getElementById("plotlyZoneEnergy");
  const plotlyAirflow = document.getElementById("plotlyAirflow");
  const plotlyUtility = document.getElementById("plotlyUtility");

  if (data.status === "done" && data.result && data.result.csv_data) {
    renderPlotlyCharts(data.result.csv_data);
  } else if (data.status === "error") {
    if (plotlyZoneTemp) plotlyZoneTemp.innerHTML = `<p style="color:var(--error); padding:2rem;">Simulation failed.</p>`;
    if (plotlyZoneEnergy) plotlyZoneEnergy.innerHTML = "";
    if (plotlyAirflow) plotlyAirflow.innerHTML = "";
    if (plotlyUtility) plotlyUtility.innerHTML = "";
  } else {
    if (plotlyZoneTemp) plotlyZoneTemp.innerHTML = `<p style="color:var(--text-secondary); padding:2rem;">Simulation in progress...</p>`;
    if (plotlyZoneEnergy) plotlyZoneEnergy.innerHTML = "";
    if (plotlyAirflow) plotlyAirflow.innerHTML = "";
    if (plotlyUtility) plotlyUtility.innerHTML = "";
  }
}

// ----------------------------
// Frontend Plotly Render Logic
// ----------------------------
function renderPlotlyCharts(csvText) {
  if (!csvText || !window.Papa || !window.Plotly) {
    console.warn("Plotly or PapaParse not loaded, or CSV empty.");
    return;
  }

  // Parse CSV
  const parsed = Papa.parse(csvText.trim(), { header: true, skipEmptyLines: true });
  if (parsed.errors.length > 0 || parsed.data.length === 0) {
    console.error("PapaParse error or empty data:", parsed.errors);
    return;
  }

  const dataRows = parsed.data;
  const headers = parsed.meta.fields;
  console.log("[Plotly] CSV Headers found:", headers);
  
  // Extract Time array
  const timeCol = headers.find(h => h.toLowerCase().includes("date/time"));
  if (!timeCol) {
    console.error("[Plotly] Could not find Date/Time column! Headers:", headers);
    if (document.getElementById('plotlyZoneTemp')) {
      document.getElementById('plotlyZoneTemp').innerHTML = `<p style="color:var(--error); padding:2rem;">Data error: Date/Time column missing from CSV.</p>`;
    }
    return;
  }
  const timeLabels = dataRows.map(row => row[timeCol].trim());

  // Helper to extract trace data based on keyword
  const createTraces = (keywords, title, yaxisLabel) => {
    const traces = [];
    headers.forEach(h => {
      const lowerH = h.toLowerCase();
      if (keywords.some(kw => lowerH.includes(kw))) {
        // Format name to be readable (remove [C](Hourly) etc)
        let name = h.replace(/\[.*?\]/g, '').replace(/\(Hourly\)/g, '').trim();
        traces.push({
          x: timeLabels,
          y: dataRows.map(row => parseFloat(row[h]) || null),
          type: 'scatter',
          mode: 'lines',
          name: name,
          line: { width: 2 }
        });
      }
    });
    return traces;
  };

  const layoutBase = {
    margin: { t: 40, r: 20, l: 50, b: 60 },
    legend: { orientation: "h", y: -0.2 },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    hovermode: 'x unified',
    font: { family: 'Inter, sans-serif' }
  };

  // Plot 1: Temperatures
  const tempTraces = createTraces(['temperature'], 'Zone Temperatures', 'Temperature (°C)');
  if (tempTraces.length > 0 && document.getElementById('plotlyZoneTemp')) {
    Plotly.newPlot('plotlyZoneTemp', tempTraces, { ...layoutBase, yaxis: { title: 'Temperature (°C)' } }, { responsive: true });
  }

  // Plot 2: Energy (Sensible Heating/Cooling)
  const energyTraces = createTraces(['sensible heating', 'sensible cooling'], 'HVAC Sensible Energy', 'Energy (J)');
  if (energyTraces.length > 0 && document.getElementById('plotlyZoneEnergy')) {
    Plotly.newPlot('plotlyZoneEnergy', energyTraces, { ...layoutBase, yaxis: { title: 'Energy (J)' } }, { responsive: true });
  }

  // Plot 3: Mass Flow Rate
  const flowTraces = createTraces(['mass flow rate'], 'HVAC Mass Flow Rate', 'Flow Rate (kg/s)');
  if (flowTraces.length > 0 && document.getElementById('plotlyAirflow')) {
    Plotly.newPlot('plotlyAirflow', flowTraces, { ...layoutBase, yaxis: { title: 'Flow Rate (kg/s)' } }, { responsive: true });
  }

  // Plot 4: Utility Meters
  const utilityTraces = createTraces(['electricity:facility', 'naturalgas:facility'], 'Utility Meters', 'Energy (J)');
  if (utilityTraces.length > 0 && document.getElementById('plotlyUtility')) {
    Plotly.newPlot('plotlyUtility', utilityTraces, { ...layoutBase, yaxis: { title: 'Energy (J)' } }, { responsive: true });
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
});

window.submitDescription = submitDescription;
window.loadRuns = loadJobs;
window.toggleSidebar = toggleSidebar;
window.testBackendConnection = testBackendConnection;
window.setBackendUrl = setBackendUrl;
