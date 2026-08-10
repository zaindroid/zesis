# PQClean ML-DSA (Dilithium, FIPS 204) levels 44/65/87 as an ESP-IDF component.
# Same integration path as the pqclean (ML-KEM) component. Each level is a
# standalone "clean" C implementation sharing the randombytes stub.
idf_component_register(
    SRCS
        randombytes.c
        ml-dsa-44/ntt.c
        ml-dsa-44/packing.c
        ml-dsa-44/poly.c
        ml-dsa-44/polyvec.c
        ml-dsa-44/reduce.c
        ml-dsa-44/rounding.c
        ml-dsa-44/sign.c
        ml-dsa-44/symmetric-shake.c
        ml-dsa-65/ntt.c
        ml-dsa-65/packing.c
        ml-dsa-65/poly.c
        ml-dsa-65/polyvec.c
        ml-dsa-65/reduce.c
        ml-dsa-65/rounding.c
        ml-dsa-65/sign.c
        ml-dsa-65/symmetric-shake.c
        ml-dsa-87/ntt.c
        ml-dsa-87/packing.c
        ml-dsa-87/poly.c
        ml-dsa-87/polyvec.c
        ml-dsa-87/reduce.c
        ml-dsa-87/rounding.c
        ml-dsa-87/sign.c
        ml-dsa-87/symmetric-shake.c
    INCLUDE_DIRS "."
                 "ml-dsa-44"
                 "ml-dsa-65"
                 "ml-dsa-87"
)
