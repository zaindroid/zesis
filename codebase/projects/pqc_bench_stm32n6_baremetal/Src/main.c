/*
 * Bare-metal PQC benchmark for STM32N6570-DK (Cortex-M55 @ 800 MHz)
 * ML-KEM-768 + ML-DSA-44/65/87 — identical methodology to the Zephyr
 * builds on MCXN947 / ESP32-S3 (PQClean clean-C, xorshift randombytes stub,
 * DWT cycle counting).
 *
 * Loaded via USB DFU (ROM serial boot) as a RAMLOAD image; console = USART1
 * (PE5/PE6) @ 115200 8N1, matching the board's ST-Link VCOM.
 *
 * INSECURE randombytes stub — benchmarking only.
 */

#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>

#include "stm32n6xx_hal.h"
#include "mlkem768/api.h"
#include "mldsa44/api.h"
#include "mldsa65/api.h"
#include "mldsa87/api.h"

UART_HandleTypeDef huart1;

/* Rejection-retry counters instrumented into the PQClean sign.c sources */
extern void PQCLEAN_MLDSA44_CLEAN_bench_reset_rejections(void);
extern uint32_t PQCLEAN_MLDSA44_CLEAN_bench_get_rejections(void);
extern void PQCLEAN_MLDSA65_CLEAN_bench_reset_rejections(void);
extern uint32_t PQCLEAN_MLDSA65_CLEAN_bench_get_rejections(void);
extern void PQCLEAN_MLDSA87_CLEAN_bench_reset_rejections(void);
extern uint32_t PQCLEAN_MLDSA87_CLEAN_bench_get_rejections(void);

/* ------------------------------------------------------------------ */
/*  UART helpers (polling transmit — simple, reliable for benchmarking) */
/* ------------------------------------------------------------------ */
static void uart_putc(char c)
{
    uint8_t b = (uint8_t)c;
    HAL_UART_Transmit(&huart1, &b, 1, HAL_MAX_DELAY);
}

static void uart_puts(const char *s)
{
    while (*s) uart_putc(*s++);
}

static void uart_putu32(uint32_t v)
{
    char buf[12];
    int i = 0;
    if (v == 0) { uart_putc('0'); return; }
    while (v > 0 && i < 11) { buf[i++] = '0' + (v % 10); v /= 10; }
    while (i > 0) uart_putc(buf[--i]);
}

/* ------------------------------------------------------------------ */
/*  Cycle counter (DWT CYCCNT on Cortex-M55)                            */
/* ------------------------------------------------------------------ */
static inline uint32_t now_cycles(void)
{
    return DWT->CYCCNT;
}

#define CPU_HZ 800000000u
#define US_PER_CYCLE_NS 1.25f /* 800 MHz */

/* ------------------------------------------------------------------ */
/*  Benchmark parameters (identical to Zephyr run)                      */
/* ------------------------------------------------------------------ */
#define KEM_REPS      100
#define DSA_KP_REPS   100
#define DSA_VF_REPS   100
#define DSA_SIGN_REPS 2000
#define MSG_LEN       32

/* Results (static — fit in RAM) */
static uint32_t kem_kp_c[KEM_REPS], kem_enc_c[KEM_REPS], kem_dec_c[KEM_REPS];
static uint32_t dsa_kp_c[3][DSA_KP_REPS], dsa_vf_c[3][DSA_VF_REPS];
static uint32_t dsa_sig_c[3][DSA_SIGN_REPS];
static uint16_t dsa_ret[3][DSA_SIGN_REPS];
static uint8_t  dsa_fail[3][DSA_SIGN_REPS];

/* Buffer reuse: ML-DSA-87 has the largest sizes */
static uint8_t dsa_pk[PQCLEAN_MLDSA87_CLEAN_CRYPTO_PUBLICKEYBYTES];
static uint8_t dsa_sk[PQCLEAN_MLDSA87_CLEAN_CRYPTO_SECRETKEYBYTES];
static uint8_t dsa_sig[PQCLEAN_MLDSA87_CLEAN_CRYPTO_BYTES];
static uint8_t dsa_msg[MSG_LEN];

