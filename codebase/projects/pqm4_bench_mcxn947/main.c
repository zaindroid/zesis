/* pqm4 benchmark main — measures pqm4 (M-profile optimized) PQC on MCXN947.
 *
 * Build one algorithm+level at a time (symbols are unprefixed):
 *   -DALG=MLKEM -DLEVEL=768 -DVARIANT=m4fspeed   -> ML-KEM-768 m4f
 *   -DALG=MLDSA -DLEVEL=44  -DVARIANT=m4f         -> ML-DSA-44 m4f
 * Compiles the pqm4 sources from codebase/pqm4/crypto_{kem,sign}/...
 *
 * Free-running (reset to start), DWT timing, stack painting.
 * Output: PQM4_BEGIN, per-op rows, PQM4_END.
 */
#include "app.h"
#include "board.h"
#include "fsl_debug_console.h"
#include "dwt.h"

#include "api.h"

/* ---- stack painting (from mldsa_bench_nxp/dwt.h pattern) ---- */
extern char __StackLimit[];
extern char __StackTop[];
#define STACK_MARGIN 128

/* ---- Exp 2: M4F->M33 fault post-mortem. Override the weak SDK
 * HardFault_Handler: capture CFSR/HFSR/MMFAR/BFAR and the stacked PC, print
 * them, then hang. (The m4f asm faults on M33; this tells us exactly why.) */
#define SCB_CFSR   (*(volatile uint32_t *)0xE000ED28u)
#define SCB_HFSR   (*(volatile uint32_t *)0xE000ED2Cu)
#define SCB_MMFAR  (*(volatile uint32_t *)0xE000ED34u)
#define SCB_BFAR   (*(volatile uint32_t *)0xE000ED38u)

void HardFault_Handler(void)
{
    uint32_t cfsr = SCB_CFSR, hfsr = SCB_HFSR;
    uint32_t mmfar = SCB_MMFAR, bfar = SCB_BFAR;
    uint32_t sp;
    __asm volatile("mrs %0, msp" : "=r"(sp));
    uint32_t stacked_pc = *((volatile uint32_t *)(sp + 24u));
    uint32_t stacked_lr = *((volatile uint32_t *)(sp + 20u));
    PRINTF("\r\n=== HardFault (M4F asm on M33) ===\r\n");
    PRINTF("CFSR  =0x%08X  HFSR  =0x%08X\r\n", (unsigned)cfsr, (unsigned)hfsr);
    PRINTF("MMFAR =0x%08X  BFAR  =0x%08X\r\n", (unsigned)mmfar, (unsigned)bfar);
    PRINTF("stacked PC=0x%08X  stacked LR=0x%08X\r\n",
           (unsigned)stacked_pc, (unsigned)stacked_lr);
    if (cfsr & (1u << 31)) PRINTF("  [IACCVIOL] instruction access violation\r\n");
    if (cfsr & (1u << 30)) PRINTF("  [DACCVIOL] data access violation (addr 0x%08X)\r\n", (unsigned)mmfar);
    if (cfsr & (1u << 24)) PRINTF("  [UNALIGNED] unaligned access fault\r\n");
    if (cfsr & (1u << 16)) PRINTF("  [UNDEFINSTR] undefined instruction\r\n");
    if (cfsr & (1u << 15)) PRINTF("  [INVSTATE] invalid EPSR.T (Thumb bit) state\r\n");
    if (cfsr & (1u << 14)) PRINTF("  [INVPC] invalid PC load\r\n");
    if (cfsr & (1u << 13)) PRINTF("  [NOCP] no coprocessor\r\n");
    if (hfsr & (1u << 30)) PRINTF("  [FORCED] escalated to HardFault\r\n");
    for (volatile uint32_t d = 0; d < 5000000u; d++) { }
    while (1) { }
}

#if 1
static void StackPaint(void)
{
    volatile char *p = __StackLimit;
    while (p < __StackTop - STACK_MARGIN) { *p = 0xAA; p++; }
}
#endif
#if 0
static size_t StackHighWaterMarkBytes(void)
{
    volatile char *p = __StackLimit;
    while (p < __StackTop - STACK_MARGIN && *p == 0xAA) { p++; }
    return (size_t)((__StackTop - STACK_MARGIN) - p);
}
#endif

/* ---- config ---- */
#ifndef ALG_MLKEM
#define ALG_MLKEM 0
#endif
#ifndef ALG_MLDSA
#define ALG_MLDSA 0
#endif
#define ALG_IS_MLKEM ALG_MLKEM
#define ALG_IS_MLDSA ALG_MLDSA
#ifndef LEVEL
#define LEVEL 768
#endif
#ifndef REPS
#define REPS 100
#endif

/* ML-KEM sizes */
#define MLKEM_PK_768 1184
#define MLKEM_SK_768 2400
#define MLKEM_CT_768 1088
#define MLKEM_SS_768 32
#define MLKEM_PK_512 800
#define MLKEM_SK_512 1632
#define MLKEM_CT_512 768
#define MLKEM_SS_512 32
#define MLKEM_PK_1024 1568
#define MLKEM_SK_1024 3168
#define MLKEM_CT_1024 1568
#define MLKEM_SS_1024 32

