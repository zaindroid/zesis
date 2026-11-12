idf_component_register(
    SRCS "main.cpp"
    INCLUDE_DIRS "."
    REQUIRES wolfcrypt pqclean_mlkem esp_timer
)
target_compile_options(${COMPONENT_LIB} PRIVATE -O2)
