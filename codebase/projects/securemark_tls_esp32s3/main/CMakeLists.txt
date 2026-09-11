# SecureMark-TLS (EEMBC) self-hosted benchmark for ESP32-S3

idf_component_register(
    SRCS "main.cpp"
         "sm_main.c"
         "th_aes.c"
         "th_sha.c"
         "th_ecdh.c"
         "th_ecdsa.c"
         "th_util.c"
         "../profile/ee_aes.c"
         "../profile/ee_ecdh.c"
         "../profile/ee_ecdsa.c"
         "../profile/ee_profile.c"
         "../profile/ee_sha.c"
         "../profile/ee_variations.c"
    INCLUDE_DIRS "."
                 "../profile"
                 "../profile/th_api"
    REQUIRES mbedtls esp_timer
)

target_compile_definitions(${COMPONENT_LIB} PRIVATE
    EE_CFG_SELFHOSTED=1
    EE_CFG_BAREMETAL=1
    EE_CFG_QUIET=0
)
