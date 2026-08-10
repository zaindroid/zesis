#include "board.h"
#include "app.h"
#include "mcmgr.h"
#include "api.h"

/* Set to 1 for CONTENTION run (crypto hammering),
   0 for BASELINE run (core 1 idle). */
#define CORE1_CRYPTO 1

static uint8_t pk[PQCLEAN_MLKEM1024_CLEAN_CRYPTO_PUBLICKEYBYTES];
static uint8_t sk[PQCLEAN_MLKEM1024_CLEAN_CRYPTO_SECRETKEYBYTES];
static uint8_t ct[PQCLEAN_MLKEM1024_CLEAN_CRYPTO_CIPHERTEXTBYTES];
static uint8_t ss[PQCLEAN_MLKEM1024_CLEAN_CRYPTO_BYTES];

int main(void)
{
    uint32_t startupData;
    mcmgr_status_t status;

    BOARD_InitHardware();
    (void)MCMGR_Init();

    do {
        status = MCMGR_GetStartupData(kMCMGR_Core0, &startupData);
    } while (status != kStatus_MCMGR_Success);

#if CORE1_CRYPTO
    PQCLEAN_MLKEM1024_CLEAN_crypto_kem_keypair(pk, sk);
    LED_INIT();
    for (;;)
    {
        PQCLEAN_MLKEM1024_CLEAN_crypto_kem_enc(ct, ss, pk);
        PQCLEAN_MLKEM1024_CLEAN_crypto_kem_dec(ss, ct, sk);
        LED_TOGGLE();
    }
#else
    (void)pk; (void)sk; (void)ct; (void)ss;
    for (;;) { }
#endif
}
