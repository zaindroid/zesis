# Policy variant: 0=NAIVE, 1=STATIC, 2=ADAPTIVE. Select with:
#   idf.py build -DPOLICY_VARIANT=2
set(POLICY_VARIANT "0" CACHE STRING "Policy: 0=NAIVE 1=STATIC 2=ADAPTIVE")
set_property(CACHE POLICY_VARIANT PROPERTY STRINGS 0 1 2)

# ML-DSA benchmark: set MLDSA_BENCH=1 to build ONLY the ML-DSA signing-latency
# benchmark (mldsa_bench.cpp + the selected ML-DSA-level sources in main).
set(MLDSA_BENCH "0" CACHE STRING "Build ML-DSA benchmark instead of policy app")
set_property(CACHE MLDSA_BENCH PROPERTY STRINGS 0 1)

set(MLDSA_LEVEL "44" CACHE STRING "ML-DSA level for benchmark: 44/65/87")
set_property(CACHE MLDSA_LEVEL PROPERTY STRINGS 44 65 87)

if(MLDSA_BENCH STREQUAL "1")
  set(PQC_DIR "${CMAKE_CURRENT_LIST_DIR}/../components/pqc_ml_dsa")
  set(MLDSA_DIR "${PQC_DIR}/ml-dsa-${MLDSA_LEVEL}")
  set(MAIN_SRCS
      "mldsa_bench.cpp"
      "${MLDSA_DIR}/ntt.c"
      "${MLDSA_DIR}/packing.c"
      "${MLDSA_DIR}/poly.c"
      "${MLDSA_DIR}/polyvec.c"
      "${MLDSA_DIR}/reduce.c"
      "${MLDSA_DIR}/rounding.c"
      "${MLDSA_DIR}/sign.c"
      "${MLDSA_DIR}/symmetric-shake.c"
      "${PQC_DIR}/fips202.c"
      "${PQC_DIR}/randombytes.c")
  set(MAIN_REQUIRES "esp_timer")
  set(MAIN_INCDIRS "." "${PQC_DIR}" "${MLDSA_DIR}")
else()
  set(MAIN_SRCS "main.cpp" "segments.cpp")
  set(MAIN_REQUIRES "tflite-micro" "pqclean" "esp_timer")
  set(MAIN_INCDIRS "." "models")
endif()

idf_component_register(
    SRCS ${MAIN_SRCS}
    INCLUDE_DIRS ${MAIN_INCDIRS}
    REQUIRES ${MAIN_REQUIRES}
)

if(MLDSA_BENCH STREQUAL "1")
  target_compile_definitions(${COMPONENT_LIB} PRIVATE MLDSA_BENCH_MAIN MLDSA_LEVEL=${MLDSA_LEVEL})
else()
  if(POLICY_VARIANT STREQUAL "1")
    target_compile_definitions(${COMPONENT_LIB} PRIVATE POLICY=POLICY_STATIC)
  elseif(POLICY_VARIANT STREQUAL "2")
    target_compile_definitions(${COMPONENT_LIB} PRIVATE POLICY=POLICY_ADAPTIVE)
  endif()
endif()
