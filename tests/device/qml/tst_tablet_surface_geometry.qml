import QtQuick 2.12
import QtTest 1.2
import "../../../interface/resources/qml/hifi/tablet" as TabletUi
import "../../../interface/resources/qml/controlsUit" as Controls

TestCase {
    name: "TabletSurfaceGeometry"
    Component { id: profileComponent; Controls.TouchUiProfileBase {} }
    Component { id: geometryComponent; TabletUi.TabletSurfaceGeometry {} }

    function test_centeredSafeRectangle_data() {
        return [
            {tag: "pixel6a-left", w: 2400, h: 1080, l: 132, r: 0},
            {tag: "right-cutout", w: 2400, h: 1080, l: 0, r: 132},
            {tag: "asymmetric", w: 1024, h: 768, l: 8, r: 32},
            {tag: "compact", w: 640, h: 360, l: 24, r: 8},
            {tag: "no-cutout", w: 360, h: 640, l: 0, r: 0}
        ]
    }

    function test_centeredSafeRectangle(data) {
        var profile = createTemporaryObject(profileComponent, this, {
            surfaceWidth: data.w, surfaceHeight: data.h,
            safeInsetLeft: data.l, safeInsetRight: data.r,
            safeInsetTop: 12, safeInsetBottom: 24,
            density: 2.625, screenSpaceContentScale: 2.5,
            centerScreenSpaceHorizontally: true
        })
        var geometry = createTemporaryObject(geometryComponent, this, {profile: profile})
        var inset = Math.max(data.l, data.r)
        for (var cycle = 0; cycle < 3; ++cycle) {
            profile.imeInsetBottom = 180
            compare(geometry.height, data.h - 12 - 180)
            compare(geometry.x, inset)
            compare(geometry.x + geometry.width / 2, data.w / 2)
            compare(geometry.width, data.w - 2 * inset)
            verify(geometry.x >= data.l)
            verify(geometry.x + geometry.width <= data.w - data.r)
            profile.imeInsetBottom = 0
            compare(geometry.height, data.h - 12 - 24)
        }
        // A host that already applied the leading inset must not apply it twice.
        profile.screenSpaceOriginAtSafeArea = true
        compare(geometry.x + data.l + geometry.width / 2, data.w / 2)
        profile.centerScreenSpaceHorizontally = false
        compare(geometry.x, 0)
        compare(geometry.width, data.w - data.l - data.r)
        compare(profile.safeInsetLeft, data.l)
        compare(profile.safeInsetRight, data.r)
    }

    function test_centeringNeverReducesCutoutProtection() {
        var profile = createTemporaryObject(profileComponent, this, {
            surfaceWidth: 100, surfaceHeight: 80,
            safeInsetLeft: 80, safeInsetRight: 19,
            centerScreenSpaceHorizontally: true
        })
        var geometry = createTemporaryObject(geometryComponent, this, {profile: profile})
        verify(geometry.valid)
        verify(!geometry.centered)
        compare(geometry.x, 80)
        compare(geometry.width, 1)
    }

    function test_rotationKeyboardAndNativeOrigin() {
        var profile = createTemporaryObject(profileComponent, this, {
            surfaceWidth: 768, surfaceHeight: 1024,
            safeInsetLeft: 8, safeInsetRight: 12, safeInsetTop: 24, safeInsetBottom: 20
        })
        var geometry = createTemporaryObject(geometryComponent, this, {profile: profile})
        verify(geometry.valid)
        compare(geometry.x, 8)
        compare(geometry.y, 24)
        compare(geometry.width, 748)
        compare(geometry.height, 980)
        profile.screenSpaceOriginAtSafeArea = true
        compare(geometry.x, 0)
        compare(geometry.y, 0)
        compare(geometry.width, 748)
        profile.surfaceWidth = 1024
        profile.surfaceHeight = 768
        profile.imeInsetBottom = 300
        compare(geometry.width, 1004)
        compare(geometry.height, 444)
        profile.imeInsetBottom = 0
        compare(geometry.height, 724)
        profile.surfaceWidth = 0
        verify(!geometry.valid)
        compare(geometry.width, 1)
    }
}
