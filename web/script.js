// SmartHVAC Studio — Commercial-Grade Client
// Follows 5-Layer Architecture -> Layer 1 (Frontend) & Layer 2 (Firebase Coordination)

import { firebaseConfig } from "./firebaseConfig.js";

// Firebase SDKs are loaded via CDN in HTML
firebase.initializeApp(firebaseConfig);

// Firestore & Storage
const db = firebase.firestore();
const storage = firebase.storage();

console.log("Firebase initialized (5-Layer Architecture Mode)");
document.body.classList.add('js-loaded'); // Mark for CSS if needed

// ----------------------------
// Weather Index (Global)
// ----------------------------
let weatherIndex = []; // Populated on page load from weather_index.json

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

  // When user selects a value, resolve it to the epw_url
  const searchInput = document.getElementById('weatherSearch');
  if (searchInput) {
    searchInput.addEventListener('change', () => {
      const selected = weatherIndex.find(e => e.title === searchInput.value);
      const hiddenUrl = document.getElementById('weatherEpwUrl');
      if (selected && hiddenUrl) {
        hiddenUrl.value = selected.epw_url;
        console.log('[Weather] Selected:', selected.title, selected.epw_url);
      } else if (hiddenUrl) {
        hiddenUrl.value = ''; // Clear if no match
      }
    });
  }
}

// ----------------------------
// Custom EPW Upload to Firebase Storage
// ----------------------------
function handleEpwUpload(inputEl) {
  const file = inputEl.files[0];
  if (!file) return;

  const statusEl = document.getElementById('epwUploadStatus');
  if (statusEl) statusEl.textContent = 'Uploading...';

  const timestamp = Date.now();
  const storagePath = `weather_uploads/${timestamp}_${file.name}`;
  const storageRef = storage.ref(storagePath);

  storageRef.put(file).then(snapshot => {
    console.log('[Weather] Uploaded custom EPW to:', storagePath);
    // Store the Firebase Storage path as the epw_url
    const hiddenUrl = document.getElementById('weatherEpwUrl');
    if (hiddenUrl) hiddenUrl.value = `firebase_storage:${storagePath}`;
    // Clear the search box and show the uploaded filename
    const searchInput = document.getElementById('weatherSearch');
    if (searchInput) searchInput.value = `Custom: ${file.name}`;
    if (statusEl) statusEl.textContent = `Uploaded: ${file.name}`;
    statusEl.style.color = 'var(--success, green)';
  }).catch(err => {
    console.error('[Weather] Upload failed:', err);
    if (statusEl) statusEl.textContent = 'Upload failed!';
    statusEl.style.color = 'var(--error, red)';
  });
}

// ----------------------------
// TEST: Firestore write
// ----------------------------
// Added 'silent' parameter to suppress alerts for background checks
function testFirestoreWrite(silent = false) {
  const now = new Date();
  const timestampId = now.getFullYear() +
    String(now.getMonth() + 1).padStart(2, '0') +
    String(now.getDate()).padStart(2, '0') + "_" +
    String(now.getHours()).padStart(2, '0') +
    String(now.getMinutes()).padStart(2, '0') +
    String(now.getSeconds()).padStart(2, '0');

  const customId = `client_check_${timestampId}`;

  return db.collection("test_connectivity").doc(customId).set({
    message: "SmartHVAC Studio connected",
    source: "frontend_client",
    timestamp: now
  })
    .then(() => {
      if (!silent) alert("Firestore connection successful!");
      return true;
    })
    .catch((error) => {
      console.error("Firestore error:", error);
      if (!silent) alert("Firestore error: " + error.message);
      throw error;
    });
}

// Sidebar Toggle Logic
function toggleSidebar() {
  const container = document.querySelector('.dashboard-container');
  const sidebar = document.querySelector('.sidebar');
  if (container && sidebar) {
    container.classList.toggle('sidebar-collapsed');
    sidebar.classList.toggle('collapsed');
  }
}

