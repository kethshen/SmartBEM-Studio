import pandas as pd
import numpy as np

ROBOD_DIR = (r'd:\UNI\Sem 7\ME420 Mech Eng Research Project\SmartBEM-Studio'
             r'\EKF\Datasets for EKF\ROBOD, Room level Occupancy and Building Operation Dataset')

files = {
    1: 'combined_Room1.csv',
    2: 'combined_Room2.csv',
    3: 'combined_Room3.csv',
    4: 'combined_Room4.csv',
    5: 'combined_Room5.csv',
}

print(f"{'Room':<6} {'Occ%':<7} {'CO2_occ':<10} {'CO2_unocc':<12} {'CO2_out':<10} {'Lift':<10} {'Signal?'}")
print("-"*70)
for room in [1, 2, 3, 4, 5]:
    try:
        df = pd.read_csv(f'{ROBOD_DIR}/{files[room]}').ffill().bfill()
        occ = df['occupant_count [number]'].values
        cz  = df['indoor_co2 [ppm]'].values
        co  = df['outdoor_co2 [ppm]'].values
        occ_mask   = occ > 0
        unocc_mask = occ == 0
        mean_occ   = cz[occ_mask].mean()   if occ_mask.sum()   > 0 else 0
        mean_unocc = cz[unocc_mask].mean() if unocc_mask.sum() > 0 else 0
        co2_lift   = mean_occ - mean_unocc
        signal     = "YES" if co2_lift > 30 else "WEAK" if co2_lift > 10 else "NO"
        print(f"Room {room:<2} {100*occ_mask.mean():<7.1f} {mean_occ:<10.1f} {mean_unocc:<12.1f} {co.mean():<10.1f} {co2_lift:<10.1f} {signal}")
    except Exception as e:
        print(f"Room {room}: ERROR {e}")
