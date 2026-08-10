#!/usr/bin/env python3
"""Option A (reframed): learned crypto-op classifier from PPK2 power envelopes.

Trains classifiers to identify WHICH ML-KEM-1024 operation (keypair/encaps/
decaps) is running from the 10 kHz PPK2 power envelope alone (256-point
resampled per-pulse signature). sklearn models (546 samples is too small for
a deep CNN; RF/MLP are honest learned baselines).

Critical design: features are the SHAPE-ONLY envelope (z-scored per pulse:
mean removed, std normalized), so the classifier must learn from the power
signature shape, NOT from duration or absolute current level. This isolates
the actual activity-leakage signal.

Key-recovery SCA is out of scope (PPK2 10 kHz too coarse; A_FEASIBILITY.md).
This is the operational-activity leakage finding.
"""
import numpy as np
import os
from collections import Counter

RESULTS = os.path.join(os.path.dirname(__file__), "results", "activity")

envs = np.load(os.path.join(RESULTS, "envs_1024.npy"))
durs = np.load(os.path.join(RESULTS, "durs_1024.npy"))
labels = np.load(os.path.join(RESULTS, "labels_1024.npy"))

# drop the 4 outliers
good = (durs >= 45) & (durs <= 72)
envs, labels, durs = envs[good], labels[good], durs[good]
print(f"samples: {len(envs)} | labels: {np.bincount(labels)}")

# shape-only features: z-score each envelope (remove baseline & scale)
X = (envs - envs.mean(axis=1, keepdims=True)) / (envs.std(axis=1, keepdims=True) + 1e-9)
y = labels

# train/test split by index (no shuffle leakage)
n_train = int(len(X) * 0.75)
Xtr, ytr = X[:n_train], y[:n_train]
Xte, yte = X[n_train:], y[n_train:]
durs_te = durs[n_train:]
print(f"train {len(Xtr)}, test {len(Xte)}")

from sklearn.ensemble import RandomForestClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import accuracy_score, confusion_matrix

models = {
    "RandomForest(shape-only)": RandomForestClassifier(n_estimators=400, random_state=42, class_weight="balanced"),
    "MLP(shape-only)": MLPClassifier(hidden_layer_sizes=(128, 64), max_iter=1000, random_state=42),
}

print("\n=== Results ===")
for name, m in models.items():
    m.fit(Xtr, ytr)
    pred = m.predict(Xte)
    acc = accuracy_score(yte, pred)
    print(f"\n{name}: test acc = {acc:.3f}")
    print(f"  confusion (rows=true keypair/encaps/decaps):")
    print(confusion_matrix(yte, pred))

# baselines
# 1) duration-only threshold classifier
dur_pred = np.where(durs_te < 54, 0, np.where(durs_te < 62, 1, 2))
print(f"\nbaseline duration-only: {accuracy_score(yte, dur_pred):.3f}")
# 2) majority class
maj = Counter(yte).most_common(1)[0][0]
print(f"baseline majority-class: {accuracy_score(yte, [maj]*len(yte)):.3f}")

# feature importance (RF): which time-points in the envelope matter most
rf = models["RandomForest(shape-only)"]
imp = rf.feature_importances_
top5 = np.argsort(imp)[-5:]
print(f"\nRF top-5 envelope time-points (of 256): {sorted(top5)} (relative pos {[round(i/256,2) for i in sorted(top5)]})")
print("\nDONE")
