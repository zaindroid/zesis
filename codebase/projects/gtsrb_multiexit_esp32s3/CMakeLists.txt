# ESP-IDF project for the GTSRB multi-exit certified-anytime benchmark on
# ESP32-S3. Reuses the exact INT8 TFLite segment models from the frozen
# four-way certification (tau thresholds transfer because TFLite Micro
# preserves the INT8 arithmetic).
cmake_minimum_required(VERSION 3.16)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(gtsrb_multiexit_esp32s3)
