set(TARGET_NAME qml)
setup_hifi_library(Multimedia Network Qml Quick WebChannel WebSockets ${PLATFORM_QT_COMPONENTS})
if (IOS AND OVERTE_E2E_FEATURE_TESTS AND OVERTE_IOS_E2E_TEST_BUILD)
    target_compile_definitions(${TARGET_NAME} PRIVATE OVERTE_IOS_E2E_TEST_BUILD=1)
    if (TARGET Qt6::QmlPrivate)
        # An unpatched or unavailable private SDK keeps source receipts absent.
        # The patched binary and all its private consumers require one matching SDK.
        target_link_libraries(${TARGET_NAME} PRIVATE Qt6::QmlPrivate)
        target_compile_definitions(${TARGET_NAME} PRIVATE OVERTE_E2E_QML_PRIVATE_API=1)
    endif()
endif()
link_hifi_libraries(shared networking gl)

# Required for some low level GL interaction in the OffscreenQMLSurface
set(OpenGL_GL_PREFERENCE "GLVND")
target_opengl()
