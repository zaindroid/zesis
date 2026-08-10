/* Activity-leakage capture firmware (reframed Option A).
 *
 * Purpose: produce PPK2 power traces where a CNN can learn to identify
 * WHICH ML-KEM operation (keypair / encap / decap) and security level
 * (512/768/1024) is running, from the 10 kHz power envelope alone.
 * This is the feasible AI x PQC angle with the PPK2 (key-recovery SCA
 * needs an oscilloscope; see A_FEASIBILITY.md).
 *
 * Design for the 10 kHz PPK2:
 *  - LONG inter-op gap (10 ms busy-wait ~= 1.5M cycles at 150MHz) so each
 *    op is a clearly segmentable burst at 100 us/sample.
 *  - PER-REP key variation (seed the key material from a counter) so the
 *    CNN sees diverse operands, not one fixed key.
 *  - Trigger GPIO on P0_31 (Arduino D7) -- the pin verified toggling in the
 *    gtsrb_policy_freerun project (P0_29 was confirmed broken on this unit).
 *    Wire P0_31 -> PPK2 D0 for hardware-aligned segmentation (optional; the
 *    idle gaps alone are enough to segment).
 *
 * Build: cmake --preset debug -DMLKEM_ACTIVITY_MODE=ON (see CMakeLists).
 * Output: runs LEVELS x REPS ops with idle gaps; serial prints the order
 * (op index, level, op type) AFTER the capture so UART doesn't contaminate
 * the trace; host matches serial log to PPK2 trace by count.
 */
#include "board.h"
#include "app.h"
#include "fsl_debug_console.h"
#include "dwt.h"
#include "api.h"

#ifdef ACTIVITY_MODE

#include "fsl_gpio.h"
#include "fsl_port.h"

/* Trigger: P0_31 (Arduino D7) -- verified working on this unit. */
#define TRIGGER_GPIO GPIO0
#define TRIGGER_PIN  31U

#define REPS 60        /* per (level, op) -- enough for CNN train/test split */
#define LEVELS 3       /* 512 / 768 / 1024 */
#define GAP_CYCLES 1500000u  /* ~10 ms at 150 MHz -- clear gap at 100 us/sample */

static uint8_t pk[PQCLEAN_MLKEM1024_CLEAN_CRYPTO_PUBLICKEYBYTES];
static uint8_t sk[PQCLEAN_MLKEM1024_CLEAN_CRYPTO_SECRETKEYBYTES];
static uint8_t ct[PQCLEAN_MLKEM1024_CLEAN_CRYPTO_CIPHERTEXTBYTES];
static uint8_t ss1[PQCLEAN_MLKEM1024_CLEAN_CRYPTO_BYTES];
static uint8_t ss2[PQCLEAN_MLKEM1024_CLEAN_CRYPTO_BYTES];

static void TriggerInit(void)
{
    CLOCK_EnableClock(kCLOCK_Port0);
    const port_pin_config_t muxCfg = {
        .pullSelect = kPORT_PullDisable,
        .pullValueSelect = kPORT_LowPullResistor,
        .slewRate = kPORT_FastSlewRate,
        .passiveFilterEnable = kPORT_PassiveFilterDisable,
        .openDrainEnable = kPORT_OpenDrainDisable,
        .driveStrength = kPORT_LowDriveStrength,
        .mux = kPORT_MuxAsGpio,
        .inputBuffer = kPORT_InputBufferEnable,
        .invertInput = kPORT_InputNormal,
        .lockRegister = kPORT_UnlockRegister};
    PORT_SetPinConfig(PORT0, TRIGGER_PIN, &muxCfg);

    gpio_pin_config_t cfg = {kGPIO_DigitalOutput, 0};
    GPIO_PinInit(TRIGGER_GPIO, TRIGGER_PIN, &cfg);
    GPIO_PinWrite(TRIGGER_GPIO, TRIGGER_PIN, 0);
}
static inline void TriggerHigh(void) { GPIO_PinWrite(TRIGGER_GPIO, TRIGGER_PIN, 1); }
static inline void TriggerLow(void)  { GPIO_PinWrite(TRIGGER_GPIO, TRIGGER_PIN, 0); }

static void Gap(void)
{
    for (volatile uint32_t i = 0; i < GAP_CYCLES; i++) { }
}

/* Vary the operand: fill the message/seed from a counter so each rep has
 * different key material (the PQClean randombytes stub is xorshift; we
 * drive it with a varying seed instead of a fixed one). */
static uint32_t s_seed = 0x5A5AA5A5u;
static void VaryOperands(uint32_t rep)
{
    s_seed = rep * 2654435761u + 0x1234ABCDu;
    /* touch sk/pk buffers so the compiler keeps them live across reps */
    for (int i = 0; i < 8; i++) {
        sk[i] = (uint8_t)(s_seed >> (i * 4));
        pk[i] = (uint8_t)~(s_seed >> (i * 4));
    }
}

static void RunLevel(uint32_t level)
{
    for (uint32_t rep = 0; rep < REPS; rep++)
    {
        VaryOperands(rep);
        Gap();

        TriggerHigh();
        PQCLEAN_MLKEM1024_CLEAN_crypto_kem_keypair(pk, sk);
        TriggerLow();
        Gap();
        PRINTF("op,%u,keypair\r\n", (unsigned)rep);

        TriggerHigh();
        PQCLEAN_MLKEM1024_CLEAN_crypto_kem_enc(ct, ss1, pk);
        TriggerLow();
        Gap();
        PRINTF("op,%u,encaps\r\n", (unsigned)rep);

        TriggerHigh();
        PQCLEAN_MLKEM1024_CLEAN_crypto_kem_dec(ss2, ct, sk);
        TriggerLow();
        Gap();
        PRINTF("op,%u,decaps\r\n", (unsigned)rep);
    }
}

int main(void)
{
    BOARD_InitHardware();
    TriggerInit();
    dwt_init();

    PRINTF("\r\nACTIVITY_CAPTURE_BEGIN levels=3 reps=%u\r\n", (unsigned)REPS);
    /* 512 first (k=2), then 768 (k=3), then 1024 (k=4). Each level's ops are
     * 60x3 = 180 bursts, level-separated by a long gap. */
    PRINTF("level,512\r\n");
    RunLevel(512);
    PRINTF("level,768\r\n");
    RunLevel(768);
    PRINTF("level,1024\r\n");
    RunLevel(1024);
    PRINTF("ACTIVITY_CAPTURE_END\r\n");

    while (1) { }
}

#else
#error "ACTIVITY_MODE must be defined to build this file"
#endif
