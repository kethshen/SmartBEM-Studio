# Utilities & Plotting Tools Overview

This folder contains supporting **Python utility modules and visualization scripts** for IDF parsing, statistical error evaluation against ASHRAE Guideline 14 standards, and experimental vs. simulation plot rendering.

---

## 📋 Script Reference & Detailed Code Functions

### 1. [`ashrae_metrics_calculator.py`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/scripts/utils_and_plotting/ashrae_metrics_calculator.py)
* **Objective:** Computes standard statistical accuracy metrics between simulated and measured zone thermal trajectories.
* **Code Implementation:**
  * **Coefficient of Variation of Root Mean Square Error (CV(RMSE)):**
    $$\text{CV(RMSE)} = \frac{1}{\bar{y}} \sqrt{\frac{\sum_{i=1}^N (y_i - \hat{y}_i)^2}{N - p}} \times 100\%$$
  * **Normalized Mean Bias Error (NMBE):**
    $$\text{NMBE} = \frac{\sum_{i=1}^N (y_i - \hat{y}_i)}{(N - p) \cdot \bar{y}} \times 100\%$$
  * **Root Mean Square Error (RMSE):**
    $$\text{RMSE} = \sqrt{\frac{1}{N} \sum_{i=1}^N (y_i - \hat{y}_i)^2}$$
  * **Mean Absolute Error (MAE):**
    $$\text{MAE} = \frac{1}{N} \sum_{i=1}^N |y_i - \hat{y}_i|$$
  * **Coefficient of Determination ($R^2$):**
    $$R^2 = 1 - \frac{\sum (y_i - \hat{y}_i)^2}{\sum (y_i - \bar{y})^2}$$
  * Automatically evaluates whether calculated metrics satisfy **ASHRAE Guideline 14 thresholds** ($\text{CV(RMSE)} \le 5.0\%$, $|\text{NMBE}| \le 2.0\%$).

### 2. [`idf_parser_utils.py`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/scripts/utils_and_plotting/idf_parser_utils.py)
* **Objective:** Provides programmatic parsing and text manipulation functions to inspect and edit EnergyPlus `.idf` files without manual editing.
* **Code Implementation:**
  * Uses regex pattern matching to extract `Material`, `Construction`, `ZoneInfiltration:DesignFlowRate`, and `RunPeriod` blocks.
  * Replaces parameter field values (such as thermal conductivity $k$, density $\rho$, specific heat $c_p$, infiltration $\text{ACH}$) programmatically during optimization loops.
  * Validates IDF block syntax before saving updated files.

### 3. [`plot_sim_vs_experimental.py`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/scripts/utils_and_plotting/plot_sim_vs_experimental.py)
* **Objective:** Generates publication-quality comparison overlay plots comparing EnergyPlus simulated zone temperatures ($T_{\text{sim}}$) against experimental sensor readings ($T_z$).
* **Code Implementation:**
  * Aligns simulation timestep outputs with experimental timestamps onto a single time-axis in minutes.
  * Plots simulated temperature $T_{\text{sim}}$ (solid line) against spatial weighted sensor temperature $T_z$ (dashed line).
  * Computes and displays real-time CV(RMSE), NMBE, and RMSE text boxes directly on the figure legend.

### 4. [`plot_multitake_timeseries.py`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/scripts/utils_and_plotting/plot_multitake_timeseries.py)
* **Objective:** Stitches together multiple sequential experimental takes recorded across a full test day into a continuous time-series figure.
* **Code Implementation:**
  * Concatenates individual dataset CSV files (e.g. `day_2_p_1.csv` through `day_2_p_4.csv`) while maintaining correct elapsed time offsets.
  * Renders continuous multi-channel plots (Temperature, Relative Humidity, CO$_2$, Supply Fan Speed) across multi-hour experimental campaigns.
