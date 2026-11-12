# wolfSSL wolfcrypt, ML-KEM subset only. Sources are referenced from the
# wolfSSL checkout rather than copied, so the tree stays small.
set(WOLFSSL_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../../../wolfssl")

idf_component_register(
    SRCS "${WOLFSSL_ROOT}/wolfcrypt/src/wc_mlkem.c"
         "${WOLFSSL_ROOT}/wolfcrypt/src/wc_mlkem_poly.c"
         "${WOLFSSL_ROOT}/wolfcrypt/src/sha3.c"
         "${WOLFSSL_ROOT}/wolfcrypt/src/random.c"
         "${WOLFSSL_ROOT}/wolfcrypt/src/wc_port.c"
         "${WOLFSSL_ROOT}/wolfcrypt/src/memory.c"
         "${WOLFSSL_ROOT}/wolfcrypt/src/error.c"
    INCLUDE_DIRS "${WOLFSSL_ROOT}"
                 "${WOLFSSL_ROOT}/wolfssl"
                 "${CMAKE_CURRENT_LIST_DIR}"
)

target_compile_definitions(${COMPONENT_LIB} PUBLIC
    WOLFSSL_USER_SETTINGS
    WOLFSSL_IGNORE_FILE_WARN
)
target_compile_options(${COMPONENT_LIB} PRIVATE -O2 -Wno-unused-variable -Wno-sign-compare)
