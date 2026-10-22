# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
# Configure-time source metadata for dedicated E2E binaries only. Unknown or
# dirty sources never acquire a revision by copying another product's binding.
function(overte_e2e_source_identity source_root)
    set(OVERTE_E2E_CONFIGURED_SOURCE_REVISION "" PARENT_SCOPE)
    set(OVERTE_E2E_SOURCE_DEPENDENCIES "" PARENT_SCOPE)
    find_program(_overte_e2e_git NAMES git)
    if(NOT _overte_e2e_git)
        return()
    endif()
    execute_process(COMMAND "${_overte_e2e_git}" -C "${source_root}" rev-parse --show-toplevel
        RESULT_VARIABLE _overte_e2e_root_status OUTPUT_VARIABLE _overte_e2e_root ERROR_QUIET OUTPUT_STRIP_TRAILING_WHITESPACE TIMEOUT 5)
    get_filename_component(_overte_e2e_requested_root "${source_root}" REALPATH)
    get_filename_component(_overte_e2e_actual_root "${_overte_e2e_root}" REALPATH)
    if(NOT _overte_e2e_root_status EQUAL 0 OR NOT _overte_e2e_requested_root STREQUAL _overte_e2e_actual_root)
        return()
    endif()
    execute_process(COMMAND "${CMAKE_COMMAND}" -E env GIT_OPTIONAL_LOCKS=0
        "${_overte_e2e_git}" -C "${source_root}" rev-parse --verify HEAD
        RESULT_VARIABLE _overte_e2e_head_status OUTPUT_VARIABLE _overte_e2e_head
        ERROR_QUIET OUTPUT_STRIP_TRAILING_WHITESPACE TIMEOUT 5)
    execute_process(COMMAND "${CMAKE_COMMAND}" -E env GIT_OPTIONAL_LOCKS=0
        "${_overte_e2e_git}" -C "${source_root}" status --porcelain=v1 --untracked-files=all --ignore-submodules=none
        RESULT_VARIABLE _overte_e2e_status_status OUTPUT_VARIABLE _overte_e2e_status ERROR_QUIET TIMEOUT 5)
    execute_process(COMMAND "${CMAKE_COMMAND}" -E env GIT_OPTIONAL_LOCKS=0
        "${_overte_e2e_git}" -C "${source_root}" ls-files
        RESULT_VARIABLE _overte_e2e_files_status OUTPUT_VARIABLE _overte_e2e_files ERROR_QUIET TIMEOUT 5)
    # CMake regex does not implement {40}; check length independently.
    string(LENGTH "${_overte_e2e_head}" _overte_e2e_head_length)
    if(NOT _overte_e2e_head_status EQUAL 0 OR NOT _overte_e2e_status_status EQUAL 0
            OR NOT _overte_e2e_files_status EQUAL 0 OR NOT _overte_e2e_head_length EQUAL 40
            OR NOT _overte_e2e_head MATCHES "^[0-9a-f]+$" OR NOT _overte_e2e_status STREQUAL "")
        return()
    endif()
    string(REPLACE "\n" ";" _overte_e2e_files "${_overte_e2e_files}")
    set(_overte_e2e_dependencies "")
    foreach(_overte_e2e_file IN LISTS _overte_e2e_files)
        if(NOT _overte_e2e_file STREQUAL "")
            if(_overte_e2e_file MATCHES "[\"\\;]" OR NOT EXISTS "${source_root}/${_overte_e2e_file}")
                return()
            endif()
            list(APPEND _overte_e2e_dependencies "${source_root}/${_overte_e2e_file}")
        endif()
    endforeach()
    execute_process(COMMAND "${_overte_e2e_git}" -C "${source_root}" symbolic-ref -q HEAD
        OUTPUT_VARIABLE _overte_e2e_reference ERROR_QUIET OUTPUT_STRIP_TRAILING_WHITESPACE TIMEOUT 5)
    foreach(_overte_e2e_metadata IN ITEMS HEAD logs/HEAD packed-refs "${_overte_e2e_reference}")
        execute_process(COMMAND "${_overte_e2e_git}" -C "${source_root}" rev-parse --git-path "${_overte_e2e_metadata}"
            RESULT_VARIABLE _overte_e2e_meta_status OUTPUT_VARIABLE _overte_e2e_meta ERROR_QUIET OUTPUT_STRIP_TRAILING_WHITESPACE TIMEOUT 5)
        if(_overte_e2e_meta_status EQUAL 0)
            if(NOT IS_ABSOLUTE "${_overte_e2e_meta}")
                set(_overte_e2e_meta "${source_root}/${_overte_e2e_meta}")
            endif()
            if(EXISTS "${_overte_e2e_meta}")
                list(APPEND _overte_e2e_dependencies "${_overte_e2e_meta}")
            endif()
        endif()
    endforeach()
    set(OVERTE_E2E_CONFIGURED_SOURCE_REVISION "${_overte_e2e_head}" PARENT_SCOPE)
    set(OVERTE_E2E_SOURCE_DEPENDENCIES "${_overte_e2e_dependencies}" PARENT_SCOPE)
endfunction()