static uint8_t pk[PQCLEAN_MLKEM768_CLEAN_CRYPTO_PUBLICKEYBYTES];
static uint8_t sk[PQCLEAN_MLKEM768_CLEAN_CRYPTO_SECRETKEYBYTES];
static uint8_t ct[PQCLEAN_MLKEM768_CLEAN_CRYPTO_CIPHERTEXTBYTES];
static uint8_t ss[PQCLEAN_MLKEM768_CLEAN_CRYPTO_BYTES];
static uint8_t ss2[PQCLEAN_MLKEM768_CLEAN_CRYPTO_BYTES];

/* ------------------------------------------------------------------ */
/*  DSA dispatch                                                       */
/* ------------------------------------------------------------------ */
typedef int (*kp_fn)(uint8_t *, uint8_t *);
typedef int (*sign_fn)(uint8_t *, size_t *, const uint8_t *, size_t, const uint8_t *);
typedef int (*verify_fn)(const uint8_t *, size_t, const uint8_t *, size_t, const uint8_t *);
typedef void (*reset_ret_fn)(void);
typedef uint32_t (*get_ret_fn)(void);

static void dsa_kp(int lv, uint8_t *pk_, uint8_t *sk_) {
    if (lv == 0) PQCLEAN_MLDSA44_CLEAN_crypto_sign_keypair(pk_, sk_);
    if (lv == 1) PQCLEAN_MLDSA65_CLEAN_crypto_sign_keypair(pk_, sk_);
    if (lv == 2) PQCLEAN_MLDSA87_CLEAN_crypto_sign_keypair(pk_, sk_);
}
static int dsa_sign(int lv, uint8_t *s_, size_t *sl, const uint8_t *m, size_t ml, const uint8_t *sk_) {
    if (lv == 0) return PQCLEAN_MLDSA44_CLEAN_crypto_sign_signature(s_, sl, m, ml, sk_);
    if (lv == 1) return PQCLEAN_MLDSA65_CLEAN_crypto_sign_signature(s_, sl, m, ml, sk_);
    return PQCLEAN_MLDSA87_CLEAN_crypto_sign_signature(s_, sl, m, ml, sk_);
}
static int dsa_vfy(int lv, const uint8_t *s_, size_t sl, const uint8_t *m, size_t ml, const uint8_t *pk_) {
    if (lv == 0) return PQCLEAN_MLDSA44_CLEAN_crypto_sign_verify_ctx(s_, sl, m, ml, NULL, 0, pk_);
    if (lv == 1) return PQCLEAN_MLDSA65_CLEAN_crypto_sign_verify_ctx(s_, sl, m, ml, NULL, 0, pk_);
    return PQCLEAN_MLDSA87_CLEAN_crypto_sign_verify_ctx(s_, sl, m, ml, NULL, 0, pk_);
}
static void dsa_reset(int lv) {
    if (lv == 0) PQCLEAN_MLDSA44_CLEAN_bench_reset_rejections();
    if (lv == 1) PQCLEAN_MLDSA65_CLEAN_bench_reset_rejections();
    if (lv == 2) PQCLEAN_MLDSA87_CLEAN_bench_reset_rejections();
}
static uint32_t dsa_get_ret(int lv) {
    if (lv == 0) return PQCLEAN_MLDSA44_CLEAN_bench_get_rejections();
    if (lv == 1) return PQCLEAN_MLDSA65_CLEAN_bench_get_rejections();
    return PQCLEAN_MLDSA87_CLEAN_bench_get_rejections();
}

