# Standalone opt-in source; never included by the Overte product build.
cmake_minimum_required(VERSION 3.24)
if(NOT CMAKE_SYSTEM_NAME STREQUAL "iOS" OR NOT OVERTE_E2E_FEATURE_TESTS OR NOT CMAKE_GENERATOR STREQUAL "Xcode")
    message(FATAL_ERROR "The Snapshot Share receiver requires explicit iOS E2E configuration")
endif()
if(NOT OVT_SNAPSHOT_SHARE_BUNDLE_ID MATCHES "^[A-Za-z0-9-]+(\\.[A-Za-z0-9-]+)+$"
        OR NOT OVT_SNAPSHOT_SHARE_GROUP MATCHES "^group\\.[A-Za-z0-9.-]+$")
    message(FATAL_ERROR "Select a separate companion bundle identifier and provisioned App Group")
endif()
project(overte-snapshot-share LANGUAGES C OBJC)
configure_file(Shared.entitlements.in Shared.entitlements @ONLY)
configure_file(ExtensionInfo.plist.in ExtensionInfo.plist @ONLY)
add_executable(overte-snapshot-share MACOSX_BUNDLE ArchiveApp.m ShareJournal.m)
add_library(overte-snapshot-share-extension MODULE ShareReceiver.m ShareJournal.m)
foreach(target overte-snapshot-share overte-snapshot-share-extension)
    target_compile_definitions(${target} PRIVATE OVERTE_E2E_FEATURE_TESTS=1)
    target_compile_options(${target} PRIVATE -fobjc-arc)
    target_link_libraries(${target} PRIVATE "-framework UIKit" "-framework UniformTypeIdentifiers")
    set_target_properties(${target} PROPERTIES
        XCODE_ATTRIBUTE_CODE_SIGN_ENTITLEMENTS "${CMAKE_CURRENT_BINARY_DIR}/Shared.entitlements"
        XCODE_ATTRIBUTE_TARGETED_DEVICE_FAMILY "1,2")
endforeach()
set_target_properties(overte-snapshot-share PROPERTIES
    MACOSX_BUNDLE_INFO_PLIST "${CMAKE_CURRENT_SOURCE_DIR}/AppInfo.plist.in"
    XCODE_ATTRIBUTE_PRODUCT_BUNDLE_IDENTIFIER "${OVT_SNAPSHOT_SHARE_BUNDLE_ID}"
    XCODE_EMBED_APP_EXTENSIONS overte-snapshot-share-extension
    XCODE_EMBED_APP_EXTENSIONS_CODE_SIGN_ON_COPY YES)
set_target_properties(overte-snapshot-share-extension PROPERTIES
    BUNDLE YES BUNDLE_EXTENSION appex PREFIX ""
    XCODE_PRODUCT_TYPE "com.apple.product-type.app-extension"
    XCODE_EXPLICIT_FILE_TYPE "wrapper.app-extension"
    XCODE_ATTRIBUTE_INFOPLIST_FILE "${CMAKE_CURRENT_BINARY_DIR}/ExtensionInfo.plist"
    XCODE_ATTRIBUTE_PRODUCT_BUNDLE_IDENTIFIER "${OVT_SNAPSHOT_SHARE_BUNDLE_ID}.receiver"
    XCODE_ATTRIBUTE_APPLICATION_EXTENSION_API_ONLY YES
    XCODE_ATTRIBUTE_SKIP_INSTALL YES)
add_dependencies(overte-snapshot-share overte-snapshot-share-extension)
