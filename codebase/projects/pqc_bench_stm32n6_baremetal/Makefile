##########################################################################################################################
# Bare-metal PQC benchmark — STM32N6570-DK (Cortex-M55)
# ML-KEM-768 + ML-DSA-44/65/87, RAMLOAD image loaded via USB DFU
##########################################################################################################################

TARGET = pqc_bench_stm32n6

# debug build?
DEBUG = 0
# optimization
OPT = -O2

BUILD_DIR = build

######################################
# toolchain
######################################
PREFIX = arm-none-eabi-
CC = $(PREFIX)gcc
AS = $(PREFIX)gcc -x assembler-with-cpp
CP = $(PREFIX)objcopy
SZ = $(PREFIX)size
HEX = $(CP) -O ihex
BIN = $(CP) -O binary -S

######################################
# paths
######################################
STM_HAL = C:/Users/zain_/STM32Cube/Repository/STM32Cube_FW_N6_V1.3.0/Drivers/STM32N6xx_HAL_Driver
STM_CMSIS = C:/Users/zain_/STM32Cube/Repository/STM32Cube_FW_N6_V1.3.0/Drivers/CMSIS/Device/ST/STM32N6xx/Include
STM_CMSIS_CORE = C:/Users/zain_/STM32Cube/Repository/STM32Cube_FW_N6_V1.3.0/Drivers/CMSIS/Include

# C sources
C_SOURCES = \
Src/main.c \
Src/system_stm32n6xx_fsbl.c \
Src/sysmem.c \
Src/syscalls.c \
$(STM_HAL)/Src/stm32n6xx_hal.c \
$(STM_HAL)/Src/stm32n6xx_hal_cortex.c \
$(STM_HAL)/Src/stm32n6xx_hal_gpio.c \
$(STM_HAL)/Src/stm32n6xx_hal_rcc.c \
$(STM_HAL)/Src/stm32n6xx_hal_rcc_ex.c \
$(STM_HAL)/Src/stm32n6xx_hal_pwr.c \
$(STM_HAL)/Src/stm32n6xx_hal_pwr_ex.c \
$(STM_HAL)/Src/stm32n6xx_hal_uart.c \
$(STM_HAL)/Src/stm32n6xx_hal_uart_ex.c \
$(STM_HAL)/Src/stm32n6xx_hal_exti.c \
$(STM_HAL)/Src/stm32n6xx_hal_dma.c \
$(STM_HAL)/Src/stm32n6xx_hal_dma_ex.c \
pqclean/fips202.c \
pqclean/randombytes.c \
pqclean/mlkem768/cbd.c \
pqclean/mlkem768/indcpa.c \
pqclean/mlkem768/kem.c \
pqclean/mlkem768/ntt.c \
pqclean/mlkem768/poly.c \
pqclean/mlkem768/polyvec.c \
pqclean/mlkem768/reduce.c \
pqclean/mlkem768/symmetric-shake.c \
pqclean/mlkem768/verify.c \
pqclean/mldsa44/ntt.c \
pqclean/mldsa44/packing.c \
pqclean/mldsa44/poly.c \
pqclean/mldsa44/polyvec.c \
pqclean/mldsa44/reduce.c \
pqclean/mldsa44/rounding.c \
pqclean/mldsa44/sign.c \
pqclean/mldsa44/symmetric-shake.c \
pqclean/mldsa65/ntt.c \
pqclean/mldsa65/packing.c \
pqclean/mldsa65/poly.c \
pqclean/mldsa65/polyvec.c \
pqclean/mldsa65/reduce.c \
pqclean/mldsa65/rounding.c \
pqclean/mldsa65/sign.c \
pqclean/mldsa65/symmetric-shake.c \
pqclean/mldsa87/ntt.c \
pqclean/mldsa87/packing.c \
pqclean/mldsa87/poly.c \
pqclean/mldsa87/polyvec.c \
pqclean/mldsa87/reduce.c \
pqclean/mldsa87/rounding.c \
pqclean/mldsa87/sign.c \
pqclean/mldsa87/symmetric-shake.c

# ASM sources
ASM_SOURCES = \
Src/startup_stm32n657xx_fsbl.s

# Includes
C_INCLUDES = \
-I Inc \
-I Src \
-I pqclean \
-I pqclean/mlkem768 \
-I pqclean/mldsa44 \
-I pqclean/mldsa65 \
-I pqclean/mldsa87 \
-I$(STM_HAL)/Inc \
-I$(STM_HAL)/Inc/Legacy \
-I$(STM_CMSIS) \
-I$(STM_CMSIS_CORE)

# Defines
C_DEFS = \
-DUSE_HAL_DRIVER \
-DSTM32N657xx

# Linker
LDSCRIPT = STM32N657X0HXQ_AXISRAM2_fsbl.ld
LIBS = -lc -lm -lnosys
LIBDIR =
LDFLAGS = $(MCU) -specs=nano.specs -T$(LDSCRIPT) $(LIBDIR) $(LIBS) -Wl,-Map=$(BUILD_DIR)/$(TARGET).map,--cref -Wl,--gc-sections

# MCU
MCU = -mcpu=cortex-m55 -mthumb -mfloat-abi=soft

# Compile flags
CFLAGS = $(MCU) $(C_DEFS) $(C_INCLUDES) $(OPT) -Wall -fdata-sections -ffunction-sections
ifeq ($(DEBUG), 1)
CFLAGS += -g -gdwarf-2
endif
ASFLAGS = $(MCU) $(OPT) -Wall -fdata-sections -ffunction-sections

OBJECTS = $(addprefix $(BUILD_DIR)/,$(notdir $(C_SOURCES:.c=.o)))
vpath %.c $(sort $(dir $(C_SOURCES)))
OBJECTS += $(addprefix $(BUILD_DIR)/,$(notdir $(ASM_SOURCES:.s=.o)))
vpath %.s $(sort $(dir $(ASM_SOURCES)))

all: $(BUILD_DIR)/$(TARGET).elf $(BUILD_DIR)/$(TARGET).hex $(BUILD_DIR)/$(TARGET).bin

$(BUILD_DIR)/%.o: %.c Makefile | $(BUILD_DIR)
	$(CC) -c $(CFLAGS) -Wa,-a,-ad,-alms=$(BUILD_DIR)/$(notdir $(<:.c=.lst)) $< -o $@

$(BUILD_DIR)/%.o: %.s Makefile | $(BUILD_DIR)
	$(AS) -c $(ASFLAGS) $< -o $@

$(BUILD_DIR)/$(TARGET).elf: $(OBJECTS) Makefile
	$(CC) $(OBJECTS) $(LDFLAGS) -o $@
	$(SZ) $@

$(BUILD_DIR)/%.hex: $(BUILD_DIR)/%.elf | $(BUILD_DIR)
	$(HEX) $< $@

$(BUILD_DIR)/%.bin: $(BUILD_DIR)/%.elf | $(BUILD_DIR)
	$(BIN) $< $@

$(BUILD_DIR):
	mkdir $@

clean:
	-rm -fR $(BUILD_DIR)

.PHONY: clean all
