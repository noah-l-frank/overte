import QtQuick 2.7

QtObject {
    property var profile
    readonly property real horizontalProtection: Math.max(profile.safeInsetLeft, profile.safeInsetRight)
    // If no centered safe rectangle fits, retain the actual safe rectangle
    // rather than reducing protection or collapsing the surface.
    readonly property bool centered: profile.centerScreenSpaceHorizontally
        && profile.surfaceWidth > 2 * horizontalProtection
    readonly property real left: centered ? horizontalProtection : profile.safeInsetLeft
    readonly property real right: centered ? horizontalProtection : profile.safeInsetRight
    readonly property real x: left - (profile.screenSpaceOriginAtSafeArea ? profile.safeInsetLeft : 0)
    readonly property real y: profile.screenSpaceOriginAtSafeArea ? 0 : profile.safeInsetTop
    readonly property real width: Math.max(1,
        profile.surfaceWidth - left - right)
    readonly property real height: Math.max(1, profile.surfaceHeight - profile.safeInsetTop
        - Math.max(profile.safeInsetBottom, profile.imeInsetBottom))
    readonly property bool valid: profile.surfaceWidth > profile.safeInsetLeft + profile.safeInsetRight
        && profile.surfaceHeight > profile.safeInsetTop + Math.max(profile.safeInsetBottom, profile.imeInsetBottom)
}
