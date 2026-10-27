# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
# Reviewed metadata-only interpreter. No project/configure/target/compiler runs.
cmake_minimum_required(VERSION 3.17)
if (NOT CMAKE_SCRIPT_MODE_FILE)
    message(FATAL_ERROR "This metadata check requires cmake -P script mode")
endif()
if (NOT DEFINED OVERTE_METADATA_IMAGE_CMAKE OR NOT EXISTS "${OVERTE_METADATA_IMAGE_CMAKE}")
    message(FATAL_ERROR "The exact reviewed image CMake input is required")
endif()

# Fail before any external command, package, language, target, generated file,
# install, nested project or dynamic CMake evaluation could be reached.
foreach(_overte_forbidden IN ITEMS
        execute_process project enable_language find_package try_compile try_run
        add_library add_executable add_subdirectory add_custom_command add_custom_target
        configure_file install export include_external_msproject cmake_language file
        build_command aux_source_directory load_cache
        target_link_libraries target_compile_options target_include_directories
        add_compile_definitions add_definitions remove_definitions link_directories
        ExternalProject_Add FetchContent_Declare FetchContent_Populate FetchContent_MakeAvailable)
    function(${_overte_forbidden})
        message(FATAL_ERROR "Forbidden command in metadata-only check: ${CMAKE_CURRENT_FUNCTION}")
    endfunction()
endforeach()

# Current image target helpers become inert functions. They neither create an
# image target nor execute their ordinary package/compiler helper bodies.
foreach(_overte_helper IN ITEMS link_hifi_libraries
        target_nvtt target_tbb target_etc2comp target_openexr)
    function(${_overte_helper})
    endfunction()
endforeach()

function(setup_hifi_library)
    if (NOT "${TARGET_NAME}" STREQUAL "image")
        message(FATAL_ERROR "Image setup was called before its target name")
    endif()
    set_property(GLOBAL PROPERTY OVERTE_METADATA_IMAGE_READY 1)
endfunction()

function(target_compile_definitions)
    get_property(_overte_ready GLOBAL PROPERTY OVERTE_METADATA_IMAGE_READY)
    if (NOT _overte_ready EQUAL 1)
        message(FATAL_ERROR "Image definition was requested before image setup")
    endif()
    if (NOT ARGC EQUAL 3)
        message(FATAL_ERROR "Unexpected image definition argument count")
    endif()
    if (NOT "${ARGV0}" STREQUAL "image" OR NOT "${ARGV1}" STREQUAL "PRIVATE"
            OR NOT "${ARGV2}" STREQUAL "OVERTE_IOS_E2E_TEST_BUILD=1")
        message(FATAL_ERROR "Unexpected target, visibility or diagnostic definition")
    endif()
    get_property(_overte_count GLOBAL PROPERTY OVERTE_METADATA_DEFINITION_CALLS)
    math(EXPR _overte_count "${_overte_count} + 1")
    set_property(GLOBAL PROPERTY OVERTE_METADATA_DEFINITION_CALLS "${_overte_count}")
endfunction()

# The Apple branch makes the existing Threads package block unreachable; any
# accidental package or compiler path still meets the fatal functions above.
set(APPLE TRUE)
set(UNIX TRUE)
set(WIN32 FALSE)
set(_overte_cases 0)
foreach(_overte_ios OFF ON)
    foreach(_overte_feature OFF ON)
        foreach(_overte_testbuild OFF ON)
            set(IOS "${_overte_ios}")
            set(OVERTE_E2E_FEATURE_TESTS "${_overte_feature}")
            set(OVERTE_IOS_E2E_TEST_BUILD "${_overte_testbuild}")
            set(TARGET_NAME "metadata-target-was-not-initialized")
            set_property(GLOBAL PROPERTY OVERTE_METADATA_DEFINITION_CALLS 0)
            set_property(GLOBAL PROPERTY OVERTE_METADATA_IMAGE_READY 0)
            # The Python entrypoint admits only this reviewed flat file's
            # command set. No project CMake helper implementation is included.
            include("${OVERTE_METADATA_IMAGE_CMAKE}")
            get_property(_overte_count GLOBAL PROPERTY OVERTE_METADATA_DEFINITION_CALLS)
            set(_overte_expected 0)
            if (_overte_ios AND _overte_feature AND _overte_testbuild)
                set(_overte_expected 1)
            endif()
            if (NOT _overte_count EQUAL _overte_expected)
                message(FATAL_ERROR "Wrong definition count for ${_overte_ios}/${_overte_feature}/${_overte_testbuild}")
            endif()
            if (NOT "${TARGET_NAME}" STREQUAL "image")
                message(FATAL_ERROR "The actual image target declaration was not evaluated")
            endif()
            math(EXPR _overte_cases "${_overte_cases} + 1")
            message(STATUS "OVERTE_IMAGE_METADATA_CASE=${_overte_ios},${_overte_feature},${_overte_testbuild},${_overte_count}")
        endforeach()
    endforeach()
endforeach()
if (NOT _overte_cases EQUAL 8)
    message(FATAL_ERROR "The metadata option matrix is incomplete")
endif()
message(STATUS "OVERTE_IMAGE_METADATA_CASES=8;NO_CONFIGURE_OR_COMPILER")