// ----------------------------
// Create a new Job (Layer 1 -> Layer 2)
// ----------------------------
function submitDescription() {

  const input = document.getElementById("description");
  if (!input || input.value.trim() === "") {
    alert("Please enter a description.");
    return;
  }

  // Exact Data Model from Architecture PDF
  const jobData = {
    status: "queued",
    nlpInputText: input.value,
    selectedModel: document.getElementById("aiModel") ? document.getElementById("aiModel").value : "openai",
    createdAt: firebase.firestore.FieldValue.serverTimestamp(),
    updatedAt: firebase.firestore.FieldValue.serverTimestamp(),

    // Placeholders for Layer 3 (Colab) to fill
    idfFilePath: null,
    weatherFilePath: null,
    simulationConfig: {
      ...JSON.parse(localStorage.getItem("smartHVAC_config") || "{}"),
      run_type: document.getElementById("simType") ? document.getElementById("simType").value : "design_day",
      weather_file: "USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw", // Default fallback
      epw_url: document.getElementById("weatherEpwUrl") ? document.getElementById("weatherEpwUrl").value : ""
    },
    resultPath: null,
    errorMessage: null
  };

  // Generate Custom ID: "job_YYYYMMDD_HHMMSS"
  const now = new Date();
  const timestampId = now.getFullYear() +
    String(now.getMonth() + 1).padStart(2, '0') +
    String(now.getDate()).padStart(2, '0') + "_" +
    String(now.getHours()).padStart(2, '0') +
    String(now.getMinutes()).padStart(2, '0') +
    String(now.getSeconds()).padStart(2, '0');

  const customJobId = `job_${timestampId}`;

  // Use set() with custom ID instead of add()
  db.collection("jobs").doc(customJobId).set(jobData)
    .then(() => {
      const statusMsg = document.getElementById("statusMsg");
      if (statusMsg) {
        statusMsg.innerText = `Job submitted! ID: ${customJobId} (Waiting for Colab)`;
        statusMsg.style.color = "green";
      }
      input.value = ""; // Clear input
      // If we are on the results page or dashboard, refresh list
      if (typeof loadJobs === "function") {
        loadJobs();
      }
    })
    .catch((error) => {
      if (statusMsg) {
        statusMsg.innerText = "Error submitting job: " + error.message;
        statusMsg.style.color = "red";
      }
    });
}

// ----------------------------
// Run Minimal IDF (Safe Test)
// ----------------------------
function runMinimalIdf() {
  const jobData = {
    status: "queued",
    runMode: "minimal",
    nlpInputText: "Minimal.idf Safe Test Bypass",
    selectedModel: "none",
    createdAt: firebase.firestore.FieldValue.serverTimestamp(),
    updatedAt: firebase.firestore.FieldValue.serverTimestamp(),
    idfFilePath: null,
    weatherFilePath: null,
    simulationConfig: {
      ...JSON.parse(localStorage.getItem("smartHVAC_config") || "{}"),
      run_type: "design_day",
      weather_file: "USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw"
    },
    resultPath: null,
    errorMessage: null
  };

  const now = new Date();
  const timestampId = now.getFullYear() +
    String(now.getMonth() + 1).padStart(2, '0') +
    String(now.getDate()).padStart(2, '0') + "_" +
    String(now.getHours()).padStart(2, '0') +
    String(now.getMinutes()).padStart(2, '0') +
    String(now.getSeconds()).padStart(2, '0');

  const customJobId = `job_minimal_${timestampId}`;

  db.collection("jobs").doc(customJobId).set(jobData)
    .then(() => {
      const statusMsg = document.getElementById("statusMsg");
      if (statusMsg) {
        statusMsg.innerText = `Safe Test submitted! ID: ${customJobId} (Waiting for Colab)`;
        statusMsg.style.color = "blue";
        statusMsg.style.display = "block";
      }
      if (typeof loadJobs === "function") {
        loadJobs();
      }
    })
    .catch((error) => {
      alert("Error submitting safe test: " + error.message);
    });
}
window.runMinimalIdf = runMinimalIdf;

// ----------------------------
// Test AI Connectivity (Layer 4 Check)
// ----------------------------
// ----------------------------
// Test AI Connectivity (Layer 4 Check)
// ----------------------------
function testAIConnection(checkGemini = true, checkOpenAI = true, checkHF = true) {
  const statusMsg = document.getElementById("statusMsg");

  // Create a special "test_connection" job
  const jobData = {
    status: "test_connection",
    createdAt: firebase.firestore.FieldValue.serverTimestamp(),
    nlpInputText: "Connectivity Check",
    checkGemini: checkGemini,
    checkOpenAI: checkOpenAI,
    checkHF: checkHF
  };

  const now = new Date();
  const timestampId = now.getFullYear() +
    String(now.getMonth() + 1).padStart(2, '0') +
    String(now.getDate()).padStart(2, '0') + "_" +
    String(now.getHours()).padStart(2, '0') +
    String(now.getMinutes()).padStart(2, '0') +
    String(now.getSeconds()).padStart(2, '0');

  const customJobId = `test_ai_${timestampId}`;

  db.collection("test_connectivity").doc(customJobId).set(jobData)
    .then(() => {
      // SILENCED: Do not show "Waiting for Colab"
      // if (statusMsg) {
      //   statusMsg.innerText = "Test requested. Waiting for Colab...";
      //   statusMsg.style.color = "blue";
      // }

      // Listen for the result of THIS specific test job
      const unsubscribe = db.collection("test_connectivity").doc(customJobId)
        .onSnapshot((doc) => {
          const data = doc.data();
          if (data && data.status === "tested" && data.testResults) {
            // Display Detailed Results
            const results = data.testResults;
            const resDiv = document.getElementById("connectionResults");

            let html = "";
            html += `OpenAI: <span style="color:${results.openai ? 'green' : 'red'}">${results.openai ? 'Supported' : 'Failed'}</span> &nbsp;|&nbsp; `;
            html += `Gemini: <span style="color:${results.gemini ? 'green' : 'red'}">${results.gemini ? 'Supported' : 'Failed'}</span> &nbsp;|&nbsp; `;
            html += `HF: <span style="color:${results.hf ? 'green' : 'red'}">${results.hf ? 'Supported' : 'Failed'}</span>`;

            if (results.details) {
              html += `<br><small style="color:gray; font-weight:normal;">${results.details}</small>`;
            }

            if (resDiv) {
              resDiv.innerHTML = html;
              // resDiv.style.display = 'block'; // Or keep hidden if only parsing text
            }

            // SILENCED: Do not show "Check Complete"
            // if (statusMsg) statusMsg.innerText = "Connection Check Complete.";

            unsubscribe(); // Stop listening
          }
        });
    })
    .catch((e) => alert("Failed: " + e.message));
}

