#include "fsl_debug_console.h"
#include "board.h"
#include "app.h"
#include "mcmgr.h"
#include "dwt.h"

#define ARR_SIZE 8192
static volatile uint32_t work_arr[ARR_SIZE];

/* A memory-heavy workload: streams through a big array read+write.
   This stresses the same shared memory the crypto on core 1 uses. */
static uint32_t do_work(void)
{
    uint32_t sum = 0;
    for (int i = 0; i < ARR_SIZE; i++) {
        work_arr[i] = work_arr[i] * 3 + 1;
        sum += work_arr[i];
    }
    return sum;
}

int main(void)
{
    (void)MCMGR_Init();
    BOARD_InitHardware();
    dwt_init();

    (void)PRINTF("\r\nHello World from the Primary Core!\r\n\n");

#ifdef CORE1_IMAGE_COPY_TO_RAM
    uint32_t core1_image_size;
    core1_image_size = get_core1_image_size();
    (void)PRINTF("Copy Secondary core image to address: 0x%x, size: %d\r\n",
                 (void *)(char *)CORE1_BOOT_ADDRESS, core1_image_size);
    (void)memcpy((void *)(char *)CORE1_BOOT_ADDRESS, (void *)CORE1_IMAGE_START, core1_image_size);
#ifdef APP_INVALIDATE_CACHE_FOR_SECONDARY_CORE_IMAGE_MEMORY
    invalidate_cache_for_core1_image_memory(CORE1_BOOT_ADDRESS, core1_image_size);
#endif
#endif

    (void)PRINTF("Starting Secondary core.\r\n");
    (void)MCMGR_StartCore(kMCMGR_Core1, (void *)(char *)CORE1_BOOT_ADDRESS, 2, kMCMGR_Start_Synchronous);
    (void)PRINTF("Secondary core started - it is now crypto-hammering.\r\n");

    /* init the work array */
    for (int i = 0; i < ARR_SIZE; i++) work_arr[i] = i;

    (void)PRINTF("workload_cycles\r\n");

    /* Measure our workload repeatedly WHILE core 1 hammers crypto. */
    for (int r = 0; r < 100; r++)
    {
        dwt_reset();
        volatile uint32_t s = do_work();
        uint32_t c = dwt_get();
        (void)s;
        (void)PRINTF("%d\r\n", (int)c);
    }

    (void)PRINTF("done\r\n");
    for (;;) { }
}