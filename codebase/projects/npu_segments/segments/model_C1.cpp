/*
 * Copyright 2026 NXP
 * SPDX-License-Identifier: BSD-3-Clause
 *
 * 4-segment split, piece 3: feature_map[8x8x16] -> C1(Conv+ReLU6) -> feature_map[8x8x32].
 */
#include "tensorflow/lite/micro/kernels/micro_ops.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/micro/kernels/neutron/neutron.h"
#include "tensorflow/lite/schema/schema_generated.h"

#include "fsl_debug_console.h"
#include "model_data_C1.h"

namespace {
constexpr int kArenaSize = 8 * 1024;
uint8_t s_arena[kArenaSize] __attribute__((aligned(16)));
const tflite::Model* s_model = nullptr;
tflite::MicroInterpreter* s_interpreter = nullptr;
}  // namespace

bool SEGC1_Init(void)
{
    s_model = tflite::GetModel(model_data);
    if (s_model->version() != TFLITE_SCHEMA_VERSION)
    {
        PRINTF("SEGC1: model schema mismatch\r\n");
        return false;
    }

    static tflite::MicroMutableOpResolver<1> resolver;
    resolver.AddCustom(tflite::GetString_NEUTRON_GRAPH(), tflite::Register_NEUTRON_GRAPH());

    static tflite::MicroInterpreter static_interpreter(s_model, resolver, s_arena, kArenaSize);
    s_interpreter = &static_interpreter;

    if (s_interpreter->AllocateTensors() != kTfLiteOk)
    {
        PRINTF("SEGC1: AllocateTensors failed\r\n");
        return false;
    }
    PRINTF("SEGC1: arena used %d / %d bytes\r\n", (int)s_interpreter->arena_used_bytes(), kArenaSize);
    return true;
}

TfLiteStatus SEGC1_Invoke(void) { return s_interpreter->Invoke(); }
TfLiteTensor* SEGC1_Input(void) { return s_interpreter->input(0); }
TfLiteTensor* SEGC1_Output(void) { return s_interpreter->output(0); }
