# Safety-critical class subset

Used as the "must-not-miss" class set for the conformal risk bound in
`conformal/calibrate.py` (Brief 3): the empirical miss-rate constraint
`(n*Rhat+1)/(n+1) <= alpha` is evaluated specifically over these classes,
since a missed/misclassified prohibitory or danger sign has direct safety
consequences (running past a "no entry", missing a "slippery road" warning),
whereas e.g. confusing "keep left" vs "keep right" mandatory-direction signs
or two speed-limit values off by one bucket, while still an error, is a
lower-severity failure mode for the certified-anytime-exit argument this
thesis is making.

## Source of the grouping

Classes are grouped using the standard 4-superclass taxonomy from the German
Traffic Sign Detection Benchmark (Houben, S., Stallkamp, J., Salmen, J.,
Schlipsing, M., Igel, C., "Detection of Traffic Signs in Real-World Images:
The German Traffic Sign Detection Benchmark", IJCNN 2013), which partitions
the same 43 GTSRB classes into `prohibitory`, `danger`, `mandatory`, `other`.
This grouping is widely reused in the GTSRB/GTSDB literature and is the
standard reference for "which GTSRB classes are prohibitory/danger signs".

The brief specifies **prohibitory + danger**. Taken together that's 27 of
the 43 classes.

## prohibitory (12 classes) -- circular, red border, numeric/vehicle-class restriction

| ID | Sign |
|----|------|
| 0  | Speed limit (20km/h) |
| 1  | Speed limit (30km/h) |
| 2  | Speed limit (50km/h) |
| 3  | Speed limit (60km/h) |
| 4  | Speed limit (70km/h) |
| 5  | Speed limit (80km/h) |
| 7  | Speed limit (100km/h) |
| 8  | Speed limit (120km/h) |
| 9  | No passing |
| 10 | No passing for vehicles over 3.5 metric tons |
| 15 | No vehicles |
| 16 | Vehicles over 3.5 metric tons prohibited |

## danger (15 classes) -- triangular, red border, hazard warning

| ID | Sign |
|----|------|
| 11 | Right-of-way at the next intersection |
| 18 | General caution |
| 19 | Dangerous curve to the left |
| 20 | Dangerous curve to the right |
| 21 | Double curve |
| 22 | Bumpy road |
| 23 | Slippery road |
| 24 | Road narrows on the right |
| 25 | Road work |
| 26 | Traffic signals |
| 27 | Pedestrians |
| 28 | Children crossing |
| 29 | Bicycles crossing |
| 30 | Beware of ice/snow |
| 31 | Wild animals crossing |

## Explicit ID list (for code)

```python
SAFETY_CRITICAL_CLASS_IDS = [
    0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 15, 16,   # prohibitory
    11, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31,  # danger
]
```

## Boundary judgment call (documented, not silently excluded)

Classes 12 (priority road), 13 (yield), 14 (stop), and 17 (no entry) fall
under the GTSDB `other` superclass, not `prohibitory`/`danger`, and are
therefore **excluded** from `SAFETY_CRITICAL_CLASS_IDS` per the brief's
literal "prohibitory + danger" scope -- even though a missed Stop or Yield
sign is intuitively also safety-critical. If the thesis later wants a
stricter bound covering those too, extend the list explicitly (e.g. a
second `SAFETY_CRITICAL_CLASS_IDS_STRICT` including 12/13/14/17) rather than
silently redefining this one, since the conformal calibration results are
keyed to this exact set.

Excluded entirely: `mandatory` (33-40, direction/action signs) and the
remaining `other` classes (6, 32, 41, 42 -- de-restriction signs) and all
non-superclass-grouped IDs not listed above.
