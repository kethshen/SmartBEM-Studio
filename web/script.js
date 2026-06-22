// SmartBEM Studio — Direct Tunnel Architecture
// Connects directly to Google Colab via Ngrok/FastAPI

// ----------------------------
// Backend URL Management
// ----------------------------
function getBackendUrl() {
  let url = localStorage.getItem("smartbem_backend_url");
  if (!url) {
    url = "http://127.0.0.1:8000"; // Default fallback
  }
  // ensure no trailing slash
  return url.replace(/\/$/, "");
}

function setBackendUrl(url) {
  localStorage.setItem("smartbem_backend_url", url);
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
      const logsLink = document.getElementById("backendLogsLink");
      if (logsLink) {
        logsLink.href = `${url}/results/backend.log`;
        logsLink.style.display = "inline";
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
      const logsLink = document.getElementById("backendLogsLink");
      if (logsLink) {
        logsLink.style.display = "none";
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
  const jobs = localStorage.getItem("smartbem_jobs");
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
  
  try {
    localStorage.setItem("smartbem_jobs", JSON.stringify(jobs));
  } catch (e) {
    if (e.name === 'QuotaExceededError' || e.code === 22 || e.code === 1014) {
      console.warn("[Storage] Quota exceeded. Cleaning up large fields from cache and retrying...");
      // 1. Strip csv_data and idf from all jobs in memory
      jobs.forEach(j => {
        if (j.result) {
          delete j.result.csv_data;
          delete j.result.idf;
        }
      });
      try {
        localStorage.setItem("smartbem_jobs", JSON.stringify(jobs));
        console.log("[Storage] Cleaned up fields and saved successfully.");
        return;
      } catch (e2) {
        console.warn("[Storage] Quota still exceeded after stripping fields. Pruning old jobs...");
        // 2. Keep only the last 5 jobs
        while (jobs.length > 5) {
          jobs.pop(); // Remove oldest
          try {
            localStorage.setItem("smartbem_jobs", JSON.stringify(jobs));
            console.log(`[Storage] Pruned to ${jobs.length} jobs and saved successfully.`);
            return;
          } catch (e3) {
            // continue popping
          }
        }
        // 3. Fallback: clear smartbem_jobs completely or keep only the current job
        try {
          const minimalJobs = jobs.filter(j => j.id === jobData.id);
          localStorage.setItem("smartbem_jobs", JSON.stringify(minimalJobs));
          console.log("[Storage] Kept only current job to fit quota.");
        } catch (e4) {
          console.error("[Storage] Failed to save even a single job to localStorage:", e4);
        }
      }
    } else {
      console.error("[Storage] Unexpected localStorage error:", e);
    }
  }
}

function cleanupLocalStorage() {
  try {
    let jobs = localStorage.getItem("smartbem_jobs");
    if (jobs) {
      let parsed = JSON.parse(jobs);
      let modified = false;
      parsed.forEach(job => {
        if (job.result) {
          if (job.result.csv_data) {
            delete job.result.csv_data;
            modified = true;
          }
          if (job.result.idf) {
            delete job.result.idf;
            modified = true;
          }
        }
      });
      if (modified) {
        localStorage.setItem("smartbem_jobs", JSON.stringify(parsed));
        console.log("[Storage] Stripped large CSV/IDF data from localStorage cache to free quota.");
      }
    }
  } catch (e) {
    console.error("[Storage] Failed to cleanup localStorage:", e);
  }
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
      ...JSON.parse(localStorage.getItem("smartBEM_config") || "{}"),
      run_type: document.getElementById("simType") ? document.getElementById("simType").value : "design_day",
      weather_file: "USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw", 
      epw_url: document.getElementById("weatherEpwUrl") ? document.getElementById("weatherEpwUrl").value : "",
      model_type: document.getElementById("aiModel") ? document.getElementById("aiModel").value : "ollama",
      generator_type: document.getElementById("generatorType") ? document.getElementById("generatorType").value : "custom"
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
    const simStatusContainer = document.getElementById("simStatusContainer");
    const simStatusMsg = document.getElementById("simStatusMsg");
    const simErrorBox = document.getElementById("simErrorBox");
    
    if (simStatusContainer && simStatusMsg) {
      simStatusContainer.style.display = "block";
      simStatusMsg.innerText = `Job ${jobId} submitted! Running...`;
      simStatusMsg.style.color = "var(--warning)";
      if (simErrorBox) simErrorBox.style.display = "none";
    } else if (statusMsg) {
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
          
          // Update local storage without large CSV/IDF content to stay under Quota limit
          const jobData = {
            id: jobId,
            status: data.status,
            prompt: data.prompt,
            createdAt: data.created_at * 1000,
            result: data.result ? { files: data.result.files } : null,
            error_message: data.error_message
          };
          saveLocalJob(jobData);
          if (typeof loadJobs === "function") loadJobs();
          
          // Auto-refresh the details panel if this completed job is the one the user is currently viewing
          if (typeof selectedJobId !== "undefined" && selectedJobId === jobId) {
            showJobDetails(jobId, jobData);
          }
          
          const simStatusContainer = document.getElementById("simStatusContainer");
          const simStatusMsg = document.getElementById("simStatusMsg");
          const simErrorBox = document.getElementById("simErrorBox");
          const statusMsg = document.getElementById("statusMsg");
          
          if (simStatusContainer && simStatusMsg) {
            if (data.status === "done") {
              simStatusMsg.innerText = `Job ${jobId} completed successfully!`;
              simStatusMsg.style.color = "var(--success)";
              if (simErrorBox) simErrorBox.style.display = "none";
            } else if (data.status === "error") {
              simStatusMsg.innerText = `Job ${jobId} failed.`;
              simStatusMsg.style.color = "var(--error)";
              if (simErrorBox) {
                simErrorBox.innerText = data.error_message;
                simErrorBox.style.display = "block";
              }
            }
          } else if (statusMsg) {
            statusMsg.innerText = data.status === "done" ? "Simulation Complete!" : "Simulation Failed.";
            statusMsg.style.color = data.status === "done" ? "green" : "red";
            
            if (data.status === "error") {
              // Fallback for pages without simStatusContainer
              const oldErr = statusMsg.parentNode.querySelector(".sim-poll-error");
              if (oldErr) oldErr.remove();
              
              const errBox = document.createElement("pre");
              errBox.className = "sim-poll-error";
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
let selectedJobId = null;

function showJobDetails(jobId, data) {
  selectedJobId = jobId; // Track the currently viewed job
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

  const elErrorLabel = document.getElementById("detailErrorLabel");
  const elErrorBox = document.getElementById("detailErrorBox");
  
  if (data.status === "error" && data.error_message) {
    if (elErrorLabel) elErrorLabel.style.display = "inline";
    if (elErrorBox) {
      elErrorBox.innerText = data.error_message;
      elErrorBox.style.display = "block";
    }
  } else {
    if (elErrorLabel) elErrorLabel.style.display = "none";
    if (elErrorBox) elErrorBox.style.display = "none";
  }

  // Handle Buttons
  const actionContainer = document.getElementById("actionButtonsContainer");
  const btnView = document.getElementById("btnViewIDF");
  const btnSummary = document.getElementById("btnViewIDFSummary");
  const btn3D = document.getElementById("btnView3D");
  
  if (actionContainer && btnView && btnSummary) {
    if (data.status === "done" && data.result) {
      actionContainer.style.display = "flex";
      btnView.onclick = () => {
         if (data.result.files && data.result.files.idf) {
             window.open(getBackendUrl() + data.result.files.idf, "_blank");
         } else if (data.result.idf) {
             const w = window.open();
             w.document.write(`<pre>${data.result.idf.replace(/</g, "&lt;")}</pre>`);
         } else {
             alert("IDF not available.");
         }
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
  const resultsContainer = document.getElementById("resultsContainer");
  const resultsSidebar = document.getElementById("resultsSidebar");

  if (data.status === "done" && data.result) {
    if (resultsSidebar) resultsSidebar.style.display = "block";
    
    // Check if we have CSV data in the local object (old runs), or need to fetch it from the server
    if (data.result.csv_data) {
      renderPlotlyCharts(data.result.csv_data);
    } else if (data.result.files && data.result.files.csv) {
      if (resultsContainer) {
        resultsContainer.innerHTML = `<p style="color:var(--warning); padding:2rem; text-align:center; font-weight:600;">Loading chart data from server...</p>`;
      }
      const csvUrl = getBackendUrl() + data.result.files.csv;
      fetch(csvUrl, {
        headers: { 'ngrok-skip-browser-warning': 'true' }
      })
        .then(res => {
          if (!res.ok) throw new Error(`HTTP ${res.status} error loading CSV`);
          return res.text();
        })
        .then(csvText => {
          renderPlotlyCharts(csvText);
        })
        .catch(err => {
          console.error("[Storage] Failed to load results CSV:", err);
          if (resultsContainer) {
            resultsContainer.innerHTML = `<p style="color:var(--error); padding:2rem; text-align:center; font-weight:600;">Failed to load chart data: ${err.message}</p>`;
          }
        });
    } else {
      if (resultsSidebar) resultsSidebar.style.display = "none";
      if (resultsContainer) {
        resultsContainer.innerHTML = `<p style="color:var(--error); padding:2rem; text-align:center;">Results file path missing from this run.</p>`;
      }
    }
  } else {
    if (resultsSidebar) resultsSidebar.style.display = "none";
    if (resultsContainer) {
      if (data.status === "error") {
        resultsContainer.innerHTML = `<p style="color:var(--error); padding:2rem; text-align:center; font-weight:600;">Simulation failed. Check error details above.</p>`;
      } else if (data.status === "running") {
        resultsContainer.innerHTML = `<p style="color:var(--warning); padding:2rem; text-align:center; font-weight:600;">Simulation in progress... Please wait.</p>`;
      } else {
        resultsContainer.innerHTML = `<p style="color:var(--text-secondary); padding:2rem; text-align:center;">Select a job from the history to view results.</p>`;
      }
    }
  }
}

// ----------------------------
// Navigation scroll and expand handler
// ----------------------------
function scrollToCard(cardId) {
  const card = document.getElementById(cardId);
  if (card) {
    card.open = true; // Ensure details is open
    card.scrollIntoView({ behavior: 'smooth' });
    
    // Trigger Plotly resizing to ensure proper width snap
    setTimeout(() => {
      const plots = card.querySelectorAll(".js-plotly-plot");
      plots.forEach(p => Plotly.Plots.resize(p));
    }, 150);
    
    // Highlight sidebar nav item
    document.querySelectorAll(".results-nav-item").forEach(item => {
      item.classList.remove("active");
    });
    const navItem = document.getElementById(`nav_${cardId}`);
    if (navItem) {
      navItem.classList.add("active");
    }
  }
}
window.scrollToCard = scrollToCard;

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
    const container = document.getElementById("resultsContainer");
    if (container) {
      container.innerHTML = `<p style="color:var(--error); padding:2rem;">Data error: Date/Time column missing from CSV.</p>`;
    }
    return;
  }
  const timeLabels = dataRows.map((row, idx) => idx + 1);

  const resultsContainer = document.getElementById("resultsContainer");
  const resultsNavLinks = document.getElementById("resultsNavLinks");
  if (!resultsContainer) return;
  
  resultsContainer.innerHTML = "";
  if (resultsNavLinks) resultsNavLinks.innerHTML = "";

  // Helper to extract min, max from data
  const getMinMax = (colName) => {
    let min = Infinity;
    let max = -Infinity;
    dataRows.forEach(row => {
      const val = parseFloat(row[colName]);
      if (!isNaN(val)) {
        if (val < min) min = val;
        if (val > max) max = val;
      }
    });
    return { min: min === Infinity ? null : min, max: max === -Infinity ? null : max };
  };

  // Helper to sum up utility meters / loads
  const getSum = (colName) => {
    let sum = 0;
    dataRows.forEach(row => {
      const val = parseFloat(row[colName]);
      if (!isNaN(val)) {
        sum += val;
      }
    });
    return sum;
  };

  // ----------------------------------------------------
  // Discover Zones
  // ----------------------------------------------------
  const zones = new Set();
  headers.forEach(h => {
    if (h.startsWith("Zone ") && h.includes(":")) {
      const parts = h.split(":");
      const zoneName = parts[parts.length - 1].trim();
      zones.add(zoneName);
    }
  });
  const zoneList = Array.from(zones);
  console.log("[Plotly] Discovered Zones:", zoneList);

  // ----------------------------------------------------
  // 1. Global / Shared Card (Full Width)
  // ----------------------------------------------------
  const outdoorTempCol = headers.find(h => h.toLowerCase().includes("site outdoor air drybulb temperature"));
  const electricityCol = headers.find(h => h.toLowerCase().includes("electricity:facility"));
  const gasCol = headers.find(h => h.toLowerCase().includes("naturalgas:facility"));

  const outdoorStats = outdoorTempCol ? getMinMax(outdoorTempCol) : { min: null, max: null };
  const totalElec = electricityCol ? getSum(electricityCol) / 3.6e6 : null;
  const totalGas = gasCol ? getSum(gasCol) / 3.6e6 : null;

  const globalCardId = "card_global_shared";
  const globalDetails = document.createElement("details");
  globalDetails.className = "dropdown-card";
  globalDetails.id = globalCardId;
  globalDetails.open = true; // Starts open

  const globalSummary = document.createElement("summary");
  globalSummary.innerHTML = `
    <div class="summary-title-wrapper">
      <span>⚙️ Global / Shared</span>
    </div>
    <span class="summary-chevron">›</span>
  `;
  globalDetails.appendChild(globalSummary);

  const globalContent = document.createElement("div");
  globalContent.className = "dropdown-content";

  // Global KPIs Row
  let globalKpiHtml = `<div class="kpi-row">`;
  if (outdoorStats.max !== null) {
    globalKpiHtml += `
      <div class="kpi-box">
        <span class="kpi-label">Max Outdoor Temp</span>
        <span class="kpi-value">${outdoorStats.max.toFixed(1)} °C</span>
      </div>
      <div class="kpi-box">
        <span class="kpi-label">Min Outdoor Temp</span>
        <span class="kpi-value">${outdoorStats.min.toFixed(1)} °C</span>
      </div>
    `;
  }
  if (totalElec !== null) {
    globalKpiHtml += `
      <div class="kpi-box">
        <span class="kpi-label">Total Electricity</span>
        <span class="kpi-value">${totalElec.toFixed(2)} kWh</span>
      </div>
    `;
  }
  if (totalGas !== null) {
    globalKpiHtml += `
      <div class="kpi-box">
        <span class="kpi-label">Total Natural Gas</span>
        <span class="kpi-value">${totalGas.toFixed(2)} kWh</span>
      </div>
    `;
  }
  globalKpiHtml += `</div>`;
  globalContent.innerHTML = globalKpiHtml;

  const globalPlot1Id = "plot_global_weather";
  const globalPlot2Id = "plot_global_utility";

  globalContent.innerHTML += `
    <div class="inner-plot-card">
      <h5>Outdoor Weather Drybulb Temperature Profile</h5>
      <div id="${globalPlot1Id}" class="plotly-container"></div>
    </div>
    <div class="inner-plot-card">
      <h5>Building Facility Utility Meters (Cumulative kWh)</h5>
      <div id="${globalPlot2Id}" class="plotly-container"></div>
    </div>
  `;
  globalDetails.appendChild(globalContent);
  resultsContainer.appendChild(globalDetails);

  // Add global to sidebar
  if (resultsNavLinks) {
    const navItem = document.createElement("li");
    navItem.className = "results-nav-item active";
    navItem.id = `nav_${globalCardId}`;
    navItem.innerHTML = `<button onclick="scrollToCard('${globalCardId}')">⚙️ Global / Shared</button>`;
    resultsNavLinks.appendChild(navItem);
  }

  // ----------------------------------------------------
  // 2. Zone Cards Container (Grid, 2 per row)
  // ----------------------------------------------------
  const zonesGrid = document.createElement("div");
  zonesGrid.className = "zones-grid";
  resultsContainer.appendChild(zonesGrid);

  const helperFindZoneCol = (pattern, zone) => {
    return headers.find(h => {
      const parts = h.split(":");
      if (parts.length < 2) return false;
      const colVar = parts[0].trim().toLowerCase();
      const colZone = parts[parts.length - 1].trim().toLowerCase();
      return colVar.includes(pattern.toLowerCase()) && colZone === zone.toLowerCase();
    });
  };

  // Keep a map of plot configs to render with Plotly after DOM injection
  const plotlyPlotsToRender = [];

  zoneList.forEach(zoneName => {
    const zoneMeanTempCol = helperFindZoneCol("zone mean air temperature", zoneName);
    const zoneAirTempCol = helperFindZoneCol("zone air temperature", zoneName);
    const coolingEnergyCol = helperFindZoneCol("sensible cooling energy", zoneName);
    const heatingEnergyCol = helperFindZoneCol("sensible heating energy", zoneName);
    const mechVentCol = helperFindZoneCol("mechanical ventilation mass flow rate", zoneName);

    // Node flows associated with this zone
    const nodeFlowCols = headers.filter(h => {
      if (!h.toLowerCase().includes("system node mass flow rate")) return false;
      const parts = h.split(":");
      if (parts.length < 2) return false;
      const nodeName = parts[parts.length - 1].toLowerCase();
      return nodeName.includes(zoneName.toLowerCase());
    });

    // Calculate Zone KPIs
    let zoneTempStats = { min: null, max: null };
    if (zoneMeanTempCol) {
      zoneTempStats = getMinMax(zoneMeanTempCol);
    } else if (zoneAirTempCol) {
      zoneTempStats = getMinMax(zoneAirTempCol);
    }

    const zoneCoolingkWh = coolingEnergyCol ? getSum(coolingEnergyCol) / 3.6e6 : null;
    const zoneHeatingkWh = heatingEnergyCol ? getSum(heatingEnergyCol) / 3.6e6 : null;

    const zoneCardId = `card_zone_${zoneName.replace(/[^a-zA-Z0-9]/g, "_")}`;
    const zoneDetails = document.createElement("details");
    zoneDetails.className = "dropdown-card";
    zoneDetails.id = zoneCardId;
    zoneDetails.open = true; // starts open by default

    const zoneSummary = document.createElement("summary");
    zoneSummary.innerHTML = `
      <div class="summary-title-wrapper">
        <span>🚪 Zone: ${zoneName}</span>
      </div>
      <span class="summary-chevron">›</span>
    `;
    zoneDetails.appendChild(zoneSummary);

    const zoneContent = document.createElement("div");
    zoneContent.className = "dropdown-content";

    // Zone KPIs HTML
    let zoneKpiHtml = `<div class="kpi-row">`;
    if (zoneTempStats.max !== null) {
      zoneKpiHtml += `
        <div class="kpi-box">
          <span class="kpi-label">Max Indoor Temp</span>
          <span class="kpi-value">${zoneTempStats.max.toFixed(1)} °C</span>
        </div>
        <div class="kpi-box">
          <span class="kpi-label">Min Indoor Temp</span>
          <span class="kpi-value">${zoneTempStats.min.toFixed(1)} °C</span>
        </div>
      `;
    }
    if (zoneCoolingkWh !== null) {
      zoneKpiHtml += `
        <div class="kpi-box">
          <span class="kpi-label">Total Cooling</span>
          <span class="kpi-value">${zoneCoolingkWh.toFixed(2)} kWh</span>
        </div>
      `;
    }
    if (zoneHeatingkWh !== null) {
      zoneKpiHtml += `
        <div class="kpi-box">
          <span class="kpi-label">Total Heating</span>
          <span class="kpi-value">${zoneHeatingkWh.toFixed(2)} kWh</span>
        </div>
      `;
    }
    zoneKpiHtml += `</div>`;
    zoneContent.innerHTML = zoneKpiHtml;

    // Plots inside Zone Card
    const zoneTempPlotId = `plot_temp_${zoneCardId}`;
    const zoneEnergyPlotId = `plot_energy_${zoneCardId}`;
    const zoneAirflowPlotId = `plot_airflow_${zoneCardId}`;

    zoneContent.innerHTML += `
      <div class="inner-plot-card">
        <h5>Zone Temperature Profiles</h5>
        <div id="${zoneTempPlotId}" class="plotly-container"></div>
      </div>
    `;

    // Add temp traces config
    const tempTraces = [];
    if (zoneMeanTempCol) {
      tempTraces.push({
        x: timeLabels,
        y: dataRows.map(row => parseFloat(row[zoneMeanTempCol]) || null),
        type: 'scatter',
        mode: 'lines',
        name: 'Zone Mean Air Temp',
        line: { color: '#2563eb', width: 2 }
      });
    }
    if (zoneAirTempCol) {
      tempTraces.push({
        x: timeLabels,
        y: dataRows.map(row => parseFloat(row[zoneAirTempCol]) || null),
        type: 'scatter',
        mode: 'lines',
        name: 'Zone Air Temp',
        line: { color: '#10b981', width: 1.5 }
      });
    }
    if (outdoorTempCol) {
      tempTraces.push({
        x: timeLabels,
        y: dataRows.map(row => parseFloat(row[outdoorTempCol]) || null),
        type: 'scatter',
        mode: 'lines',
        name: 'Outdoor Temp (Ref)',
        line: { color: '#94a3b8', width: 1.5, dash: 'dash' }
      });
    }
    plotlyPlotsToRender.push({ 
      id: zoneTempPlotId, 
      traces: tempTraces, 
      ytitle: { text: 'Temperature (°C)', font: { size: 15, weight: 'bold', color: '#1e293b' } } 
    });
 
    // Sensible energy curves config (converted to kWh)
    if (coolingEnergyCol || heatingEnergyCol) {
      zoneContent.innerHTML += `
        <div class="inner-plot-card">
          <h5>HVAC Delivered Sensible Energy (kWh)</h5>
          <div id="${zoneEnergyPlotId}" class="plotly-container"></div>
        </div>
      `;
      const energyTraces = [];
      if (coolingEnergyCol) {
        energyTraces.push({
          x: timeLabels,
          y: dataRows.map(row => (parseFloat(row[coolingEnergyCol]) / 3.6e6) || null),
          type: 'scatter',
          mode: 'lines',
          name: 'Cooling Energy (kWh)',
          line: { color: '#3b82f6', width: 2 }
        });
      }
      if (heatingEnergyCol) {
        energyTraces.push({
          x: timeLabels,
          y: dataRows.map(row => (parseFloat(row[heatingEnergyCol]) / 3.6e6) || null),
          type: 'scatter',
          mode: 'lines',
          name: 'Heating Energy (kWh)',
          line: { color: '#ef4444', width: 2 }
        });
      }
      plotlyPlotsToRender.push({ 
        id: zoneEnergyPlotId, 
        traces: energyTraces, 
        ytitle: { text: 'Energy (kWh)', font: { size: 15, weight: 'bold', color: '#1e293b' } } 
      });
    }
 
    // Ventilation and flows config
    if (mechVentCol || nodeFlowCols.length > 0) {
      zoneContent.innerHTML += `
        <div class="inner-plot-card">
          <h5>Mechanical Ventilation & Node Airflow Rate</h5>
          <div id="${zoneAirflowPlotId}" class="plotly-container"></div>
        </div>
      `;
      const flowTraces = [];
      if (mechVentCol) {
        flowTraces.push({
          x: timeLabels,
          y: dataRows.map(row => parseFloat(row[mechVentCol]) || null),
          type: 'scatter',
          mode: 'lines',
          name: 'Mech Ventilation Rate',
          line: { color: '#10b981', width: 2 }
        });
      }
      nodeFlowCols.forEach((col, idx) => {
        let nodeShortName = col.split(":")[1] || col;
        nodeShortName = nodeShortName.replace(/\(Hourly\)/g, '').trim();
        flowTraces.push({
          x: timeLabels,
          y: dataRows.map(row => parseFloat(row[col]) || null),
          type: 'scatter',
          mode: 'lines',
          name: nodeShortName,
          line: { width: 1.5 }
        });
      });
      plotlyPlotsToRender.push({ 
        id: zoneAirflowPlotId, 
        traces: flowTraces, 
        ytitle: { text: 'Flow Rate (kg/s)', font: { size: 15, weight: 'bold', color: '#1e293b' } } 
      });
    }
 
    zoneDetails.appendChild(zoneContent);
    zonesGrid.appendChild(zoneDetails);
 
    // Sidebar navigation link
      if (resultsNavLinks) {
      const navItem = document.createElement("li");
      navItem.className = "results-nav-item";
      navItem.id = `nav_${zoneCardId}`;
      navItem.innerHTML = `<button onclick="scrollToCard('${zoneCardId}')">🚪 ${zoneName}</button>`;
      resultsNavLinks.appendChild(navItem);
    }
  });
 
  // ----------------------------------------------------
  // Dynamic tick configuration & Day boundary shapes
  // ----------------------------------------------------
  let tickmodeVal = 'auto';
  let dtickVal = undefined;
  if (timeLabels.length <= 168) {
    tickmodeVal = 'linear';
    dtickVal = 4;
  } else if (timeLabels.length <= 744) {
    tickmodeVal = 'linear';
    dtickVal = 24;
  }

  const shapes = [];
  if (timeLabels.length <= 240) {
    for (let h = 24; h < timeLabels.length; h += 24) {
      shapes.push({
        type: 'line',
        xref: 'x',
        yref: 'paper',
        x0: h,
        y0: 0,
        x1: h,
        y1: 1,
        line: {
          color: '#cbd5e1', // slate-300
          width: 1,
          dash: 'dot'
        }
      });
    }
  }

  // ----------------------------------------------------
  // Render Plotly Charts (after DOM nodes are attached)
  // ----------------------------------------------------
  const layoutBase = {
    margin: { t: 40, r: 25, l: 85, b: 100 }, // padded bottom and left margins to avoid label overlaps
    legend: { orientation: "h", y: -0.3, font: { size: 14 } },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    hovermode: 'x unified',
    font: { family: 'Inter, sans-serif', size: 15, color: '#1e293b' }, // larger base font size 15
    shapes: shapes,
    xaxis: {
      title: {
        text: 'Time (hours)',
        font: { size: 15, weight: 'bold', color: '#1e293b' },
        standoff: 15
      },
      gridcolor: '#e2e8f0',
      zeroline: false,
      tickfont: { size: 13 },
      tickmode: tickmodeVal,
      dtick: dtickVal
    },
    yaxis: {
      gridcolor: '#e2e8f0',
      zeroline: false,
      tickfont: { size: 13 }
    }
  };
 
  // Render Global Plots
  const globalWeatherTraces = [];
  if (outdoorTempCol) {
    globalWeatherTraces.push({
      x: timeLabels,
      y: dataRows.map(row => parseFloat(row[outdoorTempCol]) || null),
      type: 'scatter',
      mode: 'lines',
      name: 'Outdoor Temperature',
      line: { color: '#ef4444', width: 2 }
    });
  }
  if (globalWeatherTraces.length > 0 && document.getElementById(globalPlot1Id)) {
    Plotly.newPlot(globalPlot1Id, globalWeatherTraces, { 
      ...layoutBase, 
      yaxis: { 
        ...layoutBase.yaxis, 
        title: { text: 'Temperature (°C)', font: { size: 15, weight: 'bold', color: '#1e293b' } } 
      } 
    }, { responsive: true, displayModeBar: true });
  }
 
  const globalUtilityTraces = [];
  if (electricityCol) {
    globalUtilityTraces.push({
      x: timeLabels,
      y: dataRows.map(row => (parseFloat(row[electricityCol]) / 3.6e6) || null),
      type: 'scatter',
      mode: 'lines',
      name: 'Electricity:Facility (kWh)',
      line: { color: '#2563eb', width: 2 }
    });
  }
  if (gasCol) {
    globalUtilityTraces.push({
      x: timeLabels,
      y: dataRows.map(row => (parseFloat(row[gasCol]) / 3.6e6) || null),
      type: 'scatter',
      mode: 'lines',
      name: 'NaturalGas:Facility (kWh)',
      line: { color: '#f59e0b', width: 2 }
    });
  }
  if (globalUtilityTraces.length > 0 && document.getElementById(globalPlot2Id)) {
    Plotly.newPlot(globalPlot2Id, globalUtilityTraces, { 
      ...layoutBase, 
      yaxis: { 
        ...layoutBase.yaxis, 
        title: { text: 'Energy (kWh)', font: { size: 15, weight: 'bold', color: '#1e293b' } } 
      } 
    }, { responsive: true, displayModeBar: true });
  }
 
  // Render all Zone plots
  plotlyPlotsToRender.forEach(config => {
    const el = document.getElementById(config.id);
    if (el && config.traces.length > 0) {
      Plotly.newPlot(config.id, config.traces, { 
        ...layoutBase, 
        yaxis: { ...layoutBase.yaxis, title: config.ytitle } 
      }, { responsive: true, displayModeBar: true });
    }
  });

  // ----------------------------------------------------
  // Bind Collapsible Toggles & Resize Hook
  // ----------------------------------------------------
  document.querySelectorAll("details.dropdown-card").forEach(detailsEl => {
    detailsEl.addEventListener("toggle", (e) => {
      if (detailsEl.open) {
        const plots = detailsEl.querySelectorAll(".js-plotly-plot");
        plots.forEach(p => {
          Plotly.Plots.resize(p);
        });

        // Sync Nav bar item active class
        const cardId = detailsEl.id;
        document.querySelectorAll(".results-nav-item").forEach(item => {
          item.classList.remove("active");
        });
        const navItem = document.getElementById(`nav_${cardId}`);
        if (navItem) {
          navItem.classList.add("active");
        }
      }
    });
  });

  // Add scroll spy listener to the main-content container
  const scrollContainer = document.querySelector(".main-content");
  if (scrollContainer) {
    // debounce helper for performance
    let scrollTimer = null;
    scrollContainer.addEventListener("scroll", () => {
      if (scrollTimer) clearTimeout(scrollTimer);
      scrollTimer = setTimeout(() => {
        const cards = document.querySelectorAll("details.dropdown-card");
        let activeCardId = null;
        let minDistance = Infinity;

        cards.forEach(card => {
          const rect = card.getBoundingClientRect();
          const distance = Math.abs(rect.top - 120);
          if (rect.top < window.innerHeight * 0.4 && rect.bottom > 80) {
            if (distance < minDistance) {
              minDistance = distance;
              activeCardId = card.id;
            }
          }
        });

        if (activeCardId) {
          document.querySelectorAll(".results-nav-item").forEach(item => {
            item.classList.remove("active");
          });
          const navItem = document.getElementById(`nav_${activeCardId}`);
          if (navItem) {
            navItem.classList.add("active");
          }
        }
      }, 100);
    });
  }
}

// ----------------------------
// Auto-Init on Page Load
// ----------------------------
window.addEventListener("load", () => {
  cleanupLocalStorage();
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