// ----------------------------
// Load all Jobs (Status Polling)
// ----------------------------
function loadJobs() {

  const tableBody = document.getElementById("runsTable");
  if (!tableBody) return;

  // Clear current list
  tableBody.innerHTML = "";

  db.collection("jobs")
    .orderBy("createdAt", "desc")
    .limit(4) // Keep UI clean - Last 4 only per user request
    .onSnapshot((snapshot) => {
      // Real-time listener (better than manual polling)
      tableBody.innerHTML = ""; // Clear again for update

      snapshot.forEach((doc) => {
        const data = doc.data();
        const row = document.createElement("tr");

        // Row styling based on status
        let statusColor = "black";
        if (data.status === "running") statusColor = "orange";
        if (data.status === "done") statusColor = "green";
        if (data.status === "error") statusColor = "red";

        // Simple date formatting
        const dateStr = data.createdAt ? data.createdAt.toDate().toLocaleString() : "Just now";

        row.innerHTML = `
              <td style="padding: 0.75rem; border-bottom: 1px solid var(--border-subtle);">${data.nlpInputText ? data.nlpInputText.substring(0, 40) + "..." : "No description"}</td>
              <td style="padding: 0.75rem; border-bottom: 1px solid var(--border-subtle); color: ${statusColor}; font-weight: bold;">${data.status}</td>
              <td style="padding: 0.75rem; border-bottom: 1px solid var(--border-subtle); color: var(--text-secondary); font-size: 0.85rem;">${dateStr}</td>
            `;

        // Click to show details
        row.onclick = () => showJobDetails(doc.id, data);
        row.style.cursor = "pointer";
        row.onmouseover = () => row.style.backgroundColor = "var(--bg-app)";
        row.onmouseout = () => row.style.backgroundColor = "transparent";

        tableBody.appendChild(row);
      });
    }, (error) => {
      console.error("Error loading jobs:", error);
      const autoMsg = document.getElementById("autoMsg");
      if (autoMsg) autoMsg.innerText = "Error syncing jobs.";
    });
}

