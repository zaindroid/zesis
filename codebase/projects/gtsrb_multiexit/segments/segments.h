/*
 * Copyright 2026 NXP
 * SPDX-License-Identifier: BSD-3-Clause
 *
 * Three incremental NPU segments for the GTSRB multi-exit classifier.
 * segA/segB each have TWO outputs (exit logits + feature map for the next
 * segment); segC (final) has one (exit3 logits only). TFLite does not
 * preserve Python-side output declaration order through conversion, so
 * OutputLogits()/OutputFeatures() disambiguate by shape at runtime
 * (last dim == NUM_CLASSES => logits) rather than assuming a fixed index --
 * see model_segA.cpp/model_segB.cpp.
 */
#ifndef _SEGMENTS_H_
#define _SEGMENTS_H_

#include "tensorflow/lite/c/common.h"

bool SEGA_Init(void);
TfLiteStatus SEGA_Invoke(void);
TfLiteTensor* SEGA_Input(void);
TfLiteTensor* SEGA_OutputLogits(void);
TfLiteTensor* SEGA_OutputFeatures(void);

bool SEGB_Init(void);
TfLiteStatus SEGB_Invoke(void);
TfLiteTensor* SEGB_Input(void);
TfLiteTensor* SEGB_OutputLogits(void);
TfLiteTensor* SEGB_OutputFeatures(void);

bool SEGC_Init(void);
TfLiteStatus SEGC_Invoke(void);
TfLiteTensor* SEGC_Input(void);
TfLiteTensor* SEGC_OutputLogits(void);

#endif /* _SEGMENTS_H_ */