/* ------------------------------------------------------------------ */
/*  Benchmark runner                                                   */
/* ------------------------------------------------------------------ */
static void run_bench(void)
{
    uint32_t t0, t1;

    uart_puts("\r\nplat,stm32n6570,600000000\r\n");
    uart_puts("PQC_BENCH_START\r\n");

    /* ---- ML-KEM-768 ---- */
    uart_puts("KEM_BEGIN\r\n");
    PQCLEAN_MLKEM768_CLEAN_crypto_kem_keypair(pk, sk);
    for (int i = 0; i < KEM_REPS; i++) {
        t0 = now_cycles();
        PQCLEAN_MLKEM768_CLEAN_crypto_kem_keypair(pk, sk);
        t1 = now_cycles();
        kem_kp_c[i] = t1 - t0;
    }
    for (int i = 0; i < KEM_REPS; i++) {
        t0 = now_cycles();
        PQCLEAN_MLKEM768_CLEAN_crypto_kem_enc(ct, ss, pk);
        t1 = now_cycles();
        kem_enc_c[i] = t1 - t0;
    }
    for (int i = 0; i < KEM_REPS; i++) {
        t0 = now_cycles();
        PQCLEAN_MLKEM768_CLEAN_crypto_kem_dec(ss2, ct, sk);
        t1 = now_cycles();
        kem_dec_c[i] = t1 - t0;
    }
    uart_puts("KEM_END\r\n");
    for (int i = 0; i < KEM_REPS; i++) {
        uart_puts("K,"); uart_putu32(kem_kp_c[i]); uart_putc(',');
        uart_putu32(kem_enc_c[i]); uart_putc(',');
        uart_putu32(kem_dec_c[i]); uart_putc('\r'); uart_putc('\n');
    }

    /* ---- ML-DSA levels ---- */
    for (int lv = 0; lv < 3; lv++) {
        uart_puts("KP_BEGIN\r\n");
        for (int i = 0; i < DSA_KP_REPS; i++) {
            t0 = now_cycles();
            dsa_kp(lv, dsa_pk, dsa_sk);
            t1 = now_cycles();
            dsa_kp_c[lv][i] = t1 - t0;
        }
        uart_puts("KP_END\r\n");
        for (int i = 0; i < DSA_KP_REPS; i++) {
            uart_puts("K,"); uart_putu32(dsa_kp_c[lv][i]); uart_putc('\r'); uart_putc('\n');
        }

        uart_puts("SIGN_BEGIN\r\n");
        for (int i = 0; i < DSA_SIGN_REPS; i++) {
            for (int j = 0; j < MSG_LEN; j++) dsa_msg[j] = (uint8_t)(i + j * 7 + 1);
            dsa_reset(lv);
            t0 = now_cycles();
            int rc = dsa_sign(lv, dsa_sig, &(size_t){0}, dsa_msg, MSG_LEN, dsa_sk);
            t1 = now_cycles();
            dsa_sig_c[lv][i] = t1 - t0;
            dsa_ret[lv][i] = (uint16_t)dsa_get_ret(lv);
            dsa_fail[lv][i] = (rc != 0) ? 1 : 0;
        }
        uart_puts("SIGN_END\r\n");
        for (int i = 0; i < DSA_SIGN_REPS; i++) {
            uart_puts("S,"); uart_putu32(dsa_sig_c[lv][i]); uart_putc(',');
            uart_putu32(dsa_ret[lv][i]); uart_putc(',');
            uart_putu32(dsa_fail[lv][i]); uart_putc('\r'); uart_putc('\n');
        }

        uart_puts("VF_BEGIN\r\n");
        for (int i = 0; i < DSA_VF_REPS; i++) {
            for (int j = 0; j < MSG_LEN; j++) dsa_msg[j] = (uint8_t)(i + j * 3 + 2);
            size_t siglen = 0;
            dsa_sign(lv, dsa_sig, &siglen, dsa_msg, MSG_LEN, dsa_sk);
            t0 = now_cycles();
            int rc = dsa_vfy(lv, dsa_sig, siglen, dsa_msg, MSG_LEN, dsa_pk);
            t1 = now_cycles();
            dsa_vf_c[lv][i] = t1 - t0;
            if (rc != 0) dsa_fail[lv][i] = 2;
        }
        uart_puts("VF_END\r\n");
        for (int i = 0; i < DSA_VF_REPS; i++) {
            uart_puts("V,"); uart_putu32(dsa_vf_c[lv][i]); uart_putc('\r'); uart_putc('\n');
        }
    }

    uart_puts("BENCH_COMPLETE\r\n");
}

/* ------------------------------------------------------------------ */
/*  System init (from the UART example FSBL)                           */
/* ------------------------------------------------------------------ */
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_USART1_UART_Init(void);

static void Error_Handler(void) { while (1) {} }

static void early_uart_init(void)
{
    /* Direct USART1 init at default clock — no HAL dependency, so we can
     * print even if the full HAL init hangs. PE5=TX, PE6=RX, AF7. */
    RCC->AHB4ENSR |= RCC_AHB4ENSR_GPIOEENS;
    RCC->APB2ENSR |= RCC_APB2ENSR_USART1ENS;
    GPIOE->MODER = (GPIOE->MODER & ~(3u << 10)) | (2u << 10); /* PE5 AF */
    GPIOE->MODER = (GPIOE->MODER & ~(3u << 12)) | (2u << 12); /* PE6 AF */
    GPIOE->AFR[0] = (GPIOE->AFR[0] & ~(0xFFu << 20)) | (7u << 20); /* AF7 */
    USART1->BRR = 64000000u / 115200u;  /* default clock / baud */
    USART1->CR1 = USART_CR1_TE | USART_CR1_RE | USART_CR1_UE;
}

