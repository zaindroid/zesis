#!/usr/bin/env bash
# Build the minimal UART test (no HAL) for STM32N6570-DK
set -e
cd "$(dirname "$0")"
cd ..

TOOLCHAIN="/c/Users/zain_/.mcuxpressotools/arm-gnu-toolchain-14.2.rel1-mingw-w64-x86_64-arm-none-eabi/bin"
CC="$TOOLCHAIN/arm-none-eabi-gcc"
OBJCOPY="$TOOLCHAIN/arm-none-eabi-objcopy"
SIZE="$TOOLCHAIN/arm-none-eabi-size"

MCU="-mcpu=cortex-m55 -mthumb -mfloat-abi=hard -mcmse"
OPT="-O2"
CFLAGS="$MCU $OPT -Wall -fdata-sections -ffunction-sections"
LDFLAGS="$MCU -specs=nano.specs -T STM32N657X0HXQ_AXISRAM2_fsbl.ld -Wl,--gc-sections -Wl,-Map=build/minitest.map -lc -lm -lnosys"

mkdir -p build
echo "CC minitest/main.c"
"$CC" -c $CFLAGS minitest/main.c -o build/minitest_main.o
echo "AS startup"
"$CC" -c $MCU $OPT -x assembler-with-cpp Src/startup_stm32n657xx_fsbl.s -o build/minitest_startup.o
echo "LD"
"$CC" build/minitest_main.o build/minitest_startup.o $LDFLAGS -o build/minitest.elf
"$SIZE" build/minitest.elf
"$OBJCOPY" -O binary -S build/minitest.elf build/minitest.bin
echo "=== minitest.bin ready ==="
