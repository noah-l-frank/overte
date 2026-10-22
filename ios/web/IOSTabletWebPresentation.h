// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QtCore/qglobal.h>
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(__OBJC__)
#import <UIKit/UIKit.h>
#import <WebKit/WebKit.h>
#import <objc/runtime.h>
#include "IOSTabletWebTrace.h"
#include <cmath>

namespace overte::ios::tablet_web_presentation {
// The associated value is an opaque immutable birth string. It retains no
// UIView/window/event/touch and grants no source ownership or UI authority.
inline QString birth(NSObject* object) {
    if (!object || !world_web_trace::enabled() || !world_web_trace::mainThread()) { return {}; }
    static char key;
    NSString* original=objc_getAssociatedObject(object,&key);
    if (!original) {
        original=[NSUUID.UUID.UUIDString.lowercaseString stringByReplacingOccurrencesOfString:@"-" withString:@""];
        objc_setAssociatedObject(object,&key,original,OBJC_ASSOCIATION_COPY_NONATOMIC);
    }
    return QString::fromUtf8(original.UTF8String);
}
inline QVariantList rect(CGRect value) { return {value.origin.x,value.origin.y,value.size.width,value.size.height}; }
inline QVariantList insets(UIEdgeInsets value) { return {value.left,value.top,value.right,value.bottom}; }
inline bool finite(CGRect value) {
    return std::isfinite(value.origin.x) && std::isfinite(value.origin.y) && std::isfinite(value.size.width) && std::isfinite(value.size.height);
}
inline QVariantMap observe(WKWebView* view,UIWindow* window,UINavigationController* presentation,UIViewController* presenter) {
    if (!world_web_trace::enabled() || !world_web_trace::mainThread() || !view || !window || !presentation || !presenter) { return {}; }
    @try {
        UIViewController* top=window.rootViewController;
        QSet<QString> visited;
        while (top && top.presentedViewController) {
            const auto id=birth(top);if (visited.contains(id) || visited.size()>=32) { return {}; }visited.insert(id);top=top.presentedViewController;
        }
        UIViewController* controller=presentation.topViewController;
        if (!controller || !view.superview || !window.windowScene || !window.screen || !presentation.isViewLoaded
                || !controller.isViewLoaded || !presenter.isViewLoaded) { return {}; }
        const auto frame=[view convertRect:view.bounds toView:window];
        const auto screenFrame=[view convertRect:view.bounds toCoordinateSpace:window.screen.coordinateSpace];
        const auto screenCoordinates=window.screen.coordinateSpace.bounds;
        if (!finite(frame) || !finite(screenFrame) || !finite(screenCoordinates) || !finite(window.bounds) || !finite(window.frame) || !finite(view.bounds) || !finite(window.screen.bounds)
                || !finite(window.screen.nativeBounds)) { return {}; }
        QVariantList responders,recognizers;QList<UIView*> pending{view};int seen=0;
        // Arrays are confined to this snapshot. No UIKit object is retained in
        // the stored original. This is current geometry/recognizer state only,
        // expressly not an original UIApplication touch-lifetime ledger.
        while (!pending.isEmpty()) {
            UIView* current=pending.takeLast();if (!current || ++seen>1024) { return {}; }
            if (current.isFirstResponder) { responders.push_back(birth(current)); }
            for (UIGestureRecognizer* recognizer in current.gestureRecognizers) {
                if (recognizers.size()>=1024) { return {}; }
                recognizers.push_back(QVariantMap{{"id",birth(recognizer)},{"view",birth(current)},
                    {"state",static_cast<int>(recognizer.state)},{"enabled",static_cast<bool>(recognizer.enabled)}});
            }
            for (UIView* child in current.subviews) { pending.push_back(child); }
        }
        UIScrollView* scroll=view.scrollView;const auto offset=scroll.contentOffset;const auto size=scroll.contentSize;
        if (!std::isfinite(offset.x) || !std::isfinite(offset.y) || !std::isfinite(size.width) || !std::isfinite(size.height)
                || !std::isfinite(scroll.zoomScale) || !std::isfinite(view.alpha) || !std::isfinite(window.screen.scale)) { return {}; }
        return {{"tabletPresentationVersion",1},{"window",birth(window)},{"scene",birth(window.windowScene)},
            {"view",birth(view)},{"presentation",birth(presentation)},{"presenter",birth(presenter)},{"controller",birth(controller)},{"top",birth(top)},
            {"applicationState",static_cast<int>(UIApplication.sharedApplication.applicationState)},
            {"sceneActivationState",static_cast<int>(window.windowScene.activationState)},
            {"interfaceOrientation",static_cast<int>(window.windowScene.interfaceOrientation)},
            {"keyWindow",static_cast<bool>(window.isKeyWindow)},{"mainScreen",static_cast<bool>(window.screen==UIScreen.mainScreen)},
            {"viewWindowMatches",static_cast<bool>(view.window==window)},{"presentationWindowMatches",static_cast<bool>(presentation.view.window==window)},
            {"presented",static_cast<bool>(presentation.presentingViewController==presenter)},
            {"topMatches",static_cast<bool>(top==presentation)},{"viewInController",static_cast<bool>([view isDescendantOfView:controller.view])},
            {"beingPresented",static_cast<bool>(presentation.isBeingPresented)},{"beingDismissed",static_cast<bool>(presentation.isBeingDismissed)},
            {"hidden",static_cast<bool>(view.hidden)},{"interactionEnabled",static_cast<bool>(view.userInteractionEnabled)},{"alpha",view.alpha},
            {"windowBounds",rect(window.bounds)},{"windowFrame",rect(window.frame)},{"viewBounds",rect(view.bounds)},{"viewFrame",rect(frame)},
            {"screenBounds",rect(window.screen.bounds)},{"screenCoordinates",rect(screenCoordinates)},{"screenFrame",rect(screenFrame)},{"nativeScreenBounds",rect(window.screen.nativeBounds)},{"screenScale",window.screen.scale},
            {"safeInsets",insets(view.safeAreaInsets)},{"scrollOffset",QVariantList{offset.x,offset.y}},
            {"scrollSize",QVariantList{size.width,size.height}},{"scrollInsets",insets(scroll.adjustedContentInset)},{"zoomScale",scroll.zoomScale},
            {"dragging",static_cast<bool>(scroll.dragging)},{"decelerating",static_cast<bool>(scroll.decelerating)},
            {"tracking",static_cast<bool>(scroll.tracking)},{"zooming",static_cast<bool>(scroll.zooming)},
            {"responders",responders},{"recognizers",recognizers}};
    } @catch (NSException*) { return {}; }
}
inline bool current(const QVariantMap& value) {
    if (value.isEmpty()) { return false; }const auto json=QJsonObject::fromVariantMap(value);
    if (json.value("tabletPresentationVersion")!=QJsonValue(1) || json.value("applicationState")!=QJsonValue(0)
            || json.value("sceneActivationState")!=QJsonValue(0) || !json.value("alpha").isDouble() || json.value("alpha").toDouble()<=0) { return false; }
    for (const auto* key:{"keyWindow","mainScreen","viewWindowMatches","presentationWindowMatches","presented","topMatches","viewInController","interactionEnabled"}) {
        if (json.value(key)!=QJsonValue(true)) { return false; }
    }
    for (const auto* key:{"beingPresented","beingDismissed","hidden"}) { if (json.value(key)!=QJsonValue(false)) { return false; } }
    return json.value("top")==json.value("presentation");
}
} // namespace overte::ios::tablet_web_presentation
#endif
