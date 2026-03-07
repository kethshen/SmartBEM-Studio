# FYP – Intelligent HVAC Modeling, Estimation & Control

This repository contains my **Final Year Project (FYP)** work on intelligent HVAC systems using **EnergyPlus**, **Python**, and **EKF/AI-based estimation methods**.

The project focuses on:

* HVAC **simulation** using EnergyPlus
* **Online parameter estimation** (EKF) for zone thermal, moisture, and CO₂ dynamics
* A **web-based interface** for configuring buildings and visualizing results
* Experimental **validation using a single-zone lab test rig**

## Repository Structure (Current)

```
FYP/
│
├── README.md
│
├── notebooks/                  # Colab / Jupyter notebooks
│   ├── energyplus_setup.ipynb  # EnergyPlus installation & setup
│   ├── single_zone_sim.ipynb   # Single-zone EnergyPlus simulation
│
└── web/                        # Basic web UI (early stage)
    ├── index.html
    ├── style.css
    └── app.js
```

> Additional folders (EKF modules, IDF generators, Firebase configs, etc.) will be added **incrementally** as the project progresses.

---

## Tools & Technologies

* **EnergyPlus** (building energy simulation)
* **Python** (simulation control, data processing)
* **energy-plus-utility** (advisor-developed helper library)
* **Google Colab** (simulation and computation backend)
* **HTML / CSS / JavaScript** (web interface)
* **GitHub** (version control and collaboration)

---

## Author

**Kethaka Shehan** - Final Year Mechanical Engineering Undergraduate 

Supervisor: **Dr. D.H.S. Maithripala (@mugalan)** 

Faculty of Engineering, University of Peradeniya, Sri Lanka.
