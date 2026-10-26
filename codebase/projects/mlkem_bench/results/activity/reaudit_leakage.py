#!/usr/bin/env python3
"""Re-audit of the ML-KEM activity-leakage result (Experiment E0b).

The original figure was ~99.8% under random 5-fold cross-validation. That split
lets temporally adjacent pulses land on both sides of the train/test boundary,
which inflates accuracy for a physical trace: consecutive operations in one
capture look alike. This script reports the honest number under splits a real
attacker would actually face, plus a duration-only baseline (to check whether
the discriminator is the power envelope at all, or just that the operations take
different amounts of time).

Outputs results/activity/REAUDIT.json and prints a table.
"""
import json
import os

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.neural_network import MLPClassifier

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "REAUDIT.json")

envs = np.load(os.path.join(HERE, "envs_1024.npy"))     # (550, 256)
labels = np.load(os.path.join(HERE, "labels_1024.npy"))  # 0/1/2 = kp/enc/dec
durs = np.load(os.path.join(HERE, "durs_1024.npy"))

X = envs.astype(np.float64)
y = labels.astype(int)
res = {}

# --- 0. duration by class: is the leak just timing? ---
res["duration_ms_by_class"] = {
    str(int(c)): {"mean": round(float(durs[y == c].mean()), 2),
                  "min": round(float(durs[y == c].min()), 2),
                  "max": round(float(durs[y == c].max()), 2),
                  "std": round(float(durs[y == c].std()), 2)}
    for c in np.unique(y)
}

# --- 1. duration-only classifier (trivial baseline) ---
dmat = durs.reshape(-1, 1)
res["duration_only_cv"] = round(float(np.mean(
    cross_val_score(RandomForestClassifier(n_estimators=200, random_state=0),
                    dmat, y, cv=StratifiedKFold(5, shuffle=True, random_state=0)))), 4)

def zscore(a):
    return (a - a.mean(axis=1, keepdims=True)) / (a.std(axis=1, keepdims=True) + 1e-9)

def fit_eval(Xtr, ytr, Xte, yte, kind="rf"):
    if kind == "rf":
        m = RandomForestClassifier(n_estimators=300, random_state=0)
    else:
        m = MLPClassifier(hidden_layer_sizes=(128,), max_iter=2000, random_state=0)
    m.fit(Xtr, ytr)
    return float((m.predict(Xte) == yte).mean())

# --- 2. random 5-fold (what the original number used) ---
res["random_5fold_shape"] = round(float(np.mean(
    cross_val_score(RandomForestClassifier(n_estimators=300, random_state=0),
                    X, y, cv=StratifiedKFold(5, shuffle=True, random_state=0)))), 4)

# --- 3. temporal split: train on the first 70% of the capture, test on the last 30% ---
n = len(y)
cut = int(n * 0.70)
res["temporal_70_30"] = round(fit_eval(X[:cut], y[:cut], X[cut:], y[cut:]), 4)

# --- 4. blocked 5-fold: contiguous blocks, so no neighbour leakage ---
blk = 5
order = np.arange(n)
folds = np.array_split(order, blk)
accs = []
for f in folds:
    te = f
    tr = np.setdiff1d(order, te)
    accs.append(fit_eval(X[tr], y[tr], X[te], y[te]))
res["blocked_5fold"] = round(float(np.mean(accs)), 4)
res["blocked_5fold_folds"] = [round(a, 4) for a in accs]

# --- 5. middle-50% (drop the leading/trailing edges) ---
mid = X[:, 64:192]
res["middle50_random_5fold"] = round(float(np.mean(
    cross_val_score(RandomForestClassifier(n_estimators=300, random_state=0),
                    mid, y, cv=StratifiedKFold(5, shuffle=True, random_state=0)))), 4)
res["middle50_temporal"] = round(fit_eval(mid[:cut], y[:cut], mid[cut:], y[cut:]), 4)

# --- 6. z-scored shape only (remove amplitude) ---
Z = zscore(X)
res["zscored_shape_temporal"] = round(fit_eval(Z[:cut], y[:cut], Z[cut:], y[cut:]), 4)
res["zscored_shape_random"] = round(float(np.mean(
    cross_val_score(RandomForestClassifier(n_estimators=300, random_state=0),
                    Z, y, cv=StratifiedKFold(5, shuffle=True, random_state=0)))), 4)

# --- 7. MLP for comparison with the original CNN claim ---
res["mlp_temporal"] = round(fit_eval(X[:cut], y[:cut], X[cut:], y[cut:], "mlp"), 4)
res["mlp_random"] = round(float(np.mean(
    cross_val_score(MLPClassifier(hidden_layer_sizes=(128,), max_iter=2000, random_state=0),
                    X, y, cv=StratifiedKFold(5, shuffle=True, random_state=0)))), 4)

with open(OUT, "w") as f:
    json.dump(res, f, indent=1)

print(f"n = {n} pulses, 256-sample envelopes, {len(np.unique(y))} classes")
print()
print(f"duration-only classifier (trivial)        random CV : {res['duration_only_cv']:.3f}")
print(f"shape, RandomForest                       random CV : {res['random_5fold_shape']:.3f}   <- the original claim")
print(f"shape, RandomForest                    temporal 70/30: {res['temporal_70_30']:.3f}   <- honest")
print(f"shape, RandomForest                     blocked 5-fold: {res['blocked_5fold']:.3f}   <- honest")
print(f"shape, MLP                                random CV : {res['mlp_random']:.3f}")
print(f"shape, MLP                             temporal 70/30: {res['mlp_temporal']:.3f}")
print(f"middle-50% only                           random CV : {res['middle50_random_5fold']:.3f}")
print(f"middle-50% only                        temporal 70/30: {res['middle50_temporal']:.3f}")
print(f"z-scored shape (amplitude removed)        random CV : {res['zscored_shape_random']:.3f}")
print(f"z-scored shape (amplitude removed)     temporal 70/30: {res['zscored_shape_temporal']:.3f}")
print()
print("durations by class (ms):")
for k, v in res["duration_ms_by_class"].items():
    print(f"  class {k}: mean {v['mean']:7.2f}  min {v['min']:7.2f}  max {v['max']:7.2f}")
print()
print("wrote", OUT)
