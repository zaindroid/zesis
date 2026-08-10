# TFLite Micro component for ESP32-S3.
#
# Sources come from the NXP SDK's eIQ tensorflow-lite tree (the exact tree the
# FRDM-MCXN947 firmware builds against), copied into this component. This is
# the same TFLite Micro the certification pipeline targeted, so the INT8
# arithmetic -- and therefore the certified tau thresholds -- carry over.
#
# Sources are globbed (not hand-listed) so the set always matches the tree;
# unused kernels are dropped at link time by --gc-sections.

# Core micro framework + arena allocators + memory planner.
file(GLOB TFLM_CORE_SRCS
    tensorflow/lite/micro/*.cpp
    tensorflow/lite/micro/arena_allocator/*.cpp
    tensorflow/lite/micro/memory_planner/*.cpp
    tensorflow/lite/micro/tflite_bridge/*.cpp
)

# All standard kernels (top-level kernels dir; excludes platform subdirs).
file(GLOB TFLM_KERNEL_SRCS tensorflow/lite/micro/kernels/*.cpp)
list(FILTER TFLM_KERNEL_SRCS EXCLUDE REGEX ".*_test(_common)?.cpp$")

# TensorFlow Lite core utilities.
file(GLOB TFLM_LITE_SRCS
    tensorflow/lite/core/api/*.cpp
    tensorflow/lite/core/c/*.cpp
    tensorflow/lite/kernels/internal/*.cpp
    tensorflow/lite/kernels/internal/reference/*.cpp
    tensorflow/lite/kernels/*.cpp
    tensorflow/compiler/mlir/lite/schema/*.cpp
    tensorflow/compiler/mlir/lite/core/api/*.cpp
)

# Third-party: kissfft is needed by some ops; flatbuffers/gemmlowp/ruy are
# header-only.
file(GLOB TFLM_THIRD_PARTY_SRCS
    third_party/kissfft/*.c
    third_party/kissfft/tools/*.c
)

idf_component_register(
    SRCS ${TFLM_CORE_SRCS} ${TFLM_KERNEL_SRCS} ${TFLM_LITE_SRCS} ${TFLM_THIRD_PARTY_SRCS}
    INCLUDE_DIRS "."
                 "third_party/flatbuffers/include"
                 "third_party/gemmlowp"
                 "third_party/kissfft"
                 "third_party/ruy"
                 "third_party/cmsis_nn"
                 "third_party/cmsis_nn/Include"
)

target_compile_definitions(${COMPONENT_LIB} PUBLIC
    TF_LITE_STATIC_MEMORY
    KERNELS_OPTIMIZED_FOR_SPEED
)
