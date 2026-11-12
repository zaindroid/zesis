/* ML-KEM-768: wolfSSL native vs PQClean clean C, on the ESP32-S3 at -O2.
 *
 * Same pairing as the FRDM-MCXN947 four-way table, minus the two pqm4 variants
 * that cannot run here: pqm4 is Cortex-M4F assembly and this is Xtensa.
 *
 * Cycles come from the Xtensa CCOUNT register at 240 MHz.
 */
#include <stdio.h>
#include <string.h>
#include <stdint.h>

#include "esp_cpu.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

extern "C" {
#include "wolfssl/wolfcrypt/settings.h"
#include "wolfssl/wolfcrypt/wc_mlkem.h"
#include "wolfssl/wolfcrypt/random.h"
#include "wolfssl/error-ssl.h"

#include "api.h"        /* PQClean ml-kem-768 */
}

#define CPU_HZ         240000000u
#define REPS           50
#define N_WOLF         50

/* Deterministic RNG: same seed every boot, so runs are repeatable. */
static uint32_t g_rand_state = 0x12345678u;
extern "C" int custom_rand_block(unsigned char *out, unsigned int sz)
{
    for (unsigned int i = 0; i < sz; i++) {
        g_rand_state ^= g_rand_state << 13;
        g_rand_state ^= g_rand_state >> 17;
        g_rand_state ^= g_rand_state << 5;
        out[i] = (uint8_t)(g_rand_state & 0xFF);
    }
    return 0;
}

static inline uint32_t now(void) { return esp_cpu_get_cycle_count(); }

static uint32_t s_wkp[N_WOLF], s_wen[N_WOLF], s_wdc[N_WOLF];
static uint32_t s_pkp[REPS],  s_pen[REPS],  s_pdc[REPS];
static uint8_t  s_same_w[N_WOLF], s_same_p[REPS];

static void bench_wolfssl(void)
{
    WC_RNG rng;
    int rc = wc_InitRng(&rng);
    printf("wolfssl init rng rc=%d\n", rc);

    /* PQClean and wolfSSL both use 1184/1088/32 for ML-KEM-768. */
    static uint8_t pk[1184], ct[1088], ss1[32], ss2[32];

    for (int i = 0; i < N_WOLF; i++) {
        MlKemKey key;
        rc = wc_MlKemKey_Init(&key, WC_ML_KEM_768, NULL, INVALID_DEVID);
        if (rc != 0) { printf("wolfssl key init failed rc=%d\n", rc); break; }

        uint32_t t0 = now(); wc_MlKemKey_MakeKey(&key, &rng);        s_wkp[i] = now() - t0;
        t0 = now();         wc_MlKemKey_Encapsulate(&key, ct, ss1, &rng); s_wen[i] = now() - t0;
        t0 = now();         wc_MlKemKey_Decapsulate(&key, ss2, ct, sizeof(ct)); s_wdc[i] = now() - t0;

        s_same_w[i] = (uint8_t)(memcmp(ss1, ss2, 32) == 0);
        wc_MlKemKey_Free(&key);
    }
    wc_FreeRng(&rng);
}

static void bench_pqclean(void)
{
    static uint8_t pk[1184], sk[2400], ct[1088], ss1[32], ss2[32];
    for (int i = 0; i < REPS; i++) {
        uint32_t t0 = now(); PQCLEAN_MLKEM768_CLEAN_crypto_kem_keypair(pk, sk);       s_pkp[i] = now() - t0;
        t0 = now();          PQCLEAN_MLKEM768_CLEAN_crypto_kem_enc(ct, ss1, pk);      s_pen[i] = now() - t0;
        t0 = now();          PQCLEAN_MLKEM768_CLEAN_crypto_kem_dec(ss2, ct, sk);      s_pdc[i] = now() - t0;
        s_same_p[i] = (uint8_t)(memcmp(ss1, ss2, 32) == 0);
    }
}

extern "C" void app_main(void)
{
    /* Give the host time to open the USB Serial/JTAG port before any output:
       anything printed before the port is open is lost. */
    vTaskDelay(pdMS_TO_TICKS(8000));

    printf("\nPQC_ESP32S3_BEGIN cpu_hz=%u\n", CPU_HZ);

    bench_wolfssl();
    bench_pqclean();

    int wf = 0, pf = 0;
    for (int i = 0; i < N_WOLF; i++) if (!s_same_w[i]) wf++;
    for (int i = 0; i < REPS;  i++) if (!s_same_p[i]) pf++;
    printf("roundtrip_failures wolfssl=%d pqclean=%d\n", wf, pf);

    printf("WOLF_BEGIN\n");
    for (int i = 0; i < N_WOLF; i++)
        printf("%u,%u,%u\n", (unsigned)s_wkp[i], (unsigned)s_wen[i], (unsigned)s_wdc[i]);
    printf("WOLF_END\n");

    printf("PQC_BEGIN\n");
    for (int i = 0; i < REPS; i++)
        printf("%u,%u,%u\n", (unsigned)s_pkp[i], (unsigned)s_pen[i], (unsigned)s_pdc[i]);
    printf("PQC_END\n");

    printf("PQC_ESP32S3_COMPLETE\n");
}
