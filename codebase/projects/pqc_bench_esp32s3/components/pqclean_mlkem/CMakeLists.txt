# PQClean ML-KEM-768. Uses the vendored copy from the Zephyr bench so the same
# source is measured on both boards; PQClean upstream's clean/ variant no longer
# ships verify.c, which the decapsulation path needs.
set(PQC "${CMAKE_CURRENT_LIST_DIR}/../../../pqc_bench_zephyr/pqclean")

idf_component_register(
    SRCS "${PQC}/mlkem768/cbd.c"
         "${PQC}/mlkem768/indcpa.c"
         "${PQC}/mlkem768/kem.c"
         "${PQC}/mlkem768/ntt.c"
         "${PQC}/mlkem768/poly.c"
         "${PQC}/mlkem768/polyvec.c"
         "${PQC}/mlkem768/reduce.c"
         "${PQC}/mlkem768/symmetric-shake.c"
         "${PQC}/mlkem768/verify.c"
         "${PQC}/fips202.c"
         "${CMAKE_CURRENT_LIST_DIR}/randombytes_stub.c"
    INCLUDE_DIRS "${PQC}/mlkem768"
                 "${PQC}"
)
target_compile_options(${COMPONENT_LIB} PRIVATE -O2)
