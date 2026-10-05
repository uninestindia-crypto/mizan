cmake_minimum_required(VERSION 3.14)
project(halal_investment_client LANGUAGES CXX)

set(BINARY_NAME "halal_investment_client")

cmake_policy(SET CMP0063 NEW)

set(CMAKE_INSTALL_RPATH "$ORIGIN/lib")

# Configure build options.
get_property(IS_MULTICONFIG GLOBAL PROPERTY GENERATOR_IS_MULTI_CONFIG)
if(IS_MULTICONFIG)
  set(CMAKE_CONFIGURATION_TYPES "Debug;Profile;Release"
    CACHE STRING "" FORCE)
else()
  if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE "Debug" CACHE
      STRING "Choose the type of build, options are: Debug Profile Release."
      FORCE)
  endif()
endif()

# Application build settings.
set(APPLICATION_TITLE "Halal Invest India")
set(APPLICATION_VERSION "1.4.0")

# Target configuration.
add_executable(${BINARY_NAME} WIN32
  "runner/main.cpp"
  "runner/utils.cpp"
  "runner/win32_window.cpp"
  "runner/flutter_window.cpp"
  "runner/Runner.rc"
  "flutter/generated_plugin_registrant.cc"
)

target_compile_definitions(${BINARY_NAME} PRIVATE
  NOMINMAX
  UNICODE
  _UNICODE
  APPLICATION_TITLE="${APPLICATION_TITLE}"
  APPLICATION_VERSION="${APPLICATION_VERSION}"
)

target_link_libraries(${BINARY_NAME} PRIVATE flutter flutter_wrapper_app dwmapi.lib)
