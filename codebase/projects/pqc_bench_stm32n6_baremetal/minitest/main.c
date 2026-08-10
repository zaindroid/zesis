/* Minimal UART test — CMSIS typedefs only, no HAL init, no PWR.
 * Verifies a ROM-DFU-loaded bare-metal app can print to USART1 (PE5/PE6 -> COM10).
 * Uses the Secure (S) peripheral bases (app runs secure per ROM boot). */
#include <stdint.h>

#define PERIPH_BASE_S   0x50000000UL
#define APB2PERIPH_BASE_S (PERIPH_BASE_S + 0x02000000UL)
#define AHB4PERIPH_BASE_S (PERIPH_BASE_S + 0x06020000UL)
#define USART1_BASE_S    (APB2PERIPH_BASE_S + 0x1000UL)
#define GPIOE_BASE_S     (AHB4PERIPH_BASE_S + 0x1000UL)
#define RCC_BASE_S       (AHB4PERIPH_BASE_S + 0x8000UL)

/* Register offsets (from stm32n657xx.h) */
#define RCC_AHB4ENSR_OFF 0x0A5C
#define RCC_APB2ENSR_OFF 0x0A6C
#define GPIO_MODER_OFF   0x00
#define GPIO_AFRL_OFF    0x20
#define USART_CR1_OFF    0x00
#define USART_BRR_OFF    0x0C
#define USART_ISR_OFF    0x1C
#define USART_TDR_OFF    0x28

static volatile uint32_t *RCC_AHB4ENSR = (uint32_t *)(RCC_BASE_S + RCC_AHB4ENSR_OFF);
static volatile uint32_t *RCC_APB2ENSR = (uint32_t *)(RCC_BASE_S + RCC_APB2ENSR_OFF);
static volatile uint32_t *GPIOE_MODER = (uint32_t *)(GPIOE_BASE_S + GPIO_MODER_OFF);
static volatile uint32_t *GPIOE_AFRL  = (uint32_t *)(GPIOE_BASE_S + GPIO_AFRL_OFF);
static volatile uint32_t *USART_CR1   = (uint32_t *)(USART1_BASE_S + USART_CR1_OFF);
static volatile uint32_t *USART_BRR   = (uint32_t *)(USART1_BASE_S + USART_BRR_OFF);
static volatile uint32_t *USART_ISR   = (uint32_t *)(USART1_BASE_S + USART_ISR_OFF);
static volatile uint32_t *USART_TDR   = (uint32_t *)(USART1_BASE_S + USART_TDR_OFF);

static void putc(char c) {
    while (!(*USART_ISR & 0x80)) {}       /* TXE */
    *USART_TDR = (uint32_t)(uint8_t)c;
}
static void puts(const char *s) { while (*s) putc(*s++); }

int main(void) {
    *RCC_AHB4ENSR |= (1u << 4);           /* GPIOE clock (GPIOEENS) */
    *RCC_APB2ENSR |= (1u << 4);           /* USART1 clock (USART1ENS) */
    *GPIOE_MODER = (*GPIOE_MODER & ~((3u<<10)|(3u<<12))) | ((2u<<10)|(2u<<12)); /* PE5/PE6 AF */
    *GPIOE_AFRL  = (*GPIOE_AFRL & ~(0xFFu<<20)) | (7u<<20);                     /* AF7 */
    *USART_BRR  = 64000000u / 115200u;    /* default 64MHz HSI / 115200 */
    /* CR1 bits: UE=bit0, RE=bit2, TE=bit3 */
    *USART_CR1  = (1u<<0) | (1u<<2) | (1u<<3);
    puts("\r\nMINI_UART_OK\r\n");
    while (1) {}
}
