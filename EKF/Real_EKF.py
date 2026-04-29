import numpy as np
import matplotlib.pyplot as plt

np.random.seed(0)

steps = 1000
dt = 1.0

# ---------------- TRUE PARAMETERS ----------------
true_params = np.array([
    0.05, 0.02, 0.5,   # α
    0.04, 0.015, 0.3,  # β
    0.02               # γ_e
])

# initial true states
T_true = 25
w_true = 0.010
c_true = 600

# storage
true_states = []
measurements = []

# ---------------- SIMULATE TRUE SYSTEM ----------------
for k in range(steps):

    # inputs (varying)
    T_o = 30 + 2*np.sin(0.05*k)
    w_o = 0.012
    c_o = 420

    T_sa = 18
    w_sa = 0.009
    c_sa = 420

    m_sa = 0.5 + 0.2*np.sin(0.1*k)
    N = 5 + 2*np.sin(0.03*k)

    αo, αs, αe, βo, βs, βe, γe = true_params

    # temperature
    T_true = T_true + dt * (
        -(αo + m_sa*αs)*T_true
        + αo*T_o
        + m_sa*αs*T_sa
        + αe
    )

    # humidity
    w_true = w_true + dt * (
        -(βo + m_sa*βs)*w_true
        + βo*w_o
        + m_sa*βs*w_sa
        + βe
    )

    # CO2
    c_true = c_true + dt * (
        -(βo + m_sa*βs)*c_true
        + βo*c_o
        + m_sa*βs*c_sa
        + γe*N
    )

    true_states.append([*true_params, T_true, w_true, c_true])

    # noisy measurements (only T, w, c)
    meas = [
        T_true + np.random.normal(0, 0.5),
        w_true + np.random.normal(0, 0.0005),
        c_true + np.random.normal(0, 20)
    ]

    measurements.append(meas)

# ---------------- EKF INIT ----------------
X_est = np.array([
    0.1, 0.01, 0.1,
    0.1, 0.01, 0.1,
    0.01,
    20, 0.008, 500
])

P = np.eye(10) * 1

Q = np.eye(10) * 0.001
R = np.diag([0.5, 0.0005, 20])

# H matrix
H = np.zeros((3,10))
H[0,7] = 1
H[1,8] = 1
H[2,9] = 1

I = np.eye(10)

# storage
estimates = []

# ---------------- EKF LOOP ----------------
for k in range(steps):

    T_o = 30 + 2*np.sin(0.05*k)
    w_o = 0.012
    c_o = 420

    T_sa = 18
    w_sa = 0.009
    c_sa = 420

    m_sa = 0.5 + 0.2*np.sin(0.1*k)
    N = 5 + 2*np.sin(0.03*k)

    αo, αs, αe = X_est[0], X_est[1], X_est[2]
    βo, βs, βe = X_est[3], X_est[4], X_est[5]
    γe = X_est[6]
    T, w, c = X_est[7], X_est[8], X_est[9]

    # -------- PREDICTION --------
    T_pred = T + dt * (
        -(αo + m_sa*αs)*T
        + αo*T_o
        + m_sa*αs*T_sa
        + αe
    )

    w_pred = w + dt * (
        -(βo + m_sa*βs)*w
        + βo*w_o
        + m_sa*βs*w_sa
        + βe
    )

    c_pred = c + dt * (
        -(βo + m_sa*βs)*c
        + βo*c_o
        + m_sa*βs*c_sa
        + γe*N
    )

    X_pred = X_est.copy()
    X_pred[7], X_pred[8], X_pred[9] = T_pred, w_pred, c_pred

    # -------- F matrix --------
    F = np.eye(10)

    F[7,0] = dt*(-T + T_o)
    F[7,1] = dt*m_sa*(-T + T_sa)
    F[7,2] = dt
    F[7,7] = 1 + dt*(-(αo + m_sa*αs))

    F[8,3] = dt*(-w + w_o)
    F[8,4] = dt*m_sa*(-w + w_sa)
    F[8,5] = dt
    F[8,8] = 1 + dt*(-(βo + m_sa*βs))

    F[9,6] = dt*N
    F[9,9] = 1 + dt*(-(βo + m_sa*βs))

    # covariance
    P = F @ P @ F.T + Q

    # -------- UPDATE --------
    Z = np.array(measurements[k])

    y = Z - H @ X_pred
    S = H @ P @ H.T + R
    K = P @ H.T @ np.linalg.inv(S)

    X_est = X_pred + K @ y
    P = (I - K @ H) @ P

    estimates.append(X_est.copy())

# ---------------- DERIVED PARAMETERS ----------------
c_pa = 1006
g_CO2_occ = 0.17

Cs_list = []
M_list = []
m_inf_list = []
UA_list = []
N_list = []

for X in estimates:
    alpha_o, alpha_s = X[0], X[1]
    beta_o, beta_s = X[3], X[4]
    gamma_e = X[6]

    # compute
    Cs = c_pa / alpha_s
    M = 1 / beta_s
    m_inf = beta_o * M
    UA = alpha_o * Cs - c_pa * m_inf
    N = (gamma_e * M) / g_CO2_occ

    Cs_list.append(Cs)
    M_list.append(M)
    m_inf_list.append(m_inf)
    UA_list.append(UA)
    N_list.append(N)
    
# convert to numpy arrays
true_states = np.array(true_states)
estimates = np.array(estimates)

# ---------------- PLOTS ----------------
fig, axs = plt.subplots(4,4, figsize=(14,10))
axs = axs.flatten()

# original 10 states
labels = [
    "α_o","α_s","α_e",
    "β_o","β_s","β_e",
    "γ_e",
    "T","ω","c"
]

for i in range(10):
    axs[i].plot(true_states[:,i], label="true")
    axs[i].plot(estimates[:,i], label="est")
    axs[i].set_title(labels[i])
    axs[i].legend()

# derived parameters
derived_data = [
    Cs_list, M_list, m_inf_list, UA_list, N_list
]

derived_labels = [
    "C_s", "M", "m_inf", "UA", "N"
]

for i in range(5):
    axs[10+i].plot(derived_data[i])
    axs[10+i].set_title(derived_labels[i])

# hide last subplot (16th)
axs[15].axis('off')

plt.tight_layout()
plt.show()