static void early_putc(char c)
{
    while (!(USART1->ISR & USART_ISR_TXE_TXFNF)) {}
    USART1->TDR = (uint8_t)c;
}

static void early_puts(const char *s)
{
    while (*s) early_putc(*s++);
}

int main(void)
{
    /* Early UART so we can see output even if HAL init hangs */
    early_uart_init();
    early_puts("\r\nPQC_BARE_METAL_START\r\n");

    /* Enable CPU caches */
    SCB_EnableICache();
    SCB_EnableDCache();

    HAL_Init();

    /* Fix to enable apb clks */
    RCC->BUSENSR = 0xFFFFFFFF;

    /* Power settings */
    HAL_PWREx_EnableVddA();
    HAL_PWREx_EnableVddIO2();
    HAL_PWREx_EnableVddIO3();
    HAL_PWREx_EnableVddIO4();
    HAL_PWREx_EnableVddIO5();


    /* Set back system and CPU clock source to HSI */
    __HAL_RCC_CPUCLK_CONFIG(RCC_CPUCLKSOURCE_HSI);
    __HAL_RCC_SYSCLK_CONFIG(RCC_SYSCLKSOURCE_HSI);

    SystemClock_Config();
    MX_GPIO_Init();
    MX_USART1_UART_Init();

    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk; /* enable cycle counter */

    run_bench();

    while (1) {}
}

void SystemClock_Config(void)
{
    RCC_OscInitTypeDef RCC_OscInitStruct = {0};
    RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

    if (HAL_PWREx_ConfigSupply(PWR_EXTERNAL_SOURCE_SUPPLY) != HAL_OK) {
        Error_Handler();
    }
    if (HAL_PWREx_ControlVoltageScaling(PWR_REGULATOR_VOLTAGE_SCALE1) != HAL_OK) {
        Error_Handler();
    }

    /* Enable HSI */
    RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
    RCC_OscInitStruct.HSIState = RCC_HSI_ON;
    RCC_OscInitStruct.HSIDiv = RCC_HSI_DIV1;
    RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
    RCC_OscInitStruct.PLL1.PLLState = RCC_PLL_NONE;
    RCC_OscInitStruct.PLL2.PLLState = RCC_PLL_NONE;
    RCC_OscInitStruct.PLL3.PLLState = RCC_PLL_NONE;
    RCC_OscInitStruct.PLL4.PLLState = RCC_PLL_NONE;
    if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK) {
        Error_Handler();
    }

    /* Switch to HSI first */
    HAL_RCC_GetClockConfig(&RCC_ClkInitStruct);
    if ((RCC_ClkInitStruct.CPUCLKSource == RCC_CPUCLKSOURCE_IC1) ||
        (RCC_ClkInitStruct.SYSCLKSource == RCC_SYSCLKSOURCE_IC2_IC6_IC11)) {
        RCC_ClkInitStruct.ClockType = (RCC_CLOCKTYPE_CPUCLK | RCC_CLOCKTYPE_SYSCLK);
        RCC_ClkInitStruct.CPUCLKSource = RCC_CPUCLKSOURCE_HSI;
        RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_HSI;
        if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct) != HAL_OK) {
            Error_Handler();
        }
    }

    /* PLL1 from HSI */
    RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_NONE;
    RCC_OscInitStruct.PLL1.PLLState = RCC_PLL_ON;
    RCC_OscInitStruct.PLL1.PLLSource = RCC_PLLSOURCE_HSI;
    RCC_OscInitStruct.PLL1.PLLM = 4;
    RCC_OscInitStruct.PLL1.PLLN = 75;
    RCC_OscInitStruct.PLL1.PLLFractional = 0;
    RCC_OscInitStruct.PLL1.PLLP1 = 1;
    RCC_OscInitStruct.PLL1.PLLP2 = 1;
    RCC_OscInitStruct.PLL2.PLLState = RCC_PLL_NONE;
    RCC_OscInitStruct.PLL3.PLLState = RCC_PLL_NONE;
    RCC_OscInitStruct.PLL4.PLLState = RCC_PLL_NONE;
    if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK) {
        Error_Handler();
    }

    /* CPU/SYSCLK from PLL1 via IC */
    RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_CPUCLK | RCC_CLOCKTYPE_HCLK
                                | RCC_CLOCKTYPE_SYSCLK | RCC_CLOCKTYPE_PCLK1
                                | RCC_CLOCKTYPE_PCLK2 | RCC_CLOCKTYPE_PCLK5
                                | RCC_CLOCKTYPE_PCLK4;
    RCC_ClkInitStruct.CPUCLKSource = RCC_CPUCLKSOURCE_IC1;
    RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_IC2_IC6_IC11;
    RCC_ClkInitStruct.AHBCLKDivider = RCC_HCLK_DIV4;
    RCC_ClkInitStruct.APB1CLKDivider = RCC_APB1_DIV1;
    RCC_ClkInitStruct.APB2CLKDivider = RCC_APB2_DIV1;
    RCC_ClkInitStruct.APB4CLKDivider = RCC_APB4_DIV1;
    RCC_ClkInitStruct.APB5CLKDivider = RCC_APB5_DIV1;
    RCC_ClkInitStruct.IC1Selection.ClockSelection = RCC_ICCLKSOURCE_PLL1;
    RCC_ClkInitStruct.IC1Selection.ClockDivider = 2;
    RCC_ClkInitStruct.IC2Selection.ClockSelection = RCC_ICCLKSOURCE_PLL1;
    RCC_ClkInitStruct.IC2Selection.ClockDivider = 3;
    RCC_ClkInitStruct.IC6Selection.ClockSelection = RCC_ICCLKSOURCE_PLL1;
    RCC_ClkInitStruct.IC6Selection.ClockDivider = 4;
    RCC_ClkInitStruct.IC11Selection.ClockSelection = RCC_ICCLKSOURCE_PLL1;
    RCC_ClkInitStruct.IC11Selection.ClockDivider = 3;
    if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct) != HAL_OK) {
        Error_Handler();
    }
}

