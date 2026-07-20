Simulate a building with two zones: a Hanger and a Chamber.

The Hanger is 80.00 meters long (East-West), 17.00 meters wide (North-South), and 12.00 meters high. The Hanger has a gable roof with the ridge running East-West, gable height 12 meters. The gable roof is made of the custom material 'Hanger_Roof_Asbestos', which is a 3.2mm thick asbestos-cement corrugated sheet (thermal conductivity 0.58 W/m-K, density 1900 kg/m3, specific heat 1000 J/kg-K). The four Hanger walls are made of 'M01 100mm brick'. The Hanger floor is made of 'M15 200mm heavyweight concrete'. The Hanger uses Ideal Loads air system.

The Chamber is a sealed cold room box located inside the Hanger, positioned at the centre of the Hanger floor plan: its South-West corner is at X=39.00m, Y=7.50m from the Hanger origin. The Chamber is 2.00 meters long (East-West), 2.00 meters wide (North-South), and 2.00 meters high.

All 6 surfaces of the Chamber are interior surfaces that are fully enclosed by the Hanger zone. The Outside Boundary Condition for all Chamber walls (North, South, East, West), Chamber floor, and Chamber ceiling must be set to the Hanger zone — not Outdoors and not Ground. There is no sun exposure or wind exposure on any Chamber surface.

The Chamber walls (all four sides) and Chamber ceiling are made of a single-layer construction using the custom material 'Chamber_PU_Foam', which is a 100mm thick rigid polyurethane foam panel (thermal conductivity 0.022 W/m-K, density 32 kg/m3, specific heat 1500 J/kg-K). The Chamber floor is also made of the same 'Chamber_PU_Foam' construction.

The Chamber is cooled by a split AC unit (split_ac) with a thermostat setpoint of 16 degrees Celsius for cooling and 18 degrees Celsius for heating.

There are no windows or doors on any Chamber surface.

The occupancy rate is 0 people (unoccupied cold room). The lighting level is 0 W/m2. There is no equipment load inside the Chamber.