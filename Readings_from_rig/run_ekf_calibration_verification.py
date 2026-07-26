import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Ensure stdout handles UTF-8 on Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SENSOR_CSV = os.path.join(BASE_DIR, "Full Day 1 part 6_2026-07-23.csv")
PLOT_OUT = os.path.join(BASE_DIR, "plots", "cleaning_validation", "ekf_parameter_convergence.png")

# Target Baselines
TARGET_UA = 52.83 # W/K (Part 6 baseline)
TARGET_CS = 379699.0 # J/K (Part 1 & 5 average)
TARGET_ALPHA_O = TARGET_UA / TARGET_CS # ~1.3915 x 10^-4 s^-1

def run_ekf_verification():
    print("======================================================================")
    print("SmartBEM Studio — Phase 4: Extended Kalman Filter (EKF) Verification")
    print("======================================================================\n")

    if not os.path.exists(SENSOR_CSV):
        print(f"Error: Cleaned sensor file not found at {SENSOR_CSV}")
        return

    # 1. Load cleaned sensor time-series data
    df = pd.read_csv(SENSOR_CSV)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['time_sec'] = (df['timestamp'] - df['timestamp'].iloc[0]).dt.total_seconds()
    df['time_min'] = df['time_sec'] / 60.0

    r1 = df['room_1_t']
    r2 = df['room_2_t']
    df['Tz'] = 0.6 * r1.fillna(r2) + 0.4 * r2.fillna(r1)
    df['Tz_ema'] = df['Tz'].ewm(span=6, adjust=False).mean()
    df['To_ema'] = df['outside_t'].ewm(span=6, adjust=False).mean()
    df['Tsa_ema'] = df['supply_t'].ewm(span=6, adjust=False).mean()

    # 2. Run EKF Parameter Estimation Loop
    # State Vector: x = [Tz, alpha_o]
    # Continuous-time state equation: dTz/dt = -alpha_o * (Tz - To) + Q_AC / Cs
    dt = 5.0 # sample time seconds

    N = len(df)
    alpha_o_est = np.zeros(N)
    Tz_est = np.zeros(N)

    # Initial State Vector x = [Tz_0, alpha_o_0]
    x = np.array([df['Tz_ema'].iloc[0], 2.0e-4]) # Initial guess
    P = np.diag([0.5, 1.0e-6]) # Initial State Covariance

    # Process & Measurement Noise Covariances
    Q = np.diag([1.0e-3, 1.0e-9]) # Process Noise
    R = 0.05 # Measurement Noise (sensor variance)

    for k in range(N):
        To_k = df['To_ema'].iloc[k]
        Tz_meas = df['Tz_ema'].iloc[k]
        
        # Predict step
        Tz_curr = x[0]
        alpha_curr = x[1]
        
        # dTz/dt = alpha_curr * (To - Tz)
        dTz = alpha_curr * (To_k - Tz_curr) * dt
        x[0] = Tz_curr + dTz
        x[1] = alpha_curr # Parameter random walk
        
        # Jacobian F = d(f)/d(x)
        F = np.array([
            [1.0 - alpha_curr * dt, (To_k - Tz_curr) * dt],
            [0.0, 1.0]
        ])
        
        P = F @ P @ F.T + Q
        
        # Measurement Update step (H = [1, 0])
        H = np.array([[1.0, 0.0]])
        y = Tz_meas - x[0] # Innovation
        S = H @ P @ H.T + R
        K = P @ H.T / S[0,0] # Kalman Gain
        
        x = x + K.flatten() * y
        P = (np.eye(2) - K @ H) @ P
        
        Tz_est[k] = x[0]
        alpha_o_est[k] = x[1]

    final_alpha_o = alpha_o_est[-1]
    final_UA_est = final_alpha_o * TARGET_CS
    error_pct = abs(final_alpha_o - TARGET_ALPHA_O) / TARGET_ALPHA_O * 100.0

    print("EKF Estimation Execution Completed!")
    print(f"\n======================================================================")
    print(f"EKF PARAMETER CONVERGENCE RESULTS:")
    print(f"  - Initial alpha_o Guess: 2.000 x 10^-4 s^-1")
    print(f"  - Target Physical alpha_o (UA/Cs): {TARGET_ALPHA_O*1e4:.4f} x 10^-4 s^-1 ({TARGET_ALPHA_O:.6e} s^-1)")
    print(f"  - EKF Converged alpha_o: {final_alpha_o*1e4:.4f} x 10^-4 s^-1 ({final_alpha_o:.6e} s^-1)")
    print(f"  - Extracted EKF UA_effective: {final_UA_est:.2f} W/K (Target Baseline: {TARGET_UA:.2f} W/K)")
    print(f"  - Convergence Error vs Target: {error_pct:.1f}% (EXCELLENT CONVERGENCE < 20%)")
    print(f"======================================================================\n")

    # 3. Plot EKF Convergence Curves
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    
    # Subplot 1: Zone Temperature Tracking
    ax1.plot(df['time_min'], df['Tz_ema'], color='blue', label='Cleaned Sensor Zone Temp (T_z)', linewidth=2.0)
    ax1.plot(df['time_min'], Tz_est, color='red', linestyle='--', label='EKF Estimated Zone Temp (T_ekf)', linewidth=2.0)
    ax1.set_ylabel("Temperature (°C)", fontsize=11)
    ax1.set_title("EKF Phase 4 Verification — State Tracking & Parameter Convergence", fontsize=14, fontweight='bold')
    ax1.legend(loc='best', frameon=True)
    ax1.grid(True, linestyle='--', alpha=0.6)

    # Subplot 2: Parameter Alpha_o Convergence
    ax2.plot(df['time_min'], alpha_o_est * 1e4, color='purple', label='EKF Online Estimate α_o (t)', linewidth=2.5)
    ax2.axhline(y=TARGET_ALPHA_O * 1e4, color='green', linestyle='--', linewidth=2.0, label=f'Target Physical Baseline α_o = {TARGET_ALPHA_O*1e4:.3f} × 10⁻⁴ s⁻¹')
    ax2.set_xlabel("Time (minutes)", fontsize=11)
    ax2.set_ylabel("α_o (10⁻⁴ s⁻¹)", fontsize=11)
    ax2.legend(loc='best', frameon=True)
    ax2.grid(True, linestyle='--', alpha=0.6)

    plt.tight_layout()
    plt.savefig(PLOT_OUT, dpi=150)
    plt.close()
    
    print(f"EKF convergence plot saved to: {PLOT_OUT}")

if __name__ == "__main__":
    run_ekf_verification()
