/* Exit-leakage capture firmware (Experiment #3).
 *
 * Question: can a power-watching attacker (10kHz PPK2) tell WHICH perception
 * exit (1/2/3) the multi-exit model took, from the power envelope alone?
 * If yes, the certified-anytime system leaks its confidence decision --
 * an attack on the certification itself (an attacker learns when the model
 * is 'confident enough to stop').
 *
 * Design (same proven pattern as the ACTIVITY firmware):
 *  - For each embedded image, run the multi-exit chain EXIT-BY-EXIT with a
 *    LONG gap between exits (10ms+) so each exit's inference is a separate
 *    segmentable burst at 10kHz.
 *  - P0_31 (Arduino D7) toggles HIGH during each exit's inference.
 *  - Serial logs the order: "frame,<i>,exit,<1|2|3>" AFTER each exit's burst
 *    (labels matched to the PPK2 trace by burst count).
 *  - To get ALL THREE exits per image (not policy-gated), we force-run each
 *    exit on every image regardless of confidence -- so we capture the pure
 *    per-exit power signature, not the policy decision. The policy's exit
 *    choice is then a LATER label we can attach from the predictions.
 *
 * Output: EXIT_BEGIN, N frames x (3 exit bursts + labels), EXIT_END.
 */
#include "board_init.h"
#include "board.h"
#include "fsl_debug_console.h"
#include "timer.h"
#include "segments.h"
#include "embedded_images.h"

#include "fsl_gpio.h"
#include "fsl_port.h"

#define TRIGGER_GPIO GPIO0
#define TRIGGER_PIN  31U   /* P0_31 (Arduino D7) - verified toggling */

#define N_IMAGES 60         /* enough for train/test (3 exits each = 180 bursts) */
#define IMAGE_BYTES 6912     /* 48x48x3 int8 */
#define GAP_LOOPS 1500000u  /* ~10ms at 150MHz */

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

static void Gap(void) { for (volatile uint32_t i = 0; i < GAP_LOOPS; i++) { } }

int main(void)
{
    BOARD_Init();
    TIMER_Init();
    TriggerInit();

    if (!SEGA_Init() || !SEGB_Init() || !SEGC_Init()) {
        PRINTF("SEG INIT FAILED\r\n");
        while (1) { }
    }

    PRINTF("\r\nEXIT_BEGIN images=%d\r\n", N_IMAGES);

    for (int i = 0; i < N_IMAGES; i++)
    {
        const int8_t* img = embedded_images[i];

        /* EXIT 1: segA only */
        Gap();
        memcpy(SEGA_Input()->data.int8, img, IMAGE_BYTES);
        TriggerHigh();
        SEGA_Invoke();
        TriggerLow();
        Gap();
        PRINTF("frame,%d,exit,1\r\n", i);

        /* EXIT 2: segA -> segB */
        Gap();
        TfLiteTensor* bf1 = SEGA_OutputFeatures();
        memcpy(SEGB_Input()->data.int8, bf1->data.int8, bf1->bytes);
        TriggerHigh();
        SEGB_Invoke();
        TriggerLow();
        Gap();
        PRINTF("frame,%d,exit,2\r\n", i);

        /* EXIT 3: segA -> segB -> segC */
        Gap();
        TfLiteTensor* bf2 = SEGB_OutputFeatures();
        memcpy(SEGC_Input()->data.int8, bf2->data.int8, bf2->bytes);
        TriggerHigh();
        SEGC_Invoke();
        TriggerLow();
        Gap();
        PRINTF("frame,%d,exit,3\r\n", i);
    }

    PRINTF("EXIT_END\r\n");
    while (1) { }
}
