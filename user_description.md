Simulate a building with two nested zones: a outer Hanger and an inner Chamber test rig.

The Hanger is 80.00 meters long (East-West), 18.00 meters wide (North-South), and 6.00 meters high at the side walls. The Hanger has a gable roof with an East-West ridge line and a pitch height of 2.30 meters (total peak height 8.30 meters). The Hanger walls are 250mm thick composite masonry according to Sri Lanka Standards (SLS 855), constructed from a 220mm brick core with 15mm cement plaster coatings on both inner and outer surfaces. The long side walls (North and South) feature a series of large windows, each 1.00 meter wide by 3.00 meters high. The Hanger floor is a 200mm heavyweight concrete slab on ground. The Hanger zone uses an Ideal Loads air system.

The Chamber is a sealed cold room box located inside the Hanger, positioned at a 3.00 meter offset from the Hanger long wall and a 40.00 meter offset from the short Hanger wall. The Chamber has outside dimensions of 2.00 meters long (East-West), 2.00 meters wide (North-South), and 2.00 meters high.

All 6 surfaces of the Chamber (North, South, East, West walls, ceiling, and floor) are fully enclosed interior surfaces located inside the Hanger zone. The Outside Boundary Condition for all 6 Chamber surfaces is set to the Hanger zone — with zero direct solar or wind exposure.

All 6 surfaces of the Chamber are constructed using the custom material 'Custom_PU_Foam' with a panel thickness of 0.10 meters (100mm rigid polyurethane foam, thermal conductivity k = 0.08 W/m-K, density rho = 100 kg/m3, specific heat Cp = 1543 J/kg-K).

The Chamber is conditioned by an Air Handling Unit (AHU) system consisting of a supply main blower fan, cooling coil, heating coil, humidifier, and mixing damper. The AHU operates with 100% recirculated return air from the Chamber (0% fresh air intake damper opening) and maintains a cooling setpoint of 16.0 degrees Celsius. The Chamber zone infiltration rate is set to 12.5 Air Changes per Hour (ACH).

The Chamber has zero occupancy, zero internal lighting loads, and 1.0 Watt background equipment heat load (ESP32 micro-controller).



here is the correct details of the hanger and chamber. hanger is 80m x 18m x 6m. the 6m height is wall height without roof pitch height. it wllas made of 220mm brick + out and inside cment plaster layer totalling a 250mm wall thickness, floor is 200mm concrete. roof is gable type a steel structure support with asbestoes roof panels (15mm thickness). there is a abbestoes 10mm thickness ceiling belof roof with 15cm air gap between roof layer and ceiling layer.

its oriented at like this 

its long side walls has window groups. one group think of it as a vertical column starting from the ground 1.2m wall then 1.1m widthx2.1m height window, then 35cm wall then another 1.1m x 1.4m window. then 35cm wall. so total added upto 5.4m. theen there is a free opening of 0.6m. so totoal wall height of hanger is 6m.

long side wall has support concrte vertical columns of 60cmx60cm. between those 2 column that has 4 set of above windos group. those groups seperated at by 20cm. so its like 60cm column+ 20cm wall + 1.1m window group + 20cm wall + 1.1m window group  + 20cm wall + 1.1m window group +20cm wall + 1.1m window group + 20cm wall + 1.1m window group + 60cm column likvise it repeats upto lobbby area. in lobby are there aren't such windows, only walls.

inside hanger as given in the rough draft the chamber is located inside the hanger with other rooms. (do we really need them or shall we remove them?) all the dimensions avaliable in this drawing. rough dimensions.