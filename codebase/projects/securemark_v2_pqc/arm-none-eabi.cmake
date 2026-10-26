set(CMAKE_SYSTEM_NAME Generic)
set(CMAKE_SYSTEM_PROCESSOR arm)

set(ARMGCC "C:/Users/zain_/.mcuxpressotools/arm-gnu-toolchain-14.2.rel1-mingw-w64-x86_64-arm-none-eabi/bin")
set(CMAKE_C_COMPILER "${ARMGCC}/arm-none-eabi-gcc.exe")
set(CMAKE_AR "${ARMGCC}/arm-none-eabi-ar.exe")
set(CMAKE_RANLIB "${ARMGCC}/arm-none-eabi-ranlib.exe")

set(MCXN947_FLAGS "-mcpu=cortex-m33 -mthumb -mfloat-abi=hard -mfpu=fpv5-sp-d16 -O2 -ffunction-sections -fdata-sections")
set(CMAKE_C_FLAGS_INIT "${MCXN947_FLAGS}")
set(CMAKE_EXE_LINKER_FLAGS_INIT "-Wl,--defsym=__stack_size__=0x20000")

set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)
