/* SecureMark-TLS board entry for FRDM-MCXN947.
 * Initializes the board, then runs the EEMBC self-hosted benchmark.
 */
#include "app.h"
#include "board.h"
#include "fsl_debug_console.h"
#include "dwt.h"

int sm_bench_main(void);

int main(void)
{
    BOARD_InitHardware();
    dwt_init();

    PRINTF("\r\n=== SecureMark-TLS (self-hosted) - FRDM-MCXN947 ===\r\n");
    {
        uint32_t c1 = dwt_get();
        for (volatile int i = 0; i < 1000; i++) {}
        uint32_t c2 = dwt_get();
        PRINTF("DWT c1=%u c2=%u\r\n", (unsigned)c1, (unsigned)c2);
    }

    /* Run the EEMBC benchmark (blocks until done, prints score) */
    int rc = sm_bench_main();

    PRINTF("\r\n=== SecureMark-TLS done rc=%d ===\r\n", rc);
    while (1) { }
}
