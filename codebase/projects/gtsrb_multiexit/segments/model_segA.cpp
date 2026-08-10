/*
 * Copyright 2026 NXP
 * SPDX-License-Identifier: BSD-3-Clause
 *
 * segA: raw image -> blocks 1-3 -> [exit1_logits, block3_features].
 */
#include "tensorflow/lite/micro/kernels/micro_ops.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/micro/kernels/neutron/neutron.h"
#include "tensorflow/lite/schema/schema_generated.h"

#include "fsl_debug_console.h"
#include "model_data_segA.h"

#define NUM_CLASSES 43

namespace {
constexpr int kArenaSize = 32 * 1024;
uint8_t s_arena[kArenaSize] __attribute__((aligned(16)));
const tflite::Model* s_model = nullptr;
tflite::MicroInterpreter* s_interpreter = nullptr;
int s_logitsIdx = -1;
int s_featuresIdx = -1;
}  // namespace

bool SEGA_Init(void)
{
    s_model = tflite::GetModel(model_data);
    if (s_model->version() != TFLITE_SCHEMA_VERSION)
    {
        PRINTF("SEGA: model schema mismatch\r\n");
        return false;
    }

    static tflite::MicroMutableOpResolver<1> resolver;
    resolver.AddCustom(tflite::GetString_NEUTRON_GRAPH(), tflite::Register_NEUTRON_GRAPH());

    static tflite::MicroInterpreter static_interpreter(s_model, resolver, s_arena, kArenaSize);
    s_interpreter = &static_interpreter;

    if (s_interpreter->AllocateTensors() != kTfLiteOk)
    {
        PRINTF("SEGA: AllocateTensors failed\r\n");
        return false;
    }

    /* TFLite conversion doesn't preserve Python-side output declaration
     * order -- disambiguate by shape (last dim == NUM_CLASSES => logits). */
    for (size_t i = 0; i < s_interpreter->outputs_size(); i++)
    {
        TfLiteTensor* t = s_interpreter->output(i);
        int lastDim = t->dims->data[t->dims->size - 1];
        if (lastDim == NUM_CLASSES) { s_logitsIdx = (int)i; }
        else { s_featuresIdx = (int)i; }
    }
    if (s_logitsIdx < 0 || s_featuresIdx < 0)
    {
        PRINTF("SEGA: could not disambiguate outputs\r\n");
        return false;
    }

    PRINTF("SEGA: arena used %d / %d bytes\r\n", (int)s_interpreter->arena_used_bytes(), kArenaSize);
    return true;
}

TfLiteStatus SEGA_Invoke(void) { return s_interpreter->Invoke(); }
TfLiteTensor* SEGA_Input(void) { return s_interpreter->input(0); }
TfLiteTensor* SEGA_OutputLogits(void) { return s_interpreter->output(s_logitsIdx); }
TfLiteTensor* SEGA_OutputFeatures(void) { return s_interpreter->output(s_featuresIdx); }
