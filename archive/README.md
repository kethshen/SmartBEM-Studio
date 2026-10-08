# archive/

Finished or parked SmartBEM Studio work, kept for the record. Not part of the
current research direction (multi-agent decentralized control), so nothing here
is maintained.

| Folder | What it is | Moved from |
|---|---|---|
| `EKF/` | Extended Kalman Filter work: ROBOD and test-rig estimators, datasets, notes | `EKF/` (repo root) |
| `Experimental_Rig_Calibration/` | Test-rig calibration runs v1–v5, sensor readings, scripts, photos and CAD | `Experimental_Rig_Calibration/` (repo root) |
| `fyp-submission/` | Final year project report (LaTeX in `report/`), poster files in `poster/`, and the submitted PDFs `E20028_ES71.pdf` and `E20028_ES83.pdf` | `Final Demo/` |

The whole FYP as submitted is also tagged in git as `fyp-final`.

## Code that still points at the old locations

These paths were not updated, because the features are parked. Fix them if the
work is ever revived.

- `backend_server/core/fastapi_server.py:181` imports `EKF.Real_EKF_ROBOD`.
  That file was already deleted in commit `34da3ab`, so the EKF job failed before
  this move too. Restore with `git show 34da3ab^:EKF/Real_EKF_ROBOD.py`.
- `backend_server/core/fastapi_server.py:282` and the calibration cell in
  `backend_server/main_backend.ipynb` default to
  `Experimental_Rig_Calibration/calibrated_v3_dynamic_supply_controls`.
  The calibration job needs that folder passed in explicitly now.
- `web/pages/ekf.html` (lines 470 and 700) loads static results from
  `../../EKF/results*`. Those folders did not exist before the move either.
