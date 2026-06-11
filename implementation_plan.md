# Architectural Refactor: FastAPI, Ngrok, and OpenStudio Evaluation

This document outlines the planning and analysis for two major architectural decisions for the SmartHVAC Studio FYP.

## 1. Replacing Firebase with FastAPI + Ngrok

### Concept
Eliminate Firebase as the middleman. Instead, run a `FastAPI` server directly inside the Google Colab environment and expose it to the public internet using `ngrok` (or `pinggy`). The Vanilla JS frontend will send HTTP POST requests directly to this temporary URL.

### Pros
- **Zero Cloud Configuration:** Eliminates the need for Firebase projects, Firestore databases, and API keys.
- **Industry Standard:** Transitioning to a REST API architecture is a highly professional and standard approach.
- **Security:** Colab acts as an isolated sandbox, and the tunnel is fully encrypted.

### Implementation Steps
1. **Backend (Colab/Python):**
   - Create a `FastAPI` application with an endpoint (e.g., `/api/simulate`).
   - Implement `CORS` middleware to allow requests from the web frontend.
   - Create Pydantic models to accept the user's prompt and simulation settings.
   - Integrate `pyngrok` (or `pinggy`) to spin up the public tunnel and print the URL to the console.
2. **Frontend (Vanilla JS):**
   - Remove all Firebase SDKs (`firebase-app.js`, `firebase-firestore.js`).
   - Add a configuration input field in the UI where the user pastes the temporary Ngrok URL provided by Colab.
   - Replace Firebase Firestore listeners with asynchronous `fetch()` API calls to the Ngrok URL.

---

## 2. OpenStudio vs. Custom Plotly & IDF Generator

### Concept
The user suggested using OpenStudio (which has a Python SDK and a Desktop GUI) to replace the current custom Plotly visualizer and IDF text generator.

### Analysis

**The Reality of OpenStudio's GUI:**
OpenStudio is incredibly powerful, but its GUI is a **Desktop Application** that must be installed locally on a computer (~500MB download). It does *not* have a native web viewer. 

**If we switch to OpenStudio for Visualization:**
- **The "Zero-Install" Web Experience is Broken:** The evaluator/user would no longer be able to just open your Vercel website and instantly see the 3D model. They would have to download the `.osm` file from your web app, install the OpenStudio Desktop App on their computer, and open the file manually. This completely destroys the "smooth, magical web product" feel you are aiming for.

**If we switch to OpenStudio Python SDK for Backend Generation:**
- **Pros:** We could replace `geometry_util.py` with OpenStudio's Python SDK to build the geometry. This guarantees perfectly valid geometry, handles wall adjacencies automatically, and prevents overlapping bugs.
- **Cons:** It requires a complete rewrite of the AI prompt translation logic to interface with the OpenStudio SDK instead of generating raw IDF strings. 
- **Compatibility:** We could use the OpenStudio SDK to generate the model in the backend, export it to an `.idf`, and *still* send that IDF to your Plotly visualizer for the web UI.

### My Recommendation for the FYP
1. **Do NOT drop Plotly.** Plotly is what gives your project its web-based "Wow Factor." The ability to type a prompt and instantly see a 3D building render in a browser is incredibly impressive for an FYP. Requiring evaluators to download Desktop software ruins that flow.
2. **Stick with your Custom IDF Generator (for now).** We *just* mathematically verified and fixed your custom `geometry_util.py` (including complex multi-zone origins and interior door mirroring). Throwing away custom code that works to learn a heavy new SDK right before delivery introduces massive scope risk. 
3. If you have extra time *after* everything is stable, we can refactor the backend to use the OpenStudio Python SDK to generate the IDF, while keeping Plotly in the frontend to visualize it.

## User Review Required

> [!IMPORTANT]
> **Decision 1: FastAPI + Ngrok**
> Are you ready to approve the implementation plan for removing Firebase and integrating FastAPI? We will start by building the Colab Python script first, then update the web dashboard.
>
> **Decision 2: OpenStudio vs Plotly**
> Do you agree with the recommendation to keep Plotly to preserve the web-based "Zero-Install" experience? Let me know if you strongly prefer abandoning the web viewer for the OpenStudio Desktop App, or if you want to rewrite the backend to use the OpenStudio SDK while keeping Plotly.
