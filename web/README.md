# SmartBEM Studio — Web Dashboard

This directory contains the entire user interface for **SmartBEM Studio** — a client-side dashboard for building modeling, thermal simulation control, and parameter estimation visualization.

## Technologies Used
- **Structure:** Semantic HTML5
- **Styling:** Vanilla CSS (structured around design system variables in `design_system.css` and global styling in `style.css`)
- **Logic:** Vanilla JavaScript (modular ES6 modules for communications, UI behavior, and calculations)
- **Visuals:** Plotly.js for interactive time-series charts, and three.js/OrbitControls (incorporated via visualizer integrations) for rendering 3D building geometry.

## Key Features
1. **Simulation Setup (`pages/nlp.html`):** A natural language interface to describe buildings, select weather stations, choose AI models, and trigger simulation runs.
2. **Results Viewer (`pages/results.html`):** Displays interactive Plotly charts of zone temperatures, heat gains/losses, HVAC electricity consumption, and ambient weather.
3. **EKF Dashboard (`pages/ekf.html`):** UI component to track the status of Extended Kalman Filter parameter estimation.
4. **IDF Diff Viewer (`pages/diff_viewer.html`):** Renders a line-by-line comparison between the template base file and the AI-generated building configuration.
5. **System Status Monitor:** Verifies connectivity to the FastAPI Colab backend server.

## Local Execution
The dashboard is designed as a standalone static web application. It does not require compilation or database hosting on the user's end:

### Method A: Direct File Execution (Zero Setup)
Simply double-click [web/index.html](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/web/index.html) to open the application directly in any modern web browser.

### Method B: Local HTTP Server (Recommended)
To prevent CORS issues with certain advanced browser features, you can run a lightweight local server:
```bash
# Python 3
python -m http.server 8000
```
Then visit: `http://localhost:8000` in your web browser.

---
*Note: The frontend operates purely as a client. It communicates with the EnergyPlus + Ollama simulator backend via a secure Ngrok tunnel URL.*
