/*
 * Standalone X25519 benchmark -- performance (DWT cycle count) and
 * memory (peak stack high-water-mark, per operation) for classical
 * elliptic-curve Diffie-Hellman key exchange, on the FRDM-MCXN947.
 *
 * Companion to mlkem_bench: same board, same measurement techniques
 * (DWT cycle counter, stack painting, GPIO-triggered energy mode,
 * PPK2 wiring at J24), so the two are directly comparable. See that
 * project's BENCHMARK_METHODOLOGY.md for the full protocol -- it
 * applies here unchanged except for the operation set below.
 *
 * X25519 has a different operation structure than ML-KEM: it is a
 * plain Diffie-Hellman scheme, not a KEM, so there is no encaps/decaps
 * split -- both parties in a real exchange run the exact same two
 * operations:
 *   1. keypair: generate a private/public keypair (crypto_scalarmult_base)
 *   2. shared_secret: compute the shared secret from your private key
 *      and the peer's public key (crypto_scalarmult)
 * A full exchange from one party's perspective is therefore these two
 * operations once each -- two operations total, versus ML-KEM's three
 * (keypair/encaps/decaps). This is a real structural difference
 * between DH-based and KEM-based exchange, not a measurement
 * inconsistency, and is called out explicitly in the comparison
 * report rather than papered over.
 *
 * Build with -DENERGY_MODE for the GPIO-triggered energy-measurement
 * variant, identical in structure to mlkem_bench's.
 */
#include "board.h"
#include "app.h"
#include "fsl_debug_console.h"
#include "dwt.h"
#include "x25519.h"

#ifdef ENERGY_MODE
#include "fsl_gpio.h"
#include "fsl_port.h"

/* Same trigger pin as mlkem_bench: Arduino header D2 (P0_29 / GPIO0
 * bit 29), confirmed conflict-free against this board's official
 * pinout table. See mlkem_bench/hello_world.c for the full rationale
 * on why the explicit PORT mux config below is required. */
#define TRIGGER_GPIO GPIO0
#define TRIGGER_PIN  29U

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
}
static inline void TriggerHigh(void) { GPIO_PinWrite(TRIGGER_GPIO, TRIGGER_PIN, 1); }
static inline void TriggerLow(void)  { GPIO_PinWrite(TRIGGER_GPIO, TRIGGER_PIN, 0); }
#endif

#define REPS 100

/* Fixed (not random) test scalars -- benchmarking convenience only,
 * same rationale as mlkem_bench's deterministic RNG stub: makes runs
 * bit-for-bit reproducible. Never used outside of benchmarking.
 * crypto_scalarmult clamps these internally per the X25519 spec, so
 * any 32 bytes are a valid private scalar. */
static uint8_t alice_priv[32] = {
    0x77, 0x07, 0x6d, 0x0a, 0x73, 0x18, 0xa5, 0x7d,
    0x3c, 0x16, 0xc1, 0x72, 0x51, 0xb2, 0x66, 0x45,
    0xdf, 0x4c, 0x2f, 0x87, 0xeb, 0xc0, 0x99, 0x2a,
    0xb1, 0x77, 0xfb, 0xa5, 0x1d, 0xb9, 0x2c, 0x2a};

static uint8_t bob_priv[32] = {
    0x5d, 0xab, 0x08, 0x7e, 0x62, 0x4a, 0x8a, 0x4b,
    0x79, 0xe1, 0x7f, 0x8b, 0x83, 0x80, 0x0e, 0xe6,
    0x6f, 0x3b, 0xb1, 0x29, 0x26, 0x18, 0xb6, 0xfd,
    0x1c, 0x2f, 0x8b, 0x27, 0xff, 0x88, 0xe0, 0xeb};

static uint8_t alice_pub[32];
static uint8_t bob_pub[32];
static uint8_t shared_alice[32];
static uint8_t shared_bob[32];

/* Linker-provided stack region bounds, same technique as mlkem_bench. */
extern uint32_t __StackLimit[];
extern uint32_t __StackTop[];

#define STACK_PATTERN 0xAAAAAAAAu
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

    PRINTF("alg,X25519\r\n");
    PRINTF("stack_region_bytes,%d\r\n",
           (int)((uint8_t *)__StackTop - (uint8_t *)__StackLimit));

    /* Bob's public key is needed as the peer input for every
     * "shared_secret" repetition -- computed once, outside the
     * measurement loop, same as how mlkem_bench derives its
     * ciphertext/public-key inputs before each measured operation. */
    crypto_scalarmult_base(bob_pub, bob_priv);

#ifdef ENERGY_MODE
    TriggerInit();
    TriggerLow();

    static uint32_t s_cycles[REPS][2];
    static uint32_t s_stack[REPS][2];

    for (int i = 0; i < REPS; i++)
    {
        StackPaint();
        TriggerHigh();
        dwt_reset();
        crypto_scalarmult_base(alice_pub, alice_priv);
        c = dwt_get();
        TriggerLow();
        s_cycles[i][0] = c;
        s_stack[i][0] = StackHighWaterMarkBytes();
        InterOpGap();

        StackPaint();
        TriggerHigh();
        dwt_reset();
        crypto_scalarmult(shared_alice, alice_priv, bob_pub);
        c = dwt_get();
        TriggerLow();
        s_cycles[i][1] = c;
        s_stack[i][1] = StackHighWaterMarkBytes();
        InterOpGap();
    }

    PRINTF("op,cycles,stack_hwm_bytes\r\n");
    for (int i = 0; i < REPS; i++)
    {
        PRINTF("keypair,%d,%d\r\n", (int)s_cycles[i][0], (int)s_stack[i][0]);
        PRINTF("shared_secret,%d,%d\r\n", (int)s_cycles[i][1], (int)s_stack[i][1]);
    }
#else
    PRINTF("op,cycles,stack_hwm_bytes\r\n");

    for (int i = 0; i < REPS; i++)
    {
        StackPaint();
        dwt_reset();
        crypto_scalarmult_base(alice_pub, alice_priv);
        c = dwt_get();
        PRINTF("keypair,%d,%d\r\n", (int)c, (int)StackHighWaterMarkBytes());

        StackPaint();
        dwt_reset();
        crypto_scalarmult(shared_alice, alice_priv, bob_pub);
        c = dwt_get();
        PRINTF("shared_secret,%d,%d\r\n", (int)c, (int)StackHighWaterMarkBytes());
    }
#endif

    /* Correctness check: both parties must derive the identical
     * shared secret from their own private key and the other's
     * public key -- the fundamental Diffie-Hellman property. Analogous
     * to mlkem_bench's kem_match check. */
    crypto_scalarmult(shared_bob, bob_priv, alice_pub);
    int ok = 1;
    for (int i = 0; i < 32; i++)
    {
        if (shared_alice[i] != shared_bob[i]) ok = 0;
    }
    PRINTF("dh_match,%d\r\n", ok);

    PRINTF("done\r\n");
    while (1) { }
}
