# IDF component manifest for the project's main sources. Auto-generated initially
# by PIO; replaced with an explicit version so we can: (a) expose include/ as a
# header search path, and (b) declare REQUIRES for the IDF components we use
# (without these, the linker fails with undefined references to esp_wifi_*,
# nvs_*, esp_mqtt_*, etc.).

FILE(GLOB_RECURSE app_sources ${CMAKE_SOURCE_DIR}/src/*.cpp)

idf_component_register(
    SRCS ${app_sources}
    INCLUDE_DIRS "${CMAKE_SOURCE_DIR}/include"
    REQUIRES
        esp_wifi
        esp_event
        esp_netif
        nvs_flash
        mqtt
        esp_timer
        log
)