/* ML-DSA sizes */
#define MLDSA_PK_44 1312
#define MLDSA_SK_44 2560
#define MLDSA_SIG_44 2420
#define MLDSA_PK_65 1952
#define MLDSA_SK_65 4032
#define MLDSA_SIG_65 3309
#define MLDSA_PK_87 2592
#define MLDSA_SK_87 4896
#define MLDSA_SIG_87 4627

static uint32_t s_cycles[REPS][4]; /* per-rep op cycles */
static uint8_t s_msg[32];

#if ALG_IS_MLKEM
#if LEVEL == 512
#define PKB MLKEM_PK_512
#define SKB MLKEM_SK_512
#define CTB MLKEM_CT_512
#define SSB MLKEM_SS_512
#elif LEVEL == 1024
#define PKB MLKEM_PK_1024
#define SKB MLKEM_SK_1024
#define CTB MLKEM_CT_1024
#define SSB MLKEM_SS_1024
#else
#define PKB MLKEM_PK_768
#define SKB MLKEM_SK_768
#define CTB MLKEM_CT_768
#define SSB MLKEM_SS_768
#endif
static uint8_t pk[PKB] __attribute__((aligned(8))), sk[SKB] __attribute__((aligned(8))), ct[CTB] __attribute__((aligned(8))), ss1[SSB];
#else /* MLDSA */
#if LEVEL == 44
#define PKB MLDSA_PK_44
#define SKB MLDSA_SK_44
#define SIGB MLDSA_SIG_44
#elif LEVEL == 65
#define PKB MLDSA_PK_65
#define SKB MLDSA_SK_65
#define SIGB MLDSA_SIG_65
#else
#define PKB MLDSA_PK_87
#define SKB MLDSA_SK_87
#define SIGB MLDSA_SIG_87
#endif
static uint8_t pk[PKB] __attribute__((aligned(8))), sk[SKB] __attribute__((aligned(8))), sig[SIGB] __attribute__((aligned(8)));
static size_t siglen;
#endif

static void RunIter(int i)
{
#if ALG_IS_MLKEM
    dwt_reset(); crypto_kem_keypair(pk, sk); s_cycles[i][0] = dwt_get();
#ifndef SKIP_ENC
    dwt_reset(); crypto_kem_enc(ct, ss1, pk); s_cycles[i][1] = dwt_get();
#endif
    s_cycles[i][2] = 0; /* decap: m4f asm faults on M33 (documented) */
    s_cycles[i][3] = 0;
#else
    dwt_reset();
    PRINTF("kp.."); crypto_sign_keypair(pk, sk); PRINTF("ok ");
    s_cycles[i][0] = dwt_get();
    StackPaint(); dwt_reset();
    siglen = 0;
    PRINTF("sg.."); crypto_sign_signature(sig, &siglen, s_msg, 32, sk); PRINTF("ok ");
    s_cycles[i][1] = dwt_get();
    StackPaint(); dwt_reset();
    PRINTF("vf.."); crypto_sign_verify(sig, siglen, s_msg, 32, pk); PRINTF("ok ");
    s_cycles[i][2] = dwt_get();
    s_cycles[i][3] = 0;
#endif
}

int main(void)
{
    BOARD_InitHardware();
    dwt_init();

    for (int i = 0; i < 32; i++) s_msg[i] = (uint8_t)(i * 3 + 1);

    PRINTF("\r\nPQM4_BEGIN alg=%s level=%d\r\n",
#if ALG_IS_MLKEM
           "MLKEM",
#else
           "MLDSA",
#endif
           LEVEL);

    /* ENERGY MODE (reset-loop): the m4f asm corrupts state after the first
       kp+enc (second call hangs). So run ONE kp+enc per boot, then software-
       reset. The PPK2 sees repeated clean crypto windows. */
    RunIter(0);
    PRINTF("CYCLE_DONE\r\n");
    for (volatile uint32_t d = 0; d < 100000; d++) { }
    NVIC_SystemReset();

    PRINTF("op,cycles,stack_hwm\r\n");
#if ALG_IS_MLKEM
    for (int i = 0; i < REPS; i++)
        PRINTF("kp,%u,%u\r\nenc,%u,%u\r\ndec,%u,%u\r\n",
               (unsigned)s_cycles[i][0], 0u,
               (unsigned)s_cycles[i][1], 0u,
               (unsigned)s_cycles[i][2], 0u);
#else
    for (int i = 0; i < REPS; i++)
        PRINTF("kp,%u,%u\r\nsign,%u,%u\r\nvrfy,%u,%u\r\n",
               (unsigned)s_cycles[i][0], 0u,
               (unsigned)s_cycles[i][1], 0u,
               (unsigned)s_cycles[i][2], 0u);
#endif
    PRINTF("PQM4_END\r\n");
    while (1) { }
}
