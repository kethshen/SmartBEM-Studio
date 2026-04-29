import numpy as np
import matplotlib.pyplot as plt

np.random.seed(0)
steps = 200

# ---------------- TRUE SYSTEM ----------------
X_true = np.array([25.0, 60.0, 400.0, 2.0])

true_states = []
measurements = []

for _ in range(steps):

    temp, humid, CO2, occ = X_true

    # nonlinear system
    temp  = temp + 0.05*np.sin(occ)
    humid = humid + 0.03*np.cos(temp)
    CO2   = CO2 + 0.5*occ + 0.1*np.sin(humid)
    occ   = occ + 0.05*np.sin(CO2)

    X_true = np.array([temp, humid, CO2, occ])

    # measurements (only temp & humidity)
    z = np.array([
        temp + np.random.normal(0, 0.5),
        humid + np.random.normal(0, 1.0)
    ])

    true_states.append(X_true.copy())
    measurements.append(z)

# ---------------- EKF INIT ----------------
X_prev = np.array([[20.0],
                   [50.0],
                   [350.0],
                   [1.0]])

P_prev = np.eye(4) * 10

Q = np.eye(4) * 0.1
R = np.diag([0.5, 1.0])

H = np.array([
    [1,0,0,0],
    [0,1,0,0]
])

I = np.eye(4)

est_states = []

# ---------------- LOOP ----------------
for z in measurements:

    temp, humid, CO2, occ = X_prev.flatten()

    # -------- PREDICTION --------
    temp_p  = temp + 0.05*np.sin(occ)
    humid_p = humid + 0.03*np.cos(temp)
    CO2_p   = CO2 + 0.5*occ + 0.1*np.sin(humid)
    occ_p   = occ + 0.05*np.sin(CO2)

    X_pred = np.array([[temp_p],
                       [humid_p],
                       [CO2_p],
                       [occ_p]])

    # -------- JACOBIAN F --------
    F = np.array([
        [1, 0, 0, 0.05*np.cos(occ)],
        [-0.03*np.sin(temp), 1, 0, 0],
        [0, 0.1*np.cos(humid), 1, 0.5],
        [0, 0, 0.05*np.cos(CO2), 1]
    ])

    P_pred = F @ P_prev @ F.T + Q

    # -------- UPDATE --------
    Z = z.reshape(2,1)

    K = P_pred @ H.T @ np.linalg.inv(H @ P_pred @ H.T + R)

    X_est = X_pred + K @ (Z - H @ X_pred)
    P_est = (I - K @ H) @ P_pred

    est_states.append(X_est.flatten())

    X_prev = X_est
    P_prev = P_est

# ---------------- PLOT ----------------
true_states = np.array(true_states)
est_states = np.array(est_states)

labels = ["Temp", "Humidity", "CO2", "Occupancy"]

fig, axs = plt.subplots(2,2, figsize=(10,8))

for i, ax in enumerate(axs.flat):
    ax.plot(true_states[:,i], label="True")
    ax.plot(est_states[:,i], label="EKF")
    ax.set_title(labels[i])
    ax.legend()

plt.tight_layout()
plt.show()