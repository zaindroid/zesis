/*
 * Copyright 2026 NXP
 * SPDX-License-Identifier: BSD-3-Clause
 *
 * segB: block3_features -> blocks 4-6 -> [exit2_logits, block6_features].
 */
#include "tensorflow/lite/micro/kernels/micro_ops.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/micro/kernels/neutron/neutron.h"
#include "tensorflow/lite/schema/schema_generated.h"

#include "fsl_debug_console.h"
#include "model_data_segB.h"

#define NUM_CLASSES 43

namespace {
constexpr int kArenaSize = 16 * 1024;
uint8_t s_arena[kArenaSize] __attribute__((aligned(16)));
const tflite::Model* s_model = nullptr;
tflite::MicroInterpreter* s_interpreter = nullptr;
int s_logitsIdx = -1;
int s_featuresIdx = -1;
}  // namespace

bool SEGB_Init(void)
{
    s_model = tflite::GetModel(model_data);
    if (s_model->version() != TFLITE_SCHEMA_VERSION)
    {
        PRINTF("SEGB: model schema mismatch\r\n");
        return false;
    }

    static tflite::MicroMutableOpResolver<1> resolver;
    resolver.AddCustom(tflite::GetString_NEUTRON_GRAPH(), tflite::Register_NEUTRON_GRAPH());

    static tflite::MicroInterpreter static_interpreter(s_model, resolver, s_arena, kArenaSize);
    s_interpreter = &static_interpreter;

    if (s_interpreter->AllocateTensors() != kTfLiteOk)
    {
        PRINTF("SEGB: AllocateTensors failed\r\n");
        return false;
    }

    for (size_t i = 0; i < s_interpreter->outputs_size(); i++)
    {
        TfLiteTensor* t = s_interpreter->output(i);
        int lastDim = t->dims->data[t->dims->size - 1];
        if (lastDim == NUM_CLASSES) { s_logitsIdx = (int)i; }
        else { s_featuresIdx = (int)i; }
    }
    if (s_logitsIdx < 0 || s_featuresIdx < 0)
    {
        PRINTF("SEGB: could not disambiguate outputs\r\n");
        return false;
    }

    PRINTF("SEGB: arena used %d / %d bytes\r\n", (int)s_interpreter->arena_used_bytes(), kArenaSize);
    return true;
}

TfLiteStatus SEGB_Invoke(void) { return s_interpreter->Invoke(); }
TfLiteTensor* SEGB_Input(void) { return s_interpreter->input(0); }
TfLiteTensor* SEGB_OutputLogits(void) { return s_interpreter->output(s_logitsIdx); }
TfLiteTensor* SEGB_OutputFeatures(void) { return s_interpreter->output(s_featuresIdx); }
