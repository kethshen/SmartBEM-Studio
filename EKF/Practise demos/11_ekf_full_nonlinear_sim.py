import numpy as np
import matplotlib.pyplot as plt

np.random.seed(0)

steps = 200

# ---------------- TRUE SYSTEM ----------------
d_true = 1.0
v_true = 0.5

true_d = []
true_v = []
measurements = []

for _ in range(steps):
    d_true = d_true + np.sin(v_true)
    v_true = v_true + 0.1*np.cos(d_true)

    z = d_true**2 + np.sin(v_true) + np.random.normal(0, 0.5)

    true_d.append(d_true)
    true_v.append(v_true)
    measurements.append(z)

# ---------------- EKF INIT ----------------
X_prev = np.array([[0.0],
                   [0.0]])

P_prev = np.eye(2) * 10

Q = np.eye(2) * 0.1
R = np.array([[0.5]])

I = np.eye(2)

# storage
est_d, est_v = [], []
F_vals = []   # store [F11, F12, F21, F22]
H_vals = []   # store [H1, H2]

# ---------------- LOOP ----------------
for z in measurements:

    d_prev = X_prev[0,0]
    v_prev = X_prev[1,0]

    # -------- PREDICTION --------
    d_pred = d_prev + np.sin(v_prev)
    v_pred = v_prev + 0.1*np.cos(d_prev)

    X_pred = np.array([[d_pred],
                       [v_pred]])

    # Jacobian F
    F = np.array([
        [1, np.cos(v_prev)],
        [-0.1*np.sin(d_prev), 1]
    ])

    P_pred = F @ P_prev @ F.T + Q

    # -------- UPDATE --------
    z_pred = d_pred**2 + np.sin(v_pred)
    Z = np.array([[z]])

    # Jacobian H
    H = np.array([[2*d_pred, np.cos(v_pred)]])

    K = P_pred @ H.T @ np.linalg.inv(H @ P_pred @ H.T + R)

    X_est = X_pred + K @ (Z - np.array([[z_pred]]))
    P_est = (np.eye(2) - K @ H) @ P_pred

    # store
    est_d.append(X_est[0,0])
    est_v.append(X_est[1,0])

    F_vals.append([F[0,0], F[0,1], F[1,0], F[1,1]])
    H_vals.append([H[0,0], H[0,1]])

    X_prev = X_est
    P_prev = P_est

# ---------------- PLOT ----------------
fig, axs = plt.subplots(2, 2, figsize=(10, 8))

# d
axs[0,0].plot(true_d, label="True d")
axs[0,0].plot(est_d, label="EKF d_est")
axs[0,0].set_title("Distance")
axs[0,0].legend()

# v
axs[0,1].plot(true_v, label="True v")
axs[0,1].plot(est_v, label="EKF v_est")
axs[0,1].set_title("Velocity")
axs[0,1].legend()

# F elements
axs[1,0].plot([f[0] for f in F_vals], label="F11 = 1")
axs[1,0].plot([f[1] for f in F_vals], label="F12 = cos(v)")
axs[1,0].plot([f[2] for f in F_vals], label="F21 = -0.1*sin(d)")
axs[1,0].plot([f[3] for f in F_vals], label="F22 = 1")
axs[1,0].set_title("Jacobian F elements")
axs[1,0].legend()

# H elements
axs[1,1].plot([h[0] for h in H_vals], label="H1 = 2d")
axs[1,1].plot([h[1] for h in H_vals], label="H2 = cos(v)")
axs[1,1].set_title("Jacobian H elements")
axs[1,1].legend()

plt.tight_layout()
plt.show()