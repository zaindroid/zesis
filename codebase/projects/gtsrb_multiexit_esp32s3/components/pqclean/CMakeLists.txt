# PQClean ML-KEM-768 (C implementation) as an ESP-IDF component.
idf_component_register(
    SRCS
        cbd.c
        fips202.c
        indcpa.c
        kem.c
        ntt.c
        poly.c
        polyvec.c
        randombytes.c
        reduce.c
        symmetric-shake.c
        verify.c
    INCLUDE_DIRS "."
)
