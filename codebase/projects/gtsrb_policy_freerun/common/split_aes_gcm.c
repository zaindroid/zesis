/*
 * Compact AES-128-GCM (reference implementation for overhead measurement).
 * See split_aes_gcm.h. Not for production use — measures the privacy-layer
 * cost profile only.
 */
#include "split_aes_gcm.h"

/* AES S-box */
static const uint8_t SBOX[256] = {
  0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
  0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
  0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
  0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
  0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
  0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
  0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
  0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
  0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
  0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
  0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
  0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
  0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
  0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
  0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
  0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16
};

typedef uint8_t state_t[4][4];
static uint8_t xtime2(uint8_t x){ return (uint8_t)((x<<1)^((x>>7)?0x1b:0)); }
static void aes128_keyexpand(const uint8_t key[16], uint8_t rk[176])
{
    uint8_t temp[4], i, j, k, rcon=1;
    for(i=0;i<16;i++) rk[i]=key[i];
    for(i=4;i<44;i++){
        temp[0]=rk[(i-1)*4+0]; temp[1]=rk[(i-1)*4+1];
        temp[2]=rk[(i-1)*4+2]; temp[3]=rk[(i-1)*4+3];
        if(i%4==0){ k=temp[0]; temp[0]=SBOX[temp[1]]^rcon; temp[1]=SBOX[temp[2]];
                    temp[2]=SBOX[temp[3]]; temp[3]=SBOX[k]; rcon=xtime2(rcon); }
        j=i-4;
        rk[i*4+0]=rk[j*4+0]^temp[0]; rk[i*4+1]=rk[j*4+1]^temp[1];
        rk[i*4+2]=rk[j*4+2]^temp[2]; rk[i*4+3]=rk[j*4+3]^temp[3];
    }
}
static void AddRoundKey(uint8_t round, state_t* st, const uint8_t* rk){
    for(uint8_t i=0;i<4;i++) for(uint8_t j=0;j<4;j++) (*st)[i][j]^=rk[(round*4+i)*4+j];
}
static void SubBytes2(state_t* st){
    for(uint8_t i=0;i<4;i++) for(uint8_t j=0;j<4;j++) (*st)[i][j]=SBOX[(*st)[i][j]];
}
static void ShiftRows2(state_t* st){
    uint8_t tmp;
    tmp=(*st)[0][1];(*st)[0][1]=(*st)[1][1];(*st)[1][1]=(*st)[2][1];(*st)[2][1]=(*st)[3][1];(*st)[3][1]=tmp;
    tmp=(*st)[0][2];(*st)[0][2]=(*st)[2][2];(*st)[2][2]=tmp;
    tmp=(*st)[1][2];(*st)[1][2]=(*st)[3][2];(*st)[3][2]=tmp;
    tmp=(*st)[0][3];(*st)[0][3]=(*st)[3][3];(*st)[3][3]=(*st)[2][3];(*st)[2][3]=(*st)[1][3];(*st)[1][3]=tmp;
}
static void MixColumns2(state_t* st){
    uint8_t i, Tmp, Tm, t;
    for(i=0;i<4;i++){
        t=(*st)[i][0]; Tmp=(*st)[i][0]^(*st)[i][1]^(*st)[i][2]^(*st)[i][3];
        Tm=(*st)[i][0]^(*st)[i][1]; Tm=xtime2(Tm); (*st)[i][0]^=Tm^Tmp;
        Tm=(*st)[i][1]^(*st)[i][2]; Tm=xtime2(Tm); (*st)[i][1]^=Tm^Tmp;
        Tm=(*st)[i][2]^(*st)[i][3]; Tm=xtime2(Tm); (*st)[i][2]^=Tm^Tmp;
        Tm=(*st)[i][3]^t; Tm=xtime2(Tm); (*st)[i][3]^=Tm^Tmp;
    }
}
static void aes128_enc_block(const uint8_t *rk, uint8_t *s)
{
    state_t* st = (state_t*)s;
    uint8_t round;
    AddRoundKey(0, st, rk);
    for(round=1;round<10;round++){ SubBytes2(st); ShiftRows2(st); MixColumns2(st); AddRoundKey(round, st, rk); }
    SubBytes2(st); ShiftRows2(st); AddRoundKey(10, st, rk);
}

/* GHASH: multiply in GF(2^128) with reduction polynomial x^128+x^7+x^2+x+1 */
static void gmul(uint8_t *x, const uint8_t *y)
{
    uint8_t z[16] = {0}, v[16];
    int i, b;
    for (i = 0; i < 16; i++) v[i] = y[i];
    for (i = 0; i < 128; i++) {
        if (x[i >> 3] & (0x80 >> (i & 7))) {
            for (b = 0; b < 16; b++) z[b] ^= v[b];
        }
        {
            uint8_t lsb = v[15] & 1;
            int j;
            for (j = 15; j > 0; j--) v[j] = (uint8_t)((v[j] >> 1) | (v[j-1] << 7));
            v[0] >>= 1;
            if (lsb) v[0] ^= 0xe1;
        }
    }
    for (i = 0; i < 16; i++) x[i] = z[i];
}

static void ghash_update(uint8_t x[16], const uint8_t *h, const uint8_t *blk, size_t len)
{
    uint8_t block[16] = {0};
    size_t i;
    for (i = 0; i < len; i++) block[i] = blk[i];
    for (i = 0; i < 16; i++) x[i] ^= block[i];
    gmul(x, h);
}

