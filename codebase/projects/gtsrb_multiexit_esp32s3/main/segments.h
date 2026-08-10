/*
 * Multi-exit segment wrapper for ESP32-S3 TFLite Micro.
 *
 * Runs the three INT8 TFLite segment models (segA/segB/segC) from the frozen
 * four-way certification. Unlike the NXP port (which offloaded each segment
 * to the Neutron NPU as a single custom op), here every standard op
 * (CONV_2D, DEPTHWISE_CONV_2D, FULLY_CONNECTED, MEAN) executes on the
 * ESP32-S3 CPU via TFLite Micro. The INT8 arithmetic is preserved exactly,
 * which is what makes the certified tau thresholds transferable.
 *
 * API mirrors the NXP segments.h so main.cpp policy logic ports verbatim.
 */
#ifndef _SEGMENTS_ESP32_H_
#define _SEGMENTS_ESP32_H_

#include "tensorflow/lite/c/common.h"

bool SEGA_Init(void);
bool SEGB_Init(void);
bool SEGC_Init(void);

TfLiteStatus SEGA_Invoke(void);
TfLiteStatus SEGB_Invoke(void);
TfLiteStatus SEGC_Invoke(void);

TfLiteTensor* SEGA_Input(void);
TfLiteTensor* SEGA_OutputLogits(void);
TfLiteTensor* SEGA_OutputFeatures(void);
TfLiteTensor* SEGB_Input(void);
TfLiteTensor* SEGB_OutputLogits(void);
TfLiteTensor* SEGB_OutputFeatures(void);
TfLiteTensor* SEGC_Input(void);
TfLiteTensor* SEGC_OutputLogits(void);

#endif /* _SEGMENTS_ESP32_H_ */
