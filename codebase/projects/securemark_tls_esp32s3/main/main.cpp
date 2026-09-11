/*
 * SecureMark-TLS self-hosted benchmark — ESP32-S3 entry point.
 * Runs the official EEMBC benchmark (sm_bench_main) once at boot.
 */
#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_system.h"

extern "C" int sm_bench_main(void);

extern "C" void app_main(void)
{
    printf("SecureMark-TLS ESP32-S3: starting benchmark\r\n");
    int rc = sm_bench_main();
    printf("=== SecureMark-TLS done rc=%d ===\r\n", rc);
    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(10000));
    }
}
