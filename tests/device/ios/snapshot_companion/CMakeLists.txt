# Standalone opt-in source target; never included by the product build.
cmake_minimum_required(VERSION 3.24)
if(NOT CMAKE_SYSTEM_NAME STREQUAL "iOS" OR NOT OVERTE_E2E_FEATURE_TESTS)
    message(FATAL_ERROR "The Snapshot companion requires an explicit iOS E2E test configuration")
endif()
if(NOT OVT_SNAPSHOT_COMPANION_BUNDLE_ID MATCHES "^[A-Za-z0-9-]+(\\.[A-Za-z0-9-]+)+$")
    message(FATAL_ERROR "Select the separate test companion bundle identifier")
endif()
project(overte-snapshot-companion LANGUAGES C OBJC)
add_executable(overte-snapshot-companion MACOSX_BUNDLE main.m PhotosOriginal.m)
target_compile_definitions(overte-snapshot-companion PRIVATE OVERTE_E2E_FEATURE_TESTS=1)
target_compile_options(overte-snapshot-companion PRIVATE -fobjc-arc)
target_link_libraries(overte-snapshot-companion PRIVATE "-framework UIKit" "-framework Photos")
set_target_properties(overte-snapshot-companion PROPERTIES
    MACOSX_BUNDLE_INFO_PLIST "${CMAKE_CURRENT_SOURCE_DIR}/Info.plist.in"
    XCODE_ATTRIBUTE_PRODUCT_BUNDLE_IDENTIFIER "${OVT_SNAPSHOT_COMPANION_BUNDLE_ID}"
    XCODE_ATTRIBUTE_TARGETED_DEVICE_FAMILY "1,2")
