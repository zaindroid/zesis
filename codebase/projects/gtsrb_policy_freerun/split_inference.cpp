/* SPLIT_INFERENCE benchmark (Option B): hybrid PQC privacy-layer overhead.
 *
 * Measures the cost of protecting AI intermediate features with the
 * NIST-recommended hybrid ML-KEM-768 + AES-128-GCM construction:
 *   - ONE-TIME: ML-KEM-768 key agreement (keypair+enc+dec) = session setup
 *   - PER FRAME: AES-GCM encrypt + decrypt of the block3 feature tensor
 *     (4608 bytes, the segA->segB handoff size) = per-frame privacy cost
 *
 * Free-running (reset to start), results dumped after. For PPK2 energy
 * capture: arm PPK2, reset, capture the session (setup + N frames).
 *
 * Output: SPLIT_BEGIN, setup_us, N x "frame,<i>,<encrypt_us>,<decrypt_us>",
 * SPLIT_END.
 */
#include "board_init.h"
#include "board.h"
#include "fsl_debug_console.h"
#include "timer.h"
#include "split_aes_gcm.h"

extern "C" {
#include "api.h"   /* PQClean ML-KEM-768 */
}

#define FRAMES 200        /* frames per session (amortization test) */
#define FEAT_BYTES 4608   /* block3 features: 12x12x32 int8 */

/* ML-KEM-768 sizes (PQClean) */
#define PK_BYTES 1184
#define SK_BYTES 2400
#define CT_BYTES 1088
#define SS_BYTES 32

static uint8_t s_pk[PK_BYTES];
static uint8_t s_sk[SK_BYTES];
static uint8_t s_ct[CT_BYTES];
static uint8_t s_ss_a[SS_BYTES];  /* edge side */
static uint8_t s_ss_b[SS_BYTES];  /* cloud side */

/* feature tensor buffers */
static uint8_t s_feat[FEAT_BYTES] __attribute__((aligned(16)));
static uint8_t s_feat_ct[FEAT_BYTES + 16] __attribute__((aligned(16)));
static uint8_t s_feat_pt[FEAT_BYTES] __attribute__((aligned(16)));
static uint8_t s_tag[16];

static uint32_t s_enc_us[FRAMES];
static uint32_t s_dec_us[FRAMES];

int main(void)
{
    BOARD_Init();
    TIMER_Init();

    /* ---- session setup: ML-KEM-768 key agreement (one-time) ---- */
    uint32_t t0 = (uint32_t)TIMER_GetTimeInUS();
    PQCLEAN_MLKEM768_CLEAN_crypto_kem_keypair(s_pk, s_sk);
    PQCLEAN_MLKEM768_CLEAN_crypto_kem_enc(s_ct, s_ss_a, s_pk);
    PQCLEAN_MLKEM768_CLEAN_crypto_kem_dec(s_ss_b, s_ct, s_sk);
    uint32_t setup_us = (uint32_t)TIMER_GetTimeInUS() - t0;

    PRINTF("\r\nSPLIT_BEGIN frames=%d feat_bytes=%d\r\n", FRAMES, FEAT_BYTES);
    PRINTF("setup_us=%u (ML-KEM-768 keypair+enc+dec)\r\n", (unsigned)setup_us);

    /* fixed IV/AAD (in a real split-inference system the IV is per-frame;
     * here we reuse it to isolate the pure crypto cost) */
    uint8_t iv[12] = {0,1,2,3,4,5,6,7,8,9,10,11};
    const uint8_t aad[8] = {0x50,0x51,0x4c,0x32,0x53,0x50,0x4c,0x49}; /* "PQCSPLI" */

    /* fill feature tensor with deterministic data */
    for (int i = 0; i < FEAT_BYTES; i++) s_feat[i] = (uint8_t)(i * 7 + 3);

    for (int i = 0; i < FRAMES; i++)
    {
        /* edge encrypts the features before "transmission" */
        uint32_t e0 = (uint32_t)TIMER_GetTimeInUS();
        aes_gcm_encrypt(s_ss_a, iv, aad, 8, s_feat, FEAT_BYTES, s_feat_ct, s_tag);
        uint32_t e1 = (uint32_t)TIMER_GetTimeInUS();
        /* cloud decrypts and verifies the tag */
        int ok = aes_gcm_decrypt(s_ss_b, iv, aad, 8, s_feat_ct, FEAT_BYTES, s_feat_pt, s_tag);
        uint32_t e2 = (uint32_t)TIMER_GetTimeInUS();
        if (i < 3) PRINTF("dbg frame %d ok=%d enc=%u dec=%u\r\n", i, ok, (unsigned)(e1-e0), (unsigned)(e2-e1));
        s_enc_us[i] = e1 - e0;
        s_dec_us[i] = e2 - e1;
        if (ok != 0) { PRINTF("TAG_MISMATCH at frame %d\r\n", i); while(1); }
    }

    PRINTF("frame,encrypt_us,decrypt_us\r\n");
    for (int i = 0; i < FRAMES; i++)
        PRINTF("frame,%u,%u\r\n", (unsigned)s_enc_us[i], (unsigned)s_dec_us[i]);
    PRINTF("SPLIT_END\r\n");
    while (1) { }
}
