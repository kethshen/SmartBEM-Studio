# SmartHVAC-Studio: Next Steps & Roadmap

Now that the core pipeline is fully functional—from natural language input to multi-zone geometry generation, simulation, and web visualization—the foundation is solid. Here are several exciting directions we can take the project next, categorized by their focus area.

## 1. Advanced HVAC & Controls (High Impact)
Currently, we are using a fairly simple **Packaged Single Zone AC (PSZ-AC)** template. We can expand the AI's capabilities to select and configure more complex, realistic systems based on the user's prompt.

*   **Variable Air Volume (VAV) with Reheat:** Add support for a centralized VAV system. This is the standard for modern medium-to-large office buildings and handles multi-zone load variations much better than PSZ.
*   **Variable Refrigerant Flow (VRF):** Extremely popular in modern construction. We can add a VRF template for high-efficiency multi-zone conditioning.
*   **Fixing the DX Coil Frost Warning:** We can refine our current `psz_ac.idf` template by adding an **Air Economizer** or a **Low-Ambient Temperature Cutout**. This would stop the cooling coil from trying to run during winter blizzards and make the simulation more physically accurate.

## 2. Dynamic Operational Schedules (Medium Complexity)
Right now, the building's internal loads (Occupancy, Lighting, Equipment) are largely driven by generic "ALWAYS ON" or constant fraction schedules.

*   **NLP Schedule Parsing:** Upgrade the RAG/LLM prompt to extract operational hours (e.g., *"The office operates from 8 AM to 6 PM on weekdays, closed on weekends"*).
*   **Dynamic `Schedule:Compact` Generation:** The Python backend can dynamically write EnergyPlus schedules based on these extracted hours, leading to much more realistic energy consumption profiles (showing clear day/night and weekday/weekend drops in the graphs).

## 3. Enhanced Geometry & Multi-Story (High Complexity)
The geometry generator now handles side-by-side (1D/2D) multi-zone layouts flawlessly. The next evolution is full 3D complexity.

*   **Multi-Story Buildings:** Allow the AI to parse things like *"A two-story office building"*. We would need to update `geometry_util.py` to stack zones along the Z-axis and add floor/ceiling interior adjacencies.
*   **Pitched Roofs & Skylights:** Move beyond flat roofs by calculating geometries for pitched/gabled roofs.
*   **Window-to-Wall Ratios (WWR):** Let the user specify *"40% glazing on the South facade, 10% on the North"* and dynamically calculate window sizes and placements across the entire building.

## 4. Cost, Carbon, & Environmental Impact (High Value for Users)
EnergyPlus can do more than just calculate Watts and Joules; it can calculate money and carbon.

*   **Utility Tariffs (`UtilityCost:Tariff`):** Add basic electricity and gas cost structures to the simulation. We can plot the monthly/hourly operating cost in dollars.
*   **Carbon Emissions Reporting:** Map the electricity and gas usage to CO2 equivalent emissions and add a "Carbon Footprint" metric to the web dashboard.

## 5. Web UI Enhancements (Frontend Polish)
*   **Interactive 3D Viewer in the UI:** Instead of just a static link to `geometry.html`, embed the Plotly 3D geometry directly into the Vue.js dashboard using an `<iframe>` so users can spin the building around right next to the graphs.
*   **Zone-by-Zone Toggles:** Update the charts to allow the user to toggle specific zones on and off to compare them more easily.

---

### What do you think?
> [!QUESTION] 
> Which of these areas excites you the most? 
> - If you want a more accurate physical model, we should tackle **#1 (HVAC) or #2 (Schedules)**. 
> - If you want a more impressive visual output, **#3 (Multi-Story)** or **#5 (UI Enhancements)** would be best. 
> - If you want to pitch this as a green-tech tool, **#4 (Carbon)** is the way to go!
