#include "board_init.h"
#include "demo_config.h"
#include "demo_info.h"
#include "fsl_debug_console.h"
#include "image.h"
#include "image_utils.h"
#include "model.h"
#include "output_postproc.h"
#include "timer.h"
#include "mcmgr.h"

extern "C" {
#include "fsl_common.h"
}

/* core1 boot address - from the multicore example */
#ifndef CORE1_BOOT_ADDRESS
#define CORE1_BOOT_ADDRESS (void *)0x2004e000
#endif

int main(void)
{
    (void)MCMGR_Init();
    BOARD_Init();
    TIMER_Init();
    DEMO_PrintInfo();

    if (MODEL_Init() != kStatus_Success)
    {
        PRINTF("Failed initializing model" EOL);
        for (;;) {}
    }

    tensor_dims_t inputDims;
    tensor_type_t inputType;
    uint8_t* inputData = MODEL_GetInputTensorData(&inputDims, &inputType);
    tensor_dims_t outputDims;
    tensor_type_t outputType;
    uint8_t* outputData = MODEL_GetOutputTensorData(&outputDims, &outputType);

    /* Boot core 1 - it will hammer crypto continuously */
    PRINTF("Starting core 1 (crypto hammer)...\r\n");
    (void)MCMGR_StartCore(kMCMGR_Core1, CORE1_BOOT_ADDRESS, 2, kMCMGR_Start_Synchronous);
    PRINTF("Core 1 started.\r\n");

    /* Prime one input image */
    if (IMAGE_GetImage(inputData, inputDims.data[2], inputDims.data[1], inputDims.data[3]) != kStatus_Success)
    {
        PRINTF("Failed retrieving input image" EOL);
        for (;;) {}
    }
    MODEL_ConvertInput(inputData, &inputDims, inputType);

    PRINTF("inference_us\r\n");

    /* Run inference 100 times WHILE core 1 hammers crypto */
    for (int i = 0; i < 100; i++)
    {
        auto startTime = TIMER_GetTimeInUS();
        MODEL_RunInference();
        auto endTime = TIMER_GetTimeInUS();
        PRINTF("%d\r\n", (int)(endTime - startTime));
    }

    PRINTF("done\r\n");
    for (;;) {}
}
