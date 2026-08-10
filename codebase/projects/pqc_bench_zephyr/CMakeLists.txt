cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(pqc_bench_zephyr)

target_sources(app PRIVATE
  src/main.c
  # ML-KEM-768
  pqclean/mlkem768/cbd.c
  pqclean/mlkem768/indcpa.c
  pqclean/mlkem768/kem.c
  pqclean/mlkem768/ntt.c
  pqclean/mlkem768/poly.c
  pqclean/mlkem768/polyvec.c
  pqclean/mlkem768/reduce.c
  pqclean/mlkem768/symmetric-shake.c
  pqclean/mlkem768/verify.c
  # ML-DSA-44/65/87
  pqclean/mldsa44/ntt.c
  pqclean/mldsa44/packing.c
  pqclean/mldsa44/poly.c
  pqclean/mldsa44/polyvec.c
  pqclean/mldsa44/reduce.c
  pqclean/mldsa44/rounding.c
  pqclean/mldsa44/sign.c
  pqclean/mldsa44/symmetric-shake.c
  pqclean/mldsa65/ntt.c
  pqclean/mldsa65/packing.c
  pqclean/mldsa65/poly.c
  pqclean/mldsa65/polyvec.c
  pqclean/mldsa65/reduce.c
  pqclean/mldsa65/rounding.c
  pqclean/mldsa65/sign.c
  pqclean/mldsa65/symmetric-shake.c
  pqclean/mldsa87/ntt.c
  pqclean/mldsa87/packing.c
  pqclean/mldsa87/poly.c
  pqclean/mldsa87/polyvec.c
  pqclean/mldsa87/reduce.c
  pqclean/mldsa87/rounding.c
  pqclean/mldsa87/sign.c
  pqclean/mldsa87/symmetric-shake.c
  # shared fips202 + randombytes (single copy)
  pqclean/fips202.c
  pqclean/randombytes.c
)

target_include_directories(app PRIVATE
  pqclean
  pqclean/mlkem768
  pqclean/mldsa44
  pqclean/mldsa65
  pqclean/mldsa87
)