static void MX_GPIO_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStruct = {0};
    __HAL_RCC_GPIOE_CLK_ENABLE();
    __HAL_RCC_GPIOD_CLK_ENABLE();
    __HAL_RCC_GPIOF_CLK_ENABLE();

    HAL_GPIO_WritePin(GPIOE, GPIO_PIN_5, GPIO_PIN_SET);
    HAL_GPIO_WritePin(GPIOD, GPIO_PIN_5, GPIO_PIN_SET);

    GPIO_InitStruct.Pin = GPIO_PIN_5;
    GPIO_InitStruct.Mode = GPIO_MODE_AF_PP;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_VERY_HIGH;
    GPIO_InitStruct.Alternate = GPIO_AF7_USART1;
    HAL_GPIO_Init(GPIOE, &GPIO_InitStruct);

    GPIO_InitStruct.Pin = GPIO_PIN_6;
    GPIO_InitStruct.Mode = GPIO_MODE_AF_PP;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_VERY_HIGH;
    GPIO_InitStruct.Alternate = GPIO_AF7_USART1;
    HAL_GPIO_Init(GPIOE, &GPIO_InitStruct);
}

static void MX_USART1_UART_Init(void)
{
    huart1.Instance = USART1;
    huart1.Init.BaudRate = 115200;
    huart1.Init.WordLength = UART_WORDLENGTH_8B;
    huart1.Init.StopBits = UART_STOPBITS_1;
    huart1.Init.Parity = UART_PARITY_NONE;
    huart1.Init.Mode = UART_MODE_TX_RX;
    huart1.Init.HwFlowCtl = UART_HWCONTROL_NONE;
    huart1.Init.OverSampling = UART_OVERSAMPLING_16;
    huart1.Init.OneBitSampling = UART_ONE_BIT_SAMPLE_DISABLE;
    huart1.Init.ClockPrescaler = UART_PRESCALER_DIV1;
    huart1.AdvancedInit.AdvFeatureInit = UART_ADVFEATURE_NO_INIT;
    if (HAL_UART_Init(&huart1) != HAL_OK) Error_Handler();
}
