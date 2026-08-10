/*
 * Standalone ML-KEM benchmark -- performance (DWT cycle count) and memory
 * (peak stack high-water-mark, per operation) for the algorithm variant
 * currently linked (swapped via H:\z_thesis\swap.ps1; see
 * BENCHMARK_METHODOLOGY.md in this directory for the full protocol and
 * exactly how to reproduce every number reported from this firmware).
 *
 * Measures three separate things per operation (keypair / encapsulation /
 * decapsulation), each isolated to avoid one operation's stack usage
 * contaminating another's measurement:
 *   1. Cycle count (DWT->CYCCNT), REPS repetitions, free-running (no
 *      debugger attached during measurement -- matches this lab's
 *      established measurement rule).
 *   2. Peak stack usage via the high-water-mark ("stack painting")
 *      technique: fill the unused stack region with a known pattern
 *      before the operation runs, then scan from the bottom of the stack
 *      region upward after it returns -- the first address where the
 *      pattern is no longer intact marks how deep the stack ever grew.
 *      Standard embedded technique (cf. FreeRTOS
 *      uxTaskGetStackHighWaterMark); implemented here directly against
 *      the linker-provided __StackLimit/__StackTop symbols since there's
 *      no RTOS in this firmware.
 *
 * Code size is NOT measured at runtime -- read directly from the
 * linker's own memory-region report (m_text/m_data) printed at the end
 * of every `ninja` build; recorded manually into
 * results/mlkem_bench_summary.csv per variant (see methodology doc).
 *
 * Build with -DENERGY_MODE to additionally toggle a GPIO pin high for the
 * exact duration of each operation (for PPK2 current-trace alignment, see
 * BENCHMARK_METHODOLOGY.md Section 6) -- mirrors SecureMark-TLS's own
 * "GPIO used for external triggering" approach. In this mode, per-
 * iteration PRINTF is deliberately SUPPRESSED during the measurement
 * loop (UART TX itself draws current on the same rail the PPK2 is
 * watching -- printing mid-loop would inject spurious current spikes
 * into the very window being measured); results are buffered in RAM and
 * printed once, after the loop, once the energy-sensitive portion of the
 * run is over.
 */
#include "board.h"
#include "app.h"
#include "fsl_debug_console.h"
#include "dwt.h"
#include "api.h"

#ifdef ENERGY_MODE
#include "fsl_gpio.h"
#include "fsl_port.h"
/* Trigger pin: Arduino-header pin D2 (J1 pin 6, MCU pin P0_29 / GPIO0
 * bit 29 -- per the official FRDM-MCXN947 Hardware User Guide's Arduino
 * header pinout table; "Potential conflict: -", i.e. NXP-confirmed
 * unused elsewhere on this board). Cross-checked against this firmware's
 * own pin_mux.c (PORT0_2 SWO trace, PORT1_8/PORT1_9 debug UART) and
 * board.h (PORT0_10/PORT0_27/PORT1_2 LEDs, PORT0_6/PORT0_23 switches) --
 * no overlap. Chosen over the onboard LED (the original placeholder)
 * specifically to avoid the LED's own current draw contaminating the
 * PPK2 trace on the rail being measured. */
#define TRIGGER_GPIO GPIO0
#define TRIGGER_PIN  29U

static void TriggerInit(void)
{
    /* P0_29 (Arduino D2) is never touched by pin_mux.c, so its PORT mux
     * sits at reset default -- on this chip family that's "disabled/
     * analog", not GPIO (see fsl_port.h's port_mux enum: mux 0 means
     * kPORT_PinDisabledOrAnalog, GPIO is a separate explicit selection).
     * GPIO_PinInit() alone only sets direction/data registers; without
     * this, writes to the GPIO module never reach the physical pin. */
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
}
static inline void TriggerHigh(void) { GPIO_PinWrite(TRIGGER_GPIO, TRIGGER_PIN, 1); }
static inline void TriggerLow(void)  { GPIO_PinWrite(TRIGGER_GPIO, TRIGGER_PIN, 0); }
#endif

#define REPS 100

static uint8_t pk[PQCLEAN_MLKEM1024_CLEAN_CRYPTO_PUBLICKEYBYTES];
static uint8_t sk[PQCLEAN_MLKEM1024_CLEAN_CRYPTO_SECRETKEYBYTES];
static uint8_t ct[PQCLEAN_MLKEM1024_CLEAN_CRYPTO_CIPHERTEXTBYTES];
static uint8_t ss1[PQCLEAN_MLKEM1024_CLEAN_CRYPTO_BYTES];
static uint8_t ss2[PQCLEAN_MLKEM1024_CLEAN_CRYPTO_BYTES];

/* Linker-provided bounds of the stack region (see
 * debug/output.map: __StackLimit = __StackTop - STACK_SIZE). Declared as
 * arrays (not pointers) per the standard trick for taking the ADDRESS of
 * a linker symbol in C -- &__StackLimit gives the linker-assigned
 * address, not a value stored there. */
extern uint32_t __StackLimit[];
extern uint32_t __StackTop[];

#define STACK_PATTERN 0xAAAAAAAAu
/* Bytes of safety margin below the current stack pointer left unpainted,
 * so we never overwrite the live call frame that's about to call into
 * the operation being measured. */
#define STACK_PAINT_MARGIN_BYTES 128

