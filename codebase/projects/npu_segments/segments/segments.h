/*
 * Copyright 2026 NXP
 * SPDX-License-Identifier: BSD-3-Clause
 */
#ifndef _SEGMENTS_H_
#define _SEGMENTS_H_

#include "tensorflow/lite/c/common.h"

bool MONO_Init(void);
TfLiteStatus MONO_Invoke(void);
TfLiteTensor* MONO_Input(void);
TfLiteTensor* MONO_Output(void);

bool SEGAB_Init(void);
TfLiteStatus SEGAB_Invoke(void);
TfLiteTensor* SEGAB_Input(void);
TfLiteTensor* SEGAB_Output(void);

bool SEGA_Init(void);
TfLiteStatus SEGA_Invoke(void);
TfLiteTensor* SEGA_Input(void);
TfLiteTensor* SEGA_Output(void);

bool SEGB_Init(void);
TfLiteStatus SEGB_Invoke(void);
TfLiteTensor* SEGB_Input(void);
TfLiteTensor* SEGB_Output(void);

bool SEGC_Init(void);
TfLiteStatus SEGC_Invoke(void);
TfLiteTensor* SEGC_Input(void);
TfLiteTensor* SEGC_Output(void);

bool SEGC1_Init(void);
TfLiteStatus SEGC1_Invoke(void);
TfLiteTensor* SEGC1_Input(void);
TfLiteTensor* SEGC1_Output(void);

bool SEGC2_Init(void);
TfLiteStatus SEGC2_Invoke(void);
TfLiteTensor* SEGC2_Input(void);
TfLiteTensor* SEGC2_Output(void);

#endif /* _SEGMENTS_H_ */
