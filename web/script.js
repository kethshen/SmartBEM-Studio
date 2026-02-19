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
      weather_file: document.getElementById("weatherFile") ? document.getElementById("weatherFile").value : "USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw"
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
// Test AI Connectivity (Layer 4 Check)
// ----------------------------
// ----------------------------
// Test AI Connectivity (Layer 4 Check)
// ----------------------------
function testAIConnection(checkGemini = true, checkOpenAI = true) {
  const statusMsg = document.getElementById("statusMsg");

  // Create a special "test_connection" job
  const jobData = {
    status: "test_connection",
    createdAt: firebase.firestore.FieldValue.serverTimestamp(),
    nlpInputText: "Connectivity Check",
    checkGemini: checkGemini,
    checkOpenAI: checkOpenAI
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
            html += `Gemini: <span style="color:${results.gemini ? 'green' : 'red'}">${results.gemini ? 'Supported' : 'Failed'}</span>`;

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
  const btnView = document.getElementById("btnViewIDF");
  if (btnView) {
    if (data.status === "done" || data.status === "running") { // Allow viewing even if running if file exists (optional, keeping safe)
      // Actually only show if 'done' for now to ensure file exists, or if we track idf generation separately
      if (data.status === "done") {
        btnView.style.display = "block";
        btnView.onclick = () => viewIDF(jobId);
      } else {
        btnView.style.display = "none";
      }
    } else {
      btnView.style.display = "none";
    }
  }

  // Handle Results Visualization
  const imgInfo = document.getElementById("zonePlot");
  const msgInfo = document.getElementById("zonePlotMsg");

  if (!imgInfo) return;

  if (data.status === "done") {
    // Load real results from Storage
    const plotPath = `results/${jobId}/zone_plot.png`;
    msgInfo.innerText = "Loading plot...";

    storage.ref(plotPath).getDownloadURL()
      .then((url) => {
        imgInfo.src = url;
        msgInfo.innerText = "";
        imgInfo.style.display = "block";
      })
      .catch((e) => {
        console.log("No plot found yet:", e);
        imgInfo.style.display = "none";
        msgInfo.innerText = "Plot pending or not generated.";
      });
  } else if (data.status === "error") {
    imgInfo.style.display = "none";
    msgInfo.innerText = "Job failed: " + (data.errorMessage || "Unknown error");
    msgInfo.style.color = "var(--error)";
  } else {
    imgInfo.style.display = "none";
    msgInfo.innerText = "Simulation in progress... (" + data.status + ")";
    msgInfo.style.color = "var(--text-secondary)";
  }
  msgInfo.style.color = "var(--text-secondary)";
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
      // Fallback: If diff.html doesn't exist (e.g. old job), try opening in.idf directly
      alert("Diff view not found. Trying raw file...");
      const idfPath = `jobs/${jobId}/in.idf`;
      storage.ref(idfPath).getDownloadURL().then(u => window.open(u, "_blank"));

      if (btn) btn.innerText = "📄 View Generated IDF";
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
});

// Expose functions to global scope for HTML onclick
window.testFirestoreWrite = testFirestoreWrite;
window.submitDescription = submitDescription;
window.testAIConnection = testAIConnection;
window.loadRuns = loadJobs; // Alias for backward compatibility if HTML buttons haven't changed yet
window.testAIConnection = testAIConnection;
window.loadRuns = loadJobs; // Alias for backward compatibility if HTML buttons haven't changed yet
window.toggleSidebar = toggleSidebar;
window.viewIDF = viewIDF;