static void StackPaint(void)
{
    uint32_t currentSp;
    __asm volatile ("mov %0, sp" : "=r" (currentSp));
    uint32_t *end = (uint32_t *)(currentSp - STACK_PAINT_MARGIN_BYTES);
    uint32_t *p = __StackLimit;
    while (p < end)
    {
        *p++ = STACK_PATTERN;
    }
}

/* Returns peak stack bytes used since the last StackPaint() call. */
static uint32_t StackHighWaterMarkBytes(void)
{
    uint32_t *p = __StackLimit;
    while (p < __StackTop && *p == STACK_PATTERN)
    {
        p++;
    }
    return (uint32_t)((uint8_t *)__StackTop - (uint8_t *)p);
}

#ifdef ENERGY_MODE
/* Gap between an operation's TriggerLow and the next operation's
 * TriggerHigh, so the PPK2's current trace shows a clean, unambiguous
 * LOW region between ops (rather than a trigger edge landing right on
 * top of e.g. StackPaint()'s own small current draw) -- makes slicing
 * the trace into per-op windows in post-processing straightforward and
 * visually unambiguous. Pure busy-wait; not timed, not part of any
 * reported measurement. */
static void InterOpGap(void)
{
    for (volatile int i = 0; i < 20000; i++) { }
}
#endif

int main(void)
{
    uint32_t c;

    BOARD_InitHardware();
    dwt_init();

    dwt_reset();
    for (volatile int i = 0; i < 1000; i++) { }
    PRINTF("dwt_sanity,%d\r\n", (int)dwt_get());

    PRINTF("alg,%s\r\n", PQCLEAN_MLKEM1024_CLEAN_CRYPTO_ALGNAME);
    PRINTF("stack_region_bytes,%d\r\n",
           (int)((uint8_t *)__StackTop - (uint8_t *)__StackLimit));

#ifdef ENERGY_MODE
    TriggerInit();
    TriggerLow();
    /* Cycle counts still recorded (as a cross-check against the
     * non-energy-mode run, which should reproduce these numbers closely
     * -- if it doesn't, something about ENERGY_MODE's extra GPIO/gap
     * code is perturbing the measurement and that's worth knowing), but
     * NOT printed until after the whole loop -- see file header comment
     * on why UART traffic during the loop would contaminate the PPK2
     * trace. */
    static uint32_t s_cycles[REPS][3];
    static uint32_t s_stack[REPS][3];

    for (int i = 0; i < REPS; i++)
    {
        StackPaint();
        TriggerHigh();
        dwt_reset();
        PQCLEAN_MLKEM1024_CLEAN_crypto_kem_keypair(pk, sk);
        c = dwt_get();
        TriggerLow();
        s_cycles[i][0] = c;
        s_stack[i][0] = StackHighWaterMarkBytes();
        InterOpGap();

        StackPaint();
        TriggerHigh();
        dwt_reset();
        PQCLEAN_MLKEM1024_CLEAN_crypto_kem_enc(ct, ss1, pk);
        c = dwt_get();
        TriggerLow();
        s_cycles[i][1] = c;
        s_stack[i][1] = StackHighWaterMarkBytes();
        InterOpGap();

        StackPaint();
        TriggerHigh();
        dwt_reset();
        PQCLEAN_MLKEM1024_CLEAN_crypto_kem_dec(ss2, ct, sk);
        c = dwt_get();
        TriggerLow();
        s_cycles[i][2] = c;
        s_stack[i][2] = StackHighWaterMarkBytes();
        InterOpGap();
    }

    PRINTF("op,cycles,stack_hwm_bytes\r\n");
    for (int i = 0; i < REPS; i++)
    {
        PRINTF("keypair,%d,%d\r\n", (int)s_cycles[i][0], (int)s_stack[i][0]);
        PRINTF("encaps,%d,%d\r\n", (int)s_cycles[i][1], (int)s_stack[i][1]);
        PRINTF("decaps,%d,%d\r\n", (int)s_cycles[i][2], (int)s_stack[i][2]);
    }
#else
    PRINTF("op,cycles,stack_hwm_bytes\r\n");

    /* Each operation gets its own paint-run-measure cycle, isolated from
     * the others, so e.g. decapsulation's (typically largest) stack
     * usage doesn't get attributed to keypair generation just because it
     * happened to run in an already-deep stack region. */
    for (int i = 0; i < REPS; i++)
    {
        StackPaint();
        dwt_reset();
        PQCLEAN_MLKEM1024_CLEAN_crypto_kem_keypair(pk, sk);
        c = dwt_get();
        PRINTF("keypair,%d,%d\r\n", (int)c, (int)StackHighWaterMarkBytes());

        StackPaint();
        dwt_reset();
        PQCLEAN_MLKEM1024_CLEAN_crypto_kem_enc(ct, ss1, pk);
        c = dwt_get();
        PRINTF("encaps,%d,%d\r\n", (int)c, (int)StackHighWaterMarkBytes());

        StackPaint();
        dwt_reset();
        PQCLEAN_MLKEM1024_CLEAN_crypto_kem_dec(ss2, ct, sk);
        c = dwt_get();
        PRINTF("decaps,%d,%d\r\n", (int)c, (int)StackHighWaterMarkBytes());
    }
#endif

    int ok = 1;
    for (int i = 0; i < PQCLEAN_MLKEM1024_CLEAN_CRYPTO_BYTES; i++)
    {
        if (ss1[i] != ss2[i]) ok = 0;
    }
    PRINTF("kem_match,%d\r\n", ok);

    PRINTF("done\r\n");
    while (1) { }
}
