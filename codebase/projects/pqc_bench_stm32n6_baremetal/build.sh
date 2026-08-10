#!/usr/bin/env bash
# Bare-metal PQC benchmark build for STM32N6570-DK
# Uses arm-none-eabi-gcc directly (no make needed)
set -e
cd "$(dirname "$0")"

TOOLCHAIN="/c/Users/zain_/.mcuxpressotools/arm-gnu-toolchain-14.2.rel1-mingw-w64-x86_64-arm-none-eabi/bin"
CC="$TOOLCHAIN/arm-none-eabi-gcc"
OBJCOPY="$TOOLCHAIN/arm-none-eabi-objcopy"
SIZE="$TOOLCHAIN/arm-none-eabi-size"

STM="/c/Users/zain_/STM32Cube/Repository/STM32Cube_FW_N6_V1.3.0"
HAL="$STM/Drivers/STM32N6xx_HAL_Driver"
CMSIS_D="$STM/Drivers/CMSIS/Device/ST/STM32N6xx/Include"
CMSIS_C="$STM/Drivers/CMSIS/Include"

MCU="-mcpu=cortex-m55 -mthumb -mfloat-abi=hard -mcmse"
OPT="-O2"
DEFS="-DUSE_HAL_DRIVER -DSTM32N657xx"
INCS="-IInc -ISrc -Ipqclean -Ipqclean/mlkem768 -Ipqclean/mldsa44 -Ipqclean/mldsa65 -Ipqclean/mldsa87 -I$HAL/Inc -I$HAL/Inc/Legacy -I$CMSIS_D -I$CMSIS_C"
CFLAGS="$MCU $DEFS $INCS $OPT -Wall -fdata-sections -ffunction-sections"
LDFLAGS="$MCU -specs=nano.specs -T STM32N657X0HXQ_AXISRAM2_fsbl.ld -Wl,--gc-sections -Wl,-Map=build/pqc.map -lc -lm -lnosys"

mkdir -p build

# C sources
C_SRCS=(
  Src/main.c
  Src/system_stm32n6xx_fsbl.c
  Src/sysmem.c
  Src/syscalls.c
  "$HAL/Src/stm32n6xx_hal.c"
  "$HAL/Src/stm32n6xx_hal_cortex.c"
  "$HAL/Src/stm32n6xx_hal_gpio.c"
  "$HAL/Src/stm32n6xx_hal_rcc.c"
  "$HAL/Src/stm32n6xx_hal_rcc_ex.c"
  "$HAL/Src/stm32n6xx_hal_pwr.c"
  "$HAL/Src/stm32n6xx_hal_pwr_ex.c"
  "$HAL/Src/stm32n6xx_hal_uart.c"
  "$HAL/Src/stm32n6xx_hal_uart_ex.c"
  "$HAL/Src/stm32n6xx_hal_exti.c"
  "$HAL/Src/stm32n6xx_hal_dma.c"
  "$HAL/Src/stm32n6xx_hal_dma_ex.c"
  pqclean/fips202.c
  pqclean/randombytes.c
  pqclean/mlkem768/cbd.c pqclean/mlkem768/indcpa.c pqclean/mlkem768/kem.c
  pqclean/mlkem768/ntt.c pqclean/mlkem768/poly.c pqclean/mlkem768/polyvec.c
  pqclean/mlkem768/reduce.c pqclean/mlkem768/symmetric-shake.c pqclean/mlkem768/verify.c
  pqclean/mldsa44/ntt.c pqclean/mldsa44/packing.c pqclean/mldsa44/poly.c
  pqclean/mldsa44/polyvec.c pqclean/mldsa44/reduce.c pqclean/mldsa44/rounding.c
  pqclean/mldsa44/sign.c pqclean/mldsa44/symmetric-shake.c
  pqclean/mldsa65/ntt.c pqclean/mldsa65/packing.c pqclean/mldsa65/poly.c
  pqclean/mldsa65/polyvec.c pqclean/mldsa65/reduce.c pqclean/mldsa65/rounding.c
  pqclean/mldsa65/sign.c pqclean/mldsa65/symmetric-shake.c
  pqclean/mldsa87/ntt.c pqclean/mldsa87/packing.c pqclean/mldsa87/poly.c
  pqclean/mldsa87/polyvec.c pqclean/mldsa87/reduce.c pqclean/mldsa87/rounding.c
  pqclean/mldsa87/sign.c pqclean/mldsa87/symmetric-shake.c
)

OBJS=()
for src in "${C_SRCS[@]}"; do
  # unique object name: hash the source path
  name=$(echo "$src" | md5sum | cut -c1-8)
  obj="build/$name.o"
  echo "CC $src"
  "$CC" -c $CFLAGS "$src" -o "$obj"
  OBJS+=("$obj")
done

echo "AS Src/startup_stm32n657xx_fsbl.s"
"$CC" -c $MCU $OPT -x assembler-with-cpp Src/startup_stm32n657xx_fsbl.s -o build/startup.o
OBJS+=("build/startup.o")

echo "LD build/pqc_bench_stm32n6.elf"
"$CC" "${OBJS[@]}" $LDFLAGS -o build/pqc_bench_stm32n6.elf
"$SIZE" build/pqc_bench_stm32n6.elf
"$OBJCOPY" -O binary -S build/pqc_bench_stm32n6.elf build/pqc_bench_stm32n6.bin
echo "=== built: build/pqc_bench_stm32n6.bin ==="
