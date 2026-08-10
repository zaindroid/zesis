/*
 * Copyright 2026 NXP
 * SPDX-License-Identifier: BSD-3-Clause
 *
 * segC (final): block6_features -> blocks 7-10 -> exit3_logits.
 * Single output, no further continuation possible.
 */
#include "tensorflow/lite/micro/kernels/micro_ops.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/micro/kernels/neutron/neutron.h"
#include "tensorflow/lite/schema/schema_generated.h"

#include "fsl_debug_console.h"
#include "model_data_segC.h"

namespace {
constexpr int kArenaSize = 8 * 1024;
uint8_t s_arena[kArenaSize] __attribute__((aligned(16)));
const tflite::Model* s_model = nullptr;
tflite::MicroInterpreter* s_interpreter = nullptr;
}  // namespace

bool SEGC_Init(void)
{
    s_model = tflite::GetModel(model_data);
    if (s_model->version() != TFLITE_SCHEMA_VERSION)
    {
        PRINTF("SEGC: model schema mismatch\r\n");
        return false;
    }

    static tflite::MicroMutableOpResolver<1> resolver;
    resolver.AddCustom(tflite::GetString_NEUTRON_GRAPH(), tflite::Register_NEUTRON_GRAPH());

    static tflite::MicroInterpreter static_interpreter(s_model, resolver, s_arena, kArenaSize);
    s_interpreter = &static_interpreter;

    if (s_interpreter->AllocateTensors() != kTfLiteOk)
    {
        PRINTF("SEGC: AllocateTensors failed\r\n");
        return false;
    }
    PRINTF("SEGC: arena used %d / %d bytes\r\n", (int)s_interpreter->arena_used_bytes(), kArenaSize);
    return true;
}

TfLiteStatus SEGC_Invoke(void) { return s_interpreter->Invoke(); }
TfLiteTensor* SEGC_Input(void) { return s_interpreter->input(0); }
TfLiteTensor* SEGC_OutputLogits(void) { return s_interpreter->output(0); }
