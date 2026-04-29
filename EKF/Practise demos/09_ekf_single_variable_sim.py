import numpy as np
import matplotlib.pyplot as plt

np.random.seed(0)

steps = 100

# ---------------- TRUE SYSTEM ----------------
true_x = 2.0
true_values = []

for _ in range(steps):
    true_values.append(true_x)

# nonlinear measurements: z = x^2 + noise
measurements = [x**2 + np.random.normal(0, 0.5) for x in true_values]

# ---------------- EKF INIT ----------------
x_est = 0.5   # initial guess
P = 10

Q = 0.01
R = 0.5

estimates = []

# ---------------- LOOP ----------------
for z in measurements:

    # 🔵 Prediction
    x_pred = x_est
    P_pred = P + Q

    # 🔴 Jacobian of h(x) = x^2 → H = 2x
    H = 2 * x_pred

    # 🔴 Kalman Gain
    K = P_pred * H / (H * P_pred * H + R)

    # 🔴 Update
    x_est = x_pred + K * (z - x_pred**2)
    P = (1 - K * H) * P_pred

    estimates.append(x_est)

# ---------------- PLOT ----------------
plt.plot(true_values, label="True x")
plt.plot(estimates, label="EKF Estimate")
plt.title("EKF Estimating x from z = x^2")
plt.legend()
plt.show()