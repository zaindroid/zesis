/*
 * Copyright 2026 NXP
 * SPDX-License-Identifier: BSD-3-Clause
 *
 * Monolithic (unsplit) toy model: full_input -> A -> B -> C -> logits[10].
 */
#include "tensorflow/lite/micro/kernels/micro_ops.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/micro/kernels/neutron/neutron.h"
#include "tensorflow/lite/schema/schema_generated.h"

#include "fsl_debug_console.h"
#include "model_data_mono.h"

namespace {
constexpr int kArenaSize = 16 * 1024;
uint8_t s_arena[kArenaSize] __attribute__((aligned(16)));
const tflite::Model* s_model = nullptr;
tflite::MicroInterpreter* s_interpreter = nullptr;
}  // namespace

bool MONO_Init(void)
{
    s_model = tflite::GetModel(model_data);
    if (s_model->version() != TFLITE_SCHEMA_VERSION)
    {
        PRINTF("MONO: model schema mismatch\r\n");
        return false;
    }

    static tflite::MicroMutableOpResolver<2> resolver;
    resolver.AddPad();
    resolver.AddCustom(tflite::GetString_NEUTRON_GRAPH(), tflite::Register_NEUTRON_GRAPH());

    static tflite::MicroInterpreter static_interpreter(s_model, resolver, s_arena, kArenaSize);
    s_interpreter = &static_interpreter;

    if (s_interpreter->AllocateTensors() != kTfLiteOk)
    {
        PRINTF("MONO: AllocateTensors failed\r\n");
        return false;
    }
    PRINTF("MONO: arena used %d / %d bytes\r\n", (int)s_interpreter->arena_used_bytes(), kArenaSize);
    return true;
}

TfLiteStatus MONO_Invoke(void) { return s_interpreter->Invoke(); }
TfLiteTensor* MONO_Input(void) { return s_interpreter->input(0); }
TfLiteTensor* MONO_Output(void) { return s_interpreter->output(0); }
