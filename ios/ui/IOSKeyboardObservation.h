// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "../../tests/device/native/IOSKeyboardBridge.h"
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD) && defined(__OBJC__)
#if !__has_feature(objc_arc)
#error IOSKeyboardObservation requires the existing ARC-enabled metrics translation unit.
#endif
#import <UIKit/UIKit.h>
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QElapsedTimer>
#include <QJsonArray>
#include <QJsonDocument>
#include <QPointer>
#include <QSet>
#include <QThread>
#include <QUuid>
#include <cmath>
#include <cstring>
#include <memory>
#include <vector>

namespace overte::ios::keyboard_source {
// Reads original OS notifications and public responder state only. It never
// requests, dismisses or changes a keyboard, field, responder or focus owner.
struct Object {QString id,kind;__weak NSObject* object=nil;QJsonObject born,expired;};
struct State {
    QString instance=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
    QElapsedTimer timer;QPointer<QObject> owner;QJsonObject registered;QJsonArray events;
    std::vector<std::unique_ptr<Object>> objects;QSet<QString> requests;
    qint64 lastEpoch=0,lastMono=0;quint64 sequence=0;bool complete=true;
    QVariantMap lastQuery,lastPacket;
    State() {timer.start();}
};
inline State& state() {static State value;return value;}
inline bool enabled() {
    return QCoreApplication::instance() && NSThread.isMainThread
        && QThread::currentThread()==QCoreApplication::instance()->thread()
        && QCoreApplication::arguments().contains("--testScript");
}
inline QJsonObject stamp() {
    auto& s=state();const auto epoch=QDateTime::currentMSecsSinceEpoch(),mono=s.timer.elapsed();
    if (epoch<=0 || mono<0 || epoch<s.lastEpoch || mono<s.lastMono
            || (s.lastEpoch && qAbs(epoch-s.lastEpoch-mono+s.lastMono)>250)) {s.complete=false;}
    s.lastEpoch=epoch;s.lastMono=mono;return {{"epochMs",epoch},{"monotonicMs",mono}};
}
inline QString objectId(NSObject* object,const QString& kind) {
    if (!object) {return {};}
    auto& s=state();for (const auto& row:s.objects) {
        if (row->object==object) {if (row->kind!=kind) {s.complete=false;}return row->id;}
    }
    if (s.objects.size()>=128) {s.complete=false;return {};}
    auto row=std::make_unique<Object>();row->object=object;row->kind=kind;row->born=stamp();
    row->id=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');const auto id=row->id;
    s.objects.push_back(std::move(row));return id;
}
inline QString geometry(UIWindow* window) {
    if (!window || !window.screen || !window.windowScene) {return {};}
    const auto rect=window.bounds;const double values[]={rect.origin.x,rect.origin.y,rect.size.width,rect.size.height,window.screen.scale};
    for (double value:values) {if (!std::isfinite(value) || qAbs(value)>1000000) {return {};}}
    if (rect.size.width<=0 || rect.size.height<=0 || window.screen.scale<=0) {return {};}
    QJsonArray raw;for (double value:values) {raw.append(value);}raw.append(static_cast<int>(window.windowScene.interfaceOrientation));
    return QString::fromLatin1(QCryptographicHash::hash(QJsonDocument(raw).toJson(QJsonDocument::Compact),QCryptographicHash::Sha256).toHex());
}
inline QString kind(NSNotificationName name) {
    if ([name isEqualToString:UIKeyboardWillShowNotification]) {return "will-show";}
    if ([name isEqualToString:UIKeyboardDidShowNotification]) {return "did-show";}
    if ([name isEqualToString:UIKeyboardWillHideNotification]) {return "will-hide";}
    if ([name isEqualToString:UIKeyboardDidHideNotification]) {return "did-hide";}
    if ([name isEqualToString:UIKeyboardWillChangeFrameNotification]) {return "will-change-frame";}
    if ([name isEqualToString:UIKeyboardDidChangeFrameNotification]) {return "did-change-frame";}
    return {};
}
inline void received(NSNotification* original,UIWindow* window) noexcept {
    if (!enabled() || !original) {return;}
    try { @try {
        auto& s=state();const auto eventKind=kind(original.name);if (eventKind.isEmpty() || s.registered.isEmpty()) {return;}
        if (s.events.size()>=256) {s.complete=false;return;}
        const auto key=window && window.isKeyWindow && !window.hidden
            && window.windowScene.activationState==UISceneActivationStateForegroundActive ? window : nil;
        const auto identity=objectId(key,"window");
        id local=original.userInfo[UIKeyboardIsLocalUserInfoKey];
        QJsonValue isLocal=QJsonValue(QJsonValue::Null);
        if ([local isKindOfClass:NSNumber.class] && CFGetTypeID((__bridge CFTypeRef)local)==CFBooleanGetTypeID()) {isLocal=QJsonValue([local boolValue]);}
        QJsonValue screenMatches=QJsonValue(QJsonValue::Null);
        if ([original.object isKindOfClass:UIScreen.class] && key) {screenMatches=QJsonValue(original.object==key.screen);}
        bool valid=false,intersects=false;id raw=original.userInfo[UIKeyboardFrameEndUserInfoKey];
        if (key && [raw isKindOfClass:NSValue.class] && std::strcmp([raw objCType],@encode(CGRect))==0) {
            const auto frame=[raw CGRectValue];const double values[]={frame.origin.x,frame.origin.y,frame.size.width,frame.size.height};
            valid=true;for (double value:values) {if (!std::isfinite(value) || qAbs(value)>1000000) {valid=false;}}
            valid=valid && frame.size.width>=0 && frame.size.height>=0;
            if (valid) {
                const auto converted=[key convertRect:frame fromCoordinateSpace:key.screen.coordinateSpace];
                const double measured[]={converted.origin.x,converted.origin.y,converted.size.width,converted.size.height};
                for (double value:measured) {if (!std::isfinite(value) || qAbs(value)>1000000) {valid=false;}}
                if (valid) {
                    const auto overlap=CGRectIntersection(key.bounds,converted);
                    intersects=!CGRectIsNull(overlap) && !CGRectIsEmpty(overlap);
                }
            }
        }
        s.events.append(QJsonObject{{"sequence",s.events.size()+1},{"eventId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
            {"kind",eventKind},{"clock",stamp()},{"local",isLocal},{"screenMatches",screenMatches},
            {"window",identity.isEmpty() ? QJsonValue(QJsonValue::Null) : QJsonValue(identity)},
            {"geometrySha256",key ? QJsonValue(geometry(key)) : QJsonValue(QJsonValue::Null)},
            {"frame",QJsonObject{{"valid",valid},{"intersectsWindow",valid ? QJsonValue(intersects) : QJsonValue(QJsonValue::Null)}}}});
    } @catch (NSException*) {state().complete=false;} } catch (...) {state().complete=false;}
}
inline UIView* responder(UIView* view,int depth,int& visited,QSet<quintptr>& seen) {
    if (!view) {return nil;}const auto address=reinterpret_cast<quintptr>((__bridge void*)view);
    if (depth>128 || ++visited>4096 || seen.contains(address)) {state().complete=false;return nil;}seen.insert(address);
    UIView* found=view.isFirstResponder ? view : nil;
    for (UIView* child in view.subviews) {
        auto candidate=responder(child,depth+1,visited,seen);
        if (candidate) {if (found) {state().complete=false;}else {found=candidate;}}
        if (!state().complete) {return found;}
    }
    return found;
}
inline QVariantMap capture(const QVariantMap& query,NSArray<UIWindow*>* windows) {
    auto& s=state();if (!enabled() || !overte::e2e::keyboard::command(query) || s.registered.isEmpty() || !s.owner) {return {};}
    const auto request=query.value("commandId").toString();
    if (s.requests.contains(request)) {return query==s.lastQuery ? s.lastPacket : QVariantMap{};}
    if (s.requests.size()>=512) {s.complete=false;return {};}
    s.requests.insert(request);const auto before=stamp();QJsonArray current;
    @autoreleasepool {
        if (!windows || windows.count>64) {s.complete=false;}
        int visited=0;QSet<quintptr> windowIds;
        for (UIWindow* window in windows) {
            if (current.size()>=64) {s.complete=false;break;}
            const auto address=reinterpret_cast<quintptr>((__bridge void*)window);
            if (windowIds.contains(address)) {s.complete=false;break;}windowIds.insert(address);
            QSet<quintptr> seen;auto actual=responder(window,0,visited,seen);
            const auto responderKind=[actual isKindOfClass:UIWindow.class] ? QString("window") : QString("responder");
            const auto first=objectId(actual,responderKind);const auto identifier=objectId(window,"window");
            auto className=actual ? QString::fromUtf8(NSStringFromClass(actual.class).UTF8String) : QString();
            if (className.size()>256 || identifier.isEmpty()) {s.complete=false;}
            current.append(QJsonObject{{"id",identifier},{"key",bool(window.isKeyWindow)},{"visible",!window.hidden},
                {"sceneActive",window.windowScene && window.windowScene.activationState==UISceneActivationStateForegroundActive},
                {"geometrySha256",geometry(window)},
                {"responder",first.isEmpty() ? QJsonValue(QJsonValue::Null) : QJsonValue(QJsonObject{{"id",first},{"className",className}})}});
        }
    }
    QJsonArray objects;
    for (const auto& row:s.objects) {
        const bool alive=row->object!=nil;if (!alive && row->expired.isEmpty()) {row->expired=stamp();}
        objects.append(QJsonObject{{"id",row->id},{"kind",row->kind},{"born",row->born},
            {"expired",row->expired.isEmpty() ? QJsonValue(QJsonValue::Null) : QJsonValue(row->expired)},{"alive",alive}});
    }
    QJsonObject packet{{"iosKeyboardVersion",1},{"requestId",request},{"runId",query.value("runId").toString()},
        {"instance",s.instance},{"sequence",static_cast<double>(++s.sequence)},
        {"processId",static_cast<double>(QCoreApplication::applicationPid())},{"clockDomain","native-main-ios-keyboard"},
        {"clockBefore",before},{"clockAfter",stamp()},
        {"source",QJsonObject{{"registered",s.registered},{"complete",s.complete},{"ownerAlive",bool(s.owner)},
            {"applicationActive",UIApplication.sharedApplication.applicationState==UIApplicationStateActive},
            {"events",s.events},{"objects",objects},{"windows",current}}}};
    s.lastQuery=query;s.lastPacket=packet.toVariantMap();return s.lastPacket;
}
inline void install(QObject* owner,std::function<NSArray<UIWindow*>*()> windows) {
    if (!enabled() || !owner || !windows || !state().registered.isEmpty()
            || QCoreApplication::instance()->property(overte::e2e::keyboard::property()).isValid()) {return;}
    state().owner=owner;state().registered=stamp();QPointer<QObject> guarded(owner);
    overte::e2e::keyboard::Provider provider=[guarded,windows](const QVariantMap& query) {
        if (!guarded) {return QVariantMap{};}return capture(query,windows());
    };
    QCoreApplication::instance()->setProperty(overte::e2e::keyboard::property(),QVariant::fromValue(provider));
}
}
#endif
