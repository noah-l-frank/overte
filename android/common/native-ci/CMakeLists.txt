# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
# Parent-owned Android native acceptance. Product applications remain separate.
if(NOT ANDROID OR NOT OVERTE_ANDROID_COMMON_NATIVE)
    message(FATAL_ERROR "Common native acceptance requires the Android root entry point")
endif()
if(NOT HIFI_ANDROID_APP STREQUAL "commonNative")
    message(FATAL_ERROR "Common native acceptance must not select a product application")
endif()
if(NOT ANDROID_ABI STREQUAL "arm64-v8a" AND
   NOT CMAKE_ANDROID_ARCH_ABI STREQUAL "arm64-v8a")
    message(FATAL_ERROR "Common native acceptance requires the qualified arm64-v8a graph")
endif()
list(PREPEND CMAKE_MODULE_PATH "${CMAKE_SOURCE_DIR}/android/common/cmake/android-modules")
include("${CMAKE_SOURCE_DIR}/android/common/cmake/overte-android-bootstrap.cmake")
foreach(_dependency draco::draco glad::glad etc2comp::etc2comp nvidia-texture-tools::nvidia-texture-tools)
    if(NOT TARGET ${_dependency})
        message(FATAL_ERROR "Common native acceptance lacks qualified target ${_dependency}")
    endif()
endforeach()
if(USE_BREAKPAD OR HIFI_ANDROID_PRECOMPILED)
    message(FATAL_ERROR "Common native acceptance does not use legacy precompiled inputs")
endif()
# Interface is a real shared library on Android. This brings its production
# library closure, generated entities/shaders and resources into the build.
# Neither product's CMake wrapper nor Java/Gradle/APK shell is configured here.
add_subdirectory("${CMAKE_SOURCE_DIR}/interface" "${CMAKE_BINARY_DIR}/interface")
# Bionic exposes pthread in libc. Preserve the normal production metadata
# while removing a stale desktop-only link name if supplied transitively.
foreach(_link_property LINK_LIBRARIES INTERFACE_LINK_LIBRARIES)
    get_target_property(_gpu_gl_links gpu-gl ${_link_property})
    if(_gpu_gl_links)
        list(REMOVE_ITEM _gpu_gl_links pthread)
        set_property(TARGET gpu-gl PROPERTY ${_link_property} "${_gpu_gl_links}")
    endif()
endforeach()
# The shared renderer implementation is owned by the Android parent. Match
# the production Android path without importing either application's wrapper.
get_target_property(_overte_gl_sources gl SOURCES)
list(FILTER _overte_gl_sources EXCLUDE REGEX "OffscreenGLCanvas[.]cpp$")
set_property(TARGET gl PROPERTY SOURCES "${_overte_gl_sources}")
target_sources(gl PRIVATE "${CMAKE_SOURCE_DIR}/android/common/src/OffscreenGLCanvas.cpp")
target_include_directories(gl PRIVATE "${CMAKE_SOURCE_DIR}/libraries/gl/src/gl")
target_compile_options(audio-client PRIVATE -include jni.h)

# Compile/link the parent-owned JNI providers as a real shared library too.
add_library(overte-android-common-runtime SHARED
    "${CMAKE_SOURCE_DIR}/android/common/src/QtInputConnectionCompat.cpp")
target_link_libraries(overte-android-common-runtime interface Qt5::Core Qt5::Gui Qt5::AndroidExtras)
include("${CMAKE_SOURCE_DIR}/android/common/web/target.cmake")
overte_target_embedded_web(overte-android-common-runtime)
include("${CMAKE_SOURCE_DIR}/android/common/snapshot/target.cmake")
overte_target_snapshot(overte-android-common-runtime)
include("${CMAKE_SOURCE_DIR}/android/common/documents/target.cmake")
overte_target_documents(overte-android-common-runtime)
get_target_property(_overte_interface_type interface TYPE)
if(NOT _overte_interface_type STREQUAL "SHARED_LIBRARY")
    message(FATAL_ERROR "Common native acceptance requires the production Interface shared library")
endif()
function(_overte_common_native_targets directory result)
    get_property(_targets DIRECTORY "${directory}" PROPERTY BUILDSYSTEM_TARGETS)
    get_property(_children DIRECTORY "${directory}" PROPERTY SUBDIRECTORIES)
    foreach(_child IN LISTS _children)
        _overte_common_native_targets("${_child}" _child_targets)
        list(APPEND _targets ${_child_targets})
    endforeach()
    set(${result} "${_targets}" PARENT_SCOPE)
endfunction()
_overte_common_native_targets("${CMAKE_SOURCE_DIR}" _overte_targets)
add_custom_target(overte-android-common-native)
foreach(_target IN LISTS _overte_targets)
    get_target_property(_type "${_target}" TYPE)
    if(_type STREQUAL "SHARED_LIBRARY" OR _type STREQUAL "MODULE_LIBRARY")
        # A successful empty wrapper link is not acceptance of the real DSOs.
        # Apply the strict link contract to each production shared target.
        target_link_options("${_target}" PRIVATE "-Wl,--no-undefined")
        add_dependencies(overte-android-common-native "${_target}")
    endif()
endforeach()
add_dependencies(overte-android-common-native resources)
