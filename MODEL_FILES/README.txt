MODEL_FILES - the trained GTSRB multi-exit model
================================================
Copied 2026-10-09 from codebase/training_archive/training/
Total 11 MB. All files verified intact (TFLite TFL3 magic / HDF5 magic).

THE MODEL IN ONE LINE
---------------------
3-exit MobileNetV1-flavoured backbone, 48x48x3 input, 43 GTSRB classes,
exits at exactly 30% / 60% / 100% of block depth (blocks 3, 6, 10),
stage widths 16 -> 32 -> 40 -> 176, INT8 per-channel quantised.
Trained 100 epochs, seed 20260728, batch 128, lr 0.001,
loss = sum_k CE(exit_k) with equal weights.

BEST VALIDATION ACCURACY
------------------------
  exit1  0.733      exit2  0.923      exit3  0.931
  single-exit baseline control:       0.945
  (so joint multi-exit training costs the final exit ~1.4 points)

WHAT TO OPEN
------------

1) tflite_segments/  <-- START HERE
   Self-contained: architecture + weights + quantisation parameters in one file.
   This is the deployed form; runs on the device with TFLite Micro.
     segA_int8.tflite   16,736 B   exit 1 (stage A only)
     segB_int8.tflite   21,168 B   stage B (runs after A)
     segC_int8.tflite  125,896 B   stage C (runs after B)
   Any TFLite viewer can open these. No other file needed.

2) tflite_per_exit/
   Cumulative per-exit exports, if you want a model that reaches a given exit
   in one file rather than chained segments:
     exit1_int8.tflite   17,848 B   = segA
     exit2_int8.tflite   35,696 B   = segA + segB
     exit3_int8.tflite  158,144 B   = full 3-exit model

3) keras_weights_multiexit/  <-- the training output
     best_joint.weights.h5                 <-- THE SELECTED CHECKPOINT
                                               (MaxOfMin epoch 95: protects the
                                                weakest exit, not the average)
     best.weights.h5
     best_exit3_epoch71.weights.h5
     best_exit3_frozen_epoch_NA.weights.h5
     final.weights.h5

   IMPORTANT: these are PARAMETERS ONLY - no architecture is stored inside.
   There is no .keras or full-model .h5 anywhere in the project. To load one
   you must rebuild the graph first:

       from models.architectures import <factory>       # see architectures.py
       m = <factory>()                                  # same architecture
       m.load_weights("keras_weights_multiexit/best_joint.weights.h5")

   architectures.py is included here for that reason.

4) keras_weights_baseline/
   The control model: identical backbone, single final exit, single
   cross-entropy. Different architecture from the multi-exit files above.

5) Supporting evidence
     quantize_accuracy_report.csv   FP32 -> INT8 accuracy drop per exit
     quant_params.json              per-tensor scale / zero-point
     multiexit.yaml, baseline.yaml  the exact training configurations
     architectures.py               the model definition

QUANTISATION COST (why the INT8 numbers are trustworthy)
--------------------------------------------------------
     exit   FP32 acc   INT8 acc   drop
     exit1   0.7361     0.7349    +0.12 pp
     exit2   0.9246     0.9215    +0.31 pp
     exit3   0.9326     0.9308    +0.19 pp

NOT IN HERE
-----------
The conformal thresholds (tau per exit/alpha) are computed from the
calibration split, not from these files:
  training/results/conformal_tau_table.csv
  training/results/coverage_validation_table.csv

The firmware-embedded copies of these same models (as C byte arrays) live in:
  projects/gtsrb_multiexit_esp32s3/main/models/seg{A,B,C}_model_data.h
  projects/gtsrb_policy_freerun/segments/model_data_seg{A,B,C}.h