static void ghash(const uint8_t *h, const uint8_t *aad, size_t aad_len,
                  const uint8_t *data, size_t data_len, uint8_t out[16])
{
    uint8_t x[16] = {0};
    size_t off = 0;
    /* AAD blocks (each zero-padded to 16) */
    while (off < aad_len) {
        size_t n = (aad_len - off) < 16 ? (aad_len - off) : 16;
        ghash_update(x, h, aad + off, n);
        off += n;
    }
    /* data blocks */
    off = 0;
    while (off < data_len) {
        size_t n = (data_len - off) < 16 ? (data_len - off) : 16;
        ghash_update(x, h, data + off, n);
        off += n;
    }
    /* lengths block */
    uint64_t abits = (uint64_t)aad_len * 8, dbits = (uint64_t)data_len * 8;
    uint8_t lblock[16] = {0};
    lblock[0] = (uint8_t)(abits >> 56); lblock[1] = (uint8_t)(abits >> 48);
    lblock[2] = (uint8_t)(abits >> 40); lblock[3] = (uint8_t)(abits >> 32);
    lblock[4] = (uint8_t)(abits >> 24); lblock[5] = (uint8_t)(abits >> 16);
    lblock[6] = (uint8_t)(abits >> 8);  lblock[7] = (uint8_t)abits;
    lblock[8] = (uint8_t)(dbits >> 56); lblock[9] = (uint8_t)(dbits >> 48);
    lblock[10] = (uint8_t)(dbits >> 40); lblock[11] = (uint8_t)(dbits >> 32);
    lblock[12] = (uint8_t)(dbits >> 24); lblock[13] = (uint8_t)(dbits >> 16);
    lblock[14] = (uint8_t)(dbits >> 8);  lblock[15] = (uint8_t)dbits;
    for (size_t i = 0; i < 16; i++) x[i] ^= lblock[i];
    gmul(x, h);
    for (size_t i = 0; i < 16; i++) out[i] = x[i];
}

static void ctr_encrypt(const uint8_t rk[176], const uint8_t icb[16],
                        const uint8_t *in, size_t in_len, uint8_t *out)
{
    uint8_t cb[16], s[16];
    size_t off = 0;
    for (size_t i = 0; i < 16; i++) cb[i] = icb[i];
    while (off < in_len) {
        for (size_t i = 0; i < 16; i++) s[i] = cb[i];
        aes128_enc_block(rk, s);
        size_t n = (in_len - off) < 16 ? (in_len - off) : 16;
        for (size_t i = 0; i < n; i++) out[off+i] = (uint8_t)(in[off+i] ^ s[i]);
        off += n;
        /* increment cb (32-bit counter) */
        for (int i = 15; i >= 12; i--) { cb[i]++; if (cb[i]) break; }
    }
}

static int gcm_crypt(int encrypt, const uint8_t key[16], const uint8_t iv[12],
                     const uint8_t *aad, size_t aad_len,
                     const uint8_t *in, size_t in_len, uint8_t *out, uint8_t tag[16])
{
    uint8_t rk[176], h[16], j0[16], s[16], tmp[16];
    aes128_keyexpand(key, rk);
    /* H = AES_K(0^128) */
    for (size_t i = 0; i < 16; i++) h[i] = 0;
    aes128_enc_block(rk, h);
    /* J0 = IV || 0x00000001 */
    for (size_t i = 0; i < 12; i++) j0[i] = iv[i];
    j0[12] = j0[13] = j0[14] = 0; j0[15] = 1;
    /* CTR starts at J0+1 for data blocks (J0 itself is the tag mask key) */
    {
        uint8_t icb[16];
        for (size_t i = 0; i < 16; i++) icb[i] = j0[i];
        for (int i = 15; i >= 12; i--) { icb[i]++; if (icb[i]) break; }
        ctr_encrypt(rk, icb, in, in_len, out);
    }
    /* GHASH over AAD || ciphertext */
    ghash(h, aad, aad_len, encrypt ? out : in, in_len, tmp);
    /* S = AES_K(J0) */
    for (size_t i = 0; i < 16; i++) s[i] = j0[i];
    aes128_enc_block(rk, s);
    for (size_t i = 0; i < 16; i++) tag[i] = (uint8_t)(tmp[i] ^ s[i]);
    return 0;
}

int aes_gcm_encrypt(const uint8_t key[16], const uint8_t iv[12],
                    const uint8_t *aad, size_t aad_len,
                    const uint8_t *pt, size_t pt_len,
                    uint8_t *ct, uint8_t tag[16])
{
    return gcm_crypt(1, key, iv, aad, aad_len, pt, pt_len, ct, tag);
}

int aes_gcm_decrypt(const uint8_t key[16], const uint8_t iv[12],
                    const uint8_t *aad, size_t aad_len,
                    const uint8_t *ct, size_t ct_len,
                    uint8_t *pt, const uint8_t tag[16])
{
    uint8_t t2[16];
    gcm_crypt(0, key, iv, aad, aad_len, ct, ct_len, pt, t2);
    int diff = 0;
    for (size_t i = 0; i < 16; i++) diff |= t2[i] ^ tag[i];
    return diff ? -1 : 0;
}
