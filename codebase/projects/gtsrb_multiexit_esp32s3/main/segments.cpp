/*
 * Multi-exit segment implementation for ESP32-S3 TFLite Micro.
 *
 * Each segment is a standalone INT8 TFLite model with standard ops only.
 * segA: 48x48x3 image -> [exit1 logits(43), block3 features(12x12x32)]
 * segB: block3 features -> [exit2 logits(43), block6 features(6x6x40)]
 * segC: block6 features -> [exit3 logits(43)]
 *
 * TFLite Micro does not preserve Python-side output declaration order, so
 * outputs are disambiguated by shape (last dim == NUM_CLASSES => logits).
 */
#include "segments.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/schema/schema_generated.h"

#include "segA_model_data.h"
#include "segB_model_data.h"
#include "segC_model_data.h"

#include <cstdio>
#include <cstring>
#include "esp_heap_caps.h"

#define NUM_CLASSES 43

/* Arena sizes: each model's intermediate tensors live here. The NXP port used
 * a 32KB arena with the NPU; on the CPU these need to hold all intermediates
 * for the segment. Total (608 KB) exceeds internal SRAM, so arenas are
 * allocated from external PSRAM (see sdkconfig.defaults: CONFIG_SPIRAM=y). */
namespace {
constexpr int kArenaA = 256 * 1024;
constexpr int kArenaB = 192 * 1024;
constexpr int kArenaC = 160 * 1024;

struct SegCtx
{
    const tflite::Model* model;
    tflite::MicroInterpreter* interp;
    uint8_t* arena;
    int logitsIdx;
    int featuresIdx; /* -1 if none */
};

SegCtx s_segA{};
SegCtx s_segB{};
SegCtx s_segC{};

template <int N>
bool InitSegment(const unsigned char* data, unsigned int len, int arenaSize,
                 const char* name, SegCtx* ctx)
{
    ctx->arena = (uint8_t*)heap_caps_malloc(arenaSize, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (ctx->arena == nullptr)
    {
        printf("SEG[%s]: PSRAM alloc of %d B failed\r\n", name, arenaSize);
        return false;
    }
    ctx->model = tflite::GetModel(data);
    if (ctx->model->version() != TFLITE_SCHEMA_VERSION)
    {
        printf("SEG[%s]: schema mismatch (model %d vs tflm %d)\r\n",
               name, (int)ctx->model->version(), (int)TFLITE_SCHEMA_VERSION);
        return false;
    }
    static tflite::MicroMutableOpResolver<N> resolver;
    /* Standard ops used by our segments. */
    resolver.AddConv2D();
    resolver.AddDepthwiseConv2D();
    resolver.AddFullyConnected();
    resolver.AddMean();

    static tflite::MicroInterpreter interp(ctx->model, resolver, ctx->arena, arenaSize);
    ctx->interp = &interp;

    if (ctx->interp->AllocateTensors() != kTfLiteOk)
    {
        printf("SEG[%s]: AllocateTensors failed (arena %d, model %u B)\r\n",
               name, arenaSize, len);
        return false;
    }

    ctx->logitsIdx = -1;
    ctx->featuresIdx = -1;
    for (size_t i = 0; i < ctx->interp->outputs_size(); i++)
    {
        TfLiteTensor* t = ctx->interp->output(i);
        int lastDim = t->dims->data[t->dims->size - 1];
        if (lastDim == NUM_CLASSES) { ctx->logitsIdx = (int)i; }
        else { ctx->featuresIdx = (int)i; }
    }
    if (ctx->logitsIdx < 0)
    {
        printf("SEG[%s]: no logits output found\r\n", name);
        return false;
    }
    printf("SEG[%s]: loaded %u B, logits out=%d", name, len, ctx->logitsIdx);
    if (ctx->featuresIdx >= 0) { printf(", features out=%d", ctx->featuresIdx); }
    printf("\r\n");
    return true;
}
}  // namespace

bool SEGA_Init(void)
{
    return InitSegment<16>(segA_tflite, segA_tflite_len, kArenaA, "A", &s_segA);
}

bool SEGB_Init(void)
{
    return InitSegment<17>(segB_tflite, segB_tflite_len, kArenaB, "B", &s_segB);
}

bool SEGC_Init(void)
{
    return InitSegment<18>(segC_tflite, segC_tflite_len, kArenaC, "C", &s_segC);
}

TfLiteStatus SEGA_Invoke(void) { return s_segA.interp->Invoke(); }
TfLiteStatus SEGB_Invoke(void) { return s_segB.interp->Invoke(); }
TfLiteStatus SEGC_Invoke(void) { return s_segC.interp->Invoke(); }

TfLiteTensor* SEGA_Input(void) { return s_segA.interp->input(0); }
TfLiteTensor* SEGA_OutputLogits(void) { return s_segA.interp->output(s_segA.logitsIdx); }
TfLiteTensor* SEGA_OutputFeatures(void)
{
    return s_segA.featuresIdx >= 0 ? s_segA.interp->output(s_segA.featuresIdx) : nullptr;
}
TfLiteTensor* SEGB_Input(void) { return s_segB.interp->input(0); }
TfLiteTensor* SEGB_OutputLogits(void) { return s_segB.interp->output(s_segB.logitsIdx); }
TfLiteTensor* SEGB_OutputFeatures(void)
{
    return s_segB.featuresIdx >= 0 ? s_segB.interp->output(s_segB.featuresIdx) : nullptr;
}
TfLiteTensor* SEGC_Input(void) { return s_segC.interp->input(0); }
TfLiteTensor* SEGC_OutputLogits(void) { return s_segC.interp->output(s_segC.logitsIdx); }
