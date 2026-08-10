extern "C" {
#include "fsl_debug_console.h"
#include "board.h"
#include "app.h"
#include "mcmgr.h"
#include <string.h>
}

#include "board_init.h"
#include "demo_config.h"
#include "demo_info.h"
#include "image.h"
#include "image_utils.h"
#include "model.h"
#include "output_postproc.h"
#include "timer.h"

int main(void)
{
    (void)MCMGR_Init();
    BOARD_Init();
    TIMER_Init();
    DEMO_PrintInfo();

    if (MODEL_Init() != kStatus_Success)
    {
        PRINTF("Failed initializing model\r\n");
        for (;;) {}
    }

    tensor_dims_t inputDims;
    tensor_type_t inputType;
    uint8_t* inputData = MODEL_GetInputTensorData(&inputDims, &inputType);
    tensor_dims_t outputDims;
    tensor_type_t outputType;
    uint8_t* outputData = MODEL_GetOutputTensorData(&outputDims, &outputType);

    /* Boot core 1 (crypto hammer) using the working multicore sequence */
#ifdef CORE1_IMAGE_COPY_TO_RAM
    uint32_t core1_image_size = get_core1_image_size();
    (void)PRINTF("Copy core1 image to 0x%x, size %d\r\n",
                 (void *)(char *)CORE1_BOOT_ADDRESS, core1_image_size);
    (void)memcpy((void *)(char *)CORE1_BOOT_ADDRESS, (void *)CORE1_IMAGE_START, core1_image_size);
#endif
    (void)PRINTF("Starting core 1 (crypto)...\r\n");
    (void)MCMGR_StartCore(kMCMGR_Core1, (void *)(char *)CORE1_BOOT_ADDRESS, 2, kMCMGR_Start_Synchronous);
    (void)PRINTF("Core 1 started.\r\n");

    /* Prime one input image */
    if (IMAGE_GetImage(inputData, inputDims.data[2], inputDims.data[1], inputDims.data[3]) != kStatus_Success)
    {
        PRINTF("Failed retrieving input image\r\n");
        for (;;) {}
    }
    MODEL_ConvertInput(inputData, &inputDims, inputType);

    PRINTF("inference_us\r\n");

    /* 100 inferences WHILE core 1 hammers crypto */
    int lastInferenceTime = 0;
    for (int i = 0; i < 100; i++)
    {
        auto startTime = TIMER_GetTimeInUS();
        MODEL_RunInference();
        auto endTime = TIMER_GetTimeInUS();
        lastInferenceTime = (int)(endTime - startTime);
        PRINTF("%d\r\n", lastInferenceTime);
    }

    PRINTF("done\r\n");
    /* Sanity-check classification result of the last run (printed after the CSV block) */
    (void)MODEL_ProcessOutput(outputData, &outputDims, outputType, lastInferenceTime);
    for (;;) {}
}
