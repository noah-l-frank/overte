# SPDX-License-Identifier: Apache-2.0
# The protected executing consumer verifies these package/tool bytes first.
function(overte_common_bind_qt_tools)
    foreach(_tool moc rcc uic qmake)
        string(TOUPPER "${_tool}" _upper)
        set(_path "${OVERTE_ANDROID_CI_${_upper}}")
        if(NOT IS_ABSOLUTE "${_path}" OR NOT EXISTS "${_path}" OR IS_DIRECTORY "${_path}" OR
           NOT TARGET Qt5::${_tool})
            message(FATAL_ERROR "Missing bound Android CI Qt host tool: ${_tool}")
        endif()
        set_target_properties(Qt5::${_tool} PROPERTIES
            IMPORTED_LOCATION "${_path}"
            IMPORTED_LOCATION_DEBUG "${_path}"
            IMPORTED_LOCATION_RELEASE "${_path}"
            IMPORTED_LOCATION_RELWITHDEBINFO "${_path}"
            MAP_IMPORTED_CONFIG_RELWITHDEBINFO "")
    endforeach()
    # Qt's resource/UI custom commands consult these before generation too.
    set(Qt5Core_MOC_EXECUTABLE Qt5::moc PARENT_SCOPE)
    set(Qt5Core_RCC_EXECUTABLE Qt5::rcc PARENT_SCOPE)
    set(Qt5Core_QMAKE_EXECUTABLE Qt5::qmake PARENT_SCOPE)
    set(Qt5Widgets_UIC_EXECUTABLE Qt5::uic PARENT_SCOPE)
endfunction()
