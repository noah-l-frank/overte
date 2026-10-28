set(TARGET_NAME material-networking)
setup_hifi_library()
link_hifi_libraries(shared shaders networking graphics ktx image gl)
include_hifi_library_headers(gpu)
include_hifi_library_headers(hfm)

if (IOS AND OVERTE_E2E_FEATURE_TESTS AND OVERTE_IOS_E2E_TEST_BUILD)
    target_compile_definitions(${TARGET_NAME} PRIVATE OVERTE_IOS_E2E_TEST_BUILD=1)
    if (TARGET Qt6::CorePrivate)
        # Optional matching QtCore SDK; an absent/unpatched API stays unavailable.
        # Rebuild the complete SDK and all private-header consumers together.
        target_link_libraries(${TARGET_NAME} PRIVATE Qt6::CorePrivate)
        target_compile_definitions(${TARGET_NAME} PRIVATE OVERTE_E2E_METACALL_PRIVATE_API=1)
        target_compile_definitions(${TARGET_NAME} PRIVATE OVERTE_E2E_RUNNABLE_POOL_PRIVATE_API=1)
    endif()
endif()
