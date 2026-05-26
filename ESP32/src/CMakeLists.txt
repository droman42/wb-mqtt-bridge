# IDF component manifest for the project's main sources. Auto-generated initially
# by PIO; replaced with an explicit version so we can: (a) expose include/ as a
# header search path, and (b) declare REQUIRES for the IDF components we use
# (without these, the linker fails with undefined references to esp_wifi_*,
# nvs_*, esp_mqtt_*, etc.).

# NOTE: CONFIGURE_DEPENDS is unsupported here — IDF runs this CMakeLists in
# script mode during component_get_requirements, where the flag is rejected.
# Adding/removing a .cpp under src/ thus requires a CMake reconfigure
# (`pio run -e <env> -t fullclean` then `pio run -e <env>`).
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
        esp_https_ota          # MQTT-triggered OTA pull (ota.cpp)
        esp_http_client        # used by esp_https_ota
        app_update             # esp_ota_* APIs / rollback marking
        driver                 # GPIO + ISR service (driver/gpio.h) for per-device drivers
        esp_rom                # esp_rom_delay_us (bit-bang timing)
)