// ----------------------------
// Show Job Details & Results
// ----------------------------
function showJobDetails(jobId, data) {
  // Hide placeholder, show content
  const placeholder = document.getElementById("detailPlaceholder");
  const content = document.getElementById("detailContent");
  if (placeholder) placeholder.style.display = 'none';
  if (content) content.style.display = 'grid';

  // Fill text details
  const elDesc = document.getElementById("detailDescription");
  const elStatus = document.getElementById("detailStatus");
  const elTime = document.getElementById("detailTime");
  const elPath = document.getElementById("detailPath"); // Re-purposed for ID/Path

  if (elDesc) elDesc.innerText = data.nlpInputText;
  if (elStatus) {
    elStatus.innerText = data.status;
    // Coloring
    if (data.status === "running") elStatus.style.color = "var(--warning)";
    else if (data.status === "done") elStatus.style.color = "var(--success)";
    else if (data.status === "error") elStatus.style.color = "var(--error)";
    else elStatus.style.color = "var(--text-primary)";
  }
  if (elTime) elTime.innerText = data.createdAt ? data.createdAt.toDate().toLocaleString() : "-";
  if (elPath) elPath.innerText = data.resultPath || "Waiting...";

  // Handle "View IDF" Button Visibility
  const actionContainer = document.getElementById("actionButtonsContainer");
  const btnView = document.getElementById("btnViewIDF");
  const btnSummary = document.getElementById("btnViewIDFSummary");
  const btn3D = document.getElementById("btnView3D");
  if (actionContainer && btnView && btnSummary) {
    if (data.status === "done") {
      actionContainer.style.display = "flex";
      btnView.onclick = () => viewIDF(jobId);
      btnSummary.onclick = () => viewIDFSummary(jobId);
      if (btn3D) {
        btn3D.onclick = () => view3DGeometry(jobId);
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

    if (data.status === "done") {
      const plotPath = `jobs/${jobId}/${plotDef.key}.png`;
      msgInfo.innerText = "Loading...";

      storage.ref(plotPath).getDownloadURL()
        .then((url) => {
          imgInfo.src = url;
          msgInfo.innerText = "";
          imgInfo.style.display = "block";
        })
        .catch((e) => {
          console.log(`No ${plotDef.key} found yet:`, e);
          imgInfo.style.display = "none";
          msgInfo.innerText = `${plotDef.fallbackText} not available.`;
        });
    } else if (data.status === "error") {
      imgInfo.style.display = "none";
      msgInfo.innerText = "Job failed.";
      msgInfo.style.color = "var(--error)";
    } else {
      imgInfo.style.display = "none";
      msgInfo.innerText = "Simulation in progress...";
      msgInfo.style.color = "var(--text-secondary)";
    }
  });
}


// ----------------------------
// ----------------------------
// IDF Viewer Logic (Server-Side Diff)
// ----------------------------
function viewIDF(jobId) {
  // Construct path: jobs/{jobId}/diff.html
  // The Backend now generates a "diff.html" file which we can view directly.
  // This bypasses CORS because we don't fetch it, we just open it.

  const diffPath = `jobs/${jobId}/diff.html`;
  const btn = document.getElementById("btnViewIDF");
  if (btn) btn.innerText = "Opening...";

  storage.ref(diffPath).getDownloadURL()
    .then((url) => {
      window.open(url, "_blank");
      if (btn) btn.innerText = "📄 View Generated IDF";
    })
    .catch((error) => {
      console.error("Error fetching Diff URL:", error);
      // Fallback: If diff.html doesn't exist, try opening the raw generated IDF directly
      const idfPath = `jobs/${jobId}/${jobId}_in.idf`;
      storage.ref(idfPath).getDownloadURL().then(u => window.open(u, "_blank")).catch(e => {
        alert("IDF file not found on server.");
      });

      if (btn) btn.innerText = "📄 View Generated IDF";
    });
}

// ----------------------------
// View IDF Summary (Backend Generated)
// ----------------------------
function viewIDFSummary(jobId) {
  const summaryPath = `jobs/${jobId}/summary.html`;
  const btn = document.getElementById("btnViewIDFSummary");
  if (btn) btn.innerText = "Opening...";

  storage.ref(summaryPath).getDownloadURL()
    .then((url) => {
      window.open(url, "_blank");
      if (btn) btn.innerText = "📋 View Object Summary";
    })
    .catch((error) => {
      console.error("Error fetching Summary URL:", error);
      alert("Summary not available. This is likely an older job generated before the summary feature was added. Please run a new job!");
      if (btn) btn.innerText = "📋 View Object Summary";
    });
}

// ----------------------------
// View 3D Geometry (Backend Generated)
// ----------------------------
function view3DGeometry(jobId) {
  const geometryPath = `jobs/${jobId}/geometry.html`;
  const btn = document.getElementById("btnView3D");
  if (btn) btn.innerText = "Opening...";

  storage.ref(geometryPath).getDownloadURL()
    .then((url) => {
      window.open(url, "_blank");
      if (btn) btn.innerText = "🧊 View 3D Model";
    })
    .catch((error) => {
      console.error("Error fetching 3D Geometry URL:", error);
      alert("3D Geometry not available for this job.");
      if (btn) btn.innerText = "🧊 View 3D Model";
    });
}

// ----------------------------
// Auto-Init on Page Load
// ----------------------------
window.addEventListener("load", () => {
  // If we are on the results page, load jobs immediately
  if (document.getElementById("runsTable")) {
    loadJobs();
  }
  // If we are on the NLP page, load the weather index
  if (document.getElementById("weatherSearch")) {
    loadWeatherIndex();
  }
});

// Expose functions to global scope for HTML onclick
window.testFirestoreWrite = testFirestoreWrite;
window.submitDescription = submitDescription;
window.testAIConnection = testAIConnection;
window.loadRuns = loadJobs; // Alias for backward compatibility if HTML buttons haven't changed yet
window.testAIConnection = testAIConnection;
window.loadRuns = loadJobs; // Alias for backward compatibility
window.toggleSidebar = toggleSidebar;
window.viewIDF = viewIDF;
window.viewIDFSummary = viewIDFSummary;
window.view3DGeometry = view3DGeometry;
window.handleEpwUpload = handleEpwUpload;
