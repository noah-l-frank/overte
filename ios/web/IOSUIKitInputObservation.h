// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QtCore/qglobal.h>
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include <QVariantMap>
namespace overte::ios::uikit_input {
// Implemented in the existing ARC-enabled IOSWebView.mm, invoked after the
// real QApplication base is constructed and before its first app window.
void startup() noexcept;
QVariantMap observation(const QVariantMap&);
}
#endif
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(__OBJC__)
#if !__has_feature(objc_arc)
#error IOSUIKitInputObservation requires the existing ARC-enabled IOSWebView translation unit.
#endif
#import <UIKit/UIKit.h>
#import <WebKit/WebKit.h>
#import <objc/runtime.h>
#include "IOSTabletWebTrace.h"
#include <QGuiApplication>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <vector>

namespace overte::ios::uikit_input {
// No location, pressure, key, text, responder contents or UIEvent description
// is read. Object births, logical contact lifetimes and dispatch returns are
// separate original facts. A cached ended UITouch is expressly still alive.
using SendEvent=void(*)(id,SEL,UIEvent*);
struct Object {
    QString id,kind;__weak NSObject* object=nil;QVariantMap born,expired;
};
struct Target { __weak WKWebView* view=nil;QString object;QVariantMap identity,clock; };
struct Contact { QString id,kind,object,target,window;QVariantMap source,began,ended;int phase{0};bool active{true}; };
struct State {
    const QString instance{world_web_trace::nonce()};QElapsedTimer timer;
    qint64 lastEpoch{0},lastMonotonic{0};quint64 sequence{0},dispatchSequence{0};
    bool attempted{false},installed{false},complete{true};QString failure,applicationClass;
    Class runtimeClass{Nil};SendEvent original{nullptr};QVariantMap installation;
    std::vector<std::unique_ptr<Object>> objects;QList<Target> targets;
    QList<Contact> contacts;QVariantList dispatches;QSet<quint64> pending;
    State() { timer.start(); }
};
inline State& state() { static auto* actual=new State;return *actual; }
inline void invalidate(const QString& reason) noexcept {
    try { auto& actual=state();actual.complete=false;if (actual.failure.isEmpty()) { actual.failure=reason; } } catch (...) {}
}
inline QVariantMap clock(State& actual) {
    const auto epoch=QDateTime::currentMSecsSinceEpoch(),mono=actual.timer.elapsed();
    if (epoch<=0 || mono<0 || epoch<actual.lastEpoch || mono<actual.lastMonotonic
            || (actual.lastEpoch && qAbs(epoch-actual.lastEpoch-mono+actual.lastMonotonic)>250)) { invalidate("clock-discontinuity"); }
    actual.lastEpoch=epoch;actual.lastMonotonic=mono;return {{"epochMs",epoch},{"monotonicMs",mono}};
}
inline bool enabled() { return overte::e2e::tablet_sources::enabled(); }
inline bool mainThread() { return NSThread.isMainThread && overte::e2e::tablet_sources::mainThread(); }
inline Object* birth(NSObject* object,const QString& kind) {
    if (!object) { return nullptr; }auto& actual=state();
    for (const auto& row:actual.objects) { if (row->object==object) { if (row->kind!=kind) { invalidate("object-kind-changed"); }return row.get(); } }
    if (actual.objects.size()>=8192) { invalidate("object-capacity");return nullptr; }
    auto row=std::make_unique<Object>();row->id=world_web_trace::nonce();row->kind=kind;row->object=object;row->born=clock(actual);
    const auto result=row.get();actual.objects.push_back(std::move(row));return result;
}
inline QString objectId(NSObject* value,const QString& kind) {
    const auto actualKind=kind=="view" && [value isKindOfClass:UIWindow.class] ? QString("window") : kind;
    const auto row=birth(value,actualKind);return row ? row->id : QString();
}
inline void sweep() {
    auto& actual=state();for (const auto& row:actual.objects) {
        // A nil zeroing weak reference is a positive object-death observation,
        // not a dealloc entry, an ended phase or a forced release/reset.
        if (!row->object && row->expired.isEmpty()) { row->expired=clock(actual); }
    }
}
inline void bind(WKWebView* view,const QVariantMap& identity) noexcept {
    if (!enabled()) { return; }
    try { @try {
        if (!mainThread() || !view || tablet_web_trace::rootFor(identity).isEmpty()) { return; }
        auto& actual=state();if (!actual.installed) { invalidate("view-before-installation");return; }
        const auto id=objectId(view,"view");
        for (const auto& target:actual.targets) { if (target.view==view) { if (target.identity!=identity) { invalidate("view-source-rebound"); }return; } }
        if (actual.targets.size()>=1024 || id.isEmpty()) { invalidate("target-capacity");return; }
        actual.targets.push_back(Target{view,id,identity,clock(actual)});
    } @catch (NSException*) { invalidate("binding-exception"); } } catch (...) { invalidate("binding-exception"); }
}
inline QVariantMap association(UIView* view) {
    QSet<QString> visited;QVariantList ancestry;auto& actual=state();
    for (UIView* current=view;current;current=current.superview) {
        const auto id=objectId(current,"view");if (id.isEmpty() || visited.contains(id) || visited.size()>=128) { invalidate("view-ancestry");return {}; }
        visited.insert(id);ancestry.push_back(id);for (const auto& target:actual.targets) { if (target.view==current) { return {{"view",target.object},{"identity",target.identity},{"bound",target.clock},{"ancestry",ancestry}}; } }
    }return {};
}
inline QVariantMap contact(NSObject* object,const QString& kind,int phase,UIView* view,UIWindow* window) {
    auto& actual=state();const auto id=objectId(object,kind);if (id.isEmpty()) { return {}; }
    const auto target=objectId(view,"view"),windowId=objectId(window,"window");const auto source=association(view);
    Contact* current=nullptr;
    for (auto& row:actual.contacts) { if (row.object==id && row.active) { if (current) { invalidate("duplicate-active-contact"); }current=&row; } }
    // UITouch/UIPress share public began=0, changed/moved=1, stationary=2,
    // ended=3, cancelled=4. No force/location/key property is inspected.
    if (phase<0 || phase>4) { invalidate("unknown-contact-phase"); }
    if (phase==0) {
        if (current) { invalidate("began-while-active"); }
        else if (actual.contacts.size()>=8192) { invalidate("contact-capacity"); }
        else { actual.contacts.push_back(Contact{world_web_trace::nonce(),kind,id,target,windowId,source,clock(actual),{},phase,true});current=&actual.contacts.last(); }
    } else if (!current) { invalidate("contact-without-began"); }
    if (current) {
        if (current->target!=target || current->window!=windowId || current->source!=source) { invalidate("contact-target-changed"); }
        current->phase=phase;if (phase==3 || phase==4) { current->active=false;current->ended=clock(actual); }
    }
    return {{"object",id},{"contact",current ? QVariant(current->id) : QVariant()}, {"kind",kind},{"phase",phase},
        {"target",target.isEmpty() ? QVariant() : QVariant(target)},{"window",windowId.isEmpty() ? QVariant() : QVariant(windowId)},
        {"source",source.isEmpty() ? QVariant() : QVariant(source)}};
}
inline quint64 entered(UIEvent* event) {
    auto& actual=state();if (!mainThread() || !event || actual.dispatches.size()>=4096 || actual.dispatchSequence>=9007199254740991ULL) { invalidate("dispatch-unavailable");return 0; }
    const auto entry=++actual.dispatchSequence;actual.pending.insert(entry);
    const auto id=objectId(event,"event");const auto stamp=clock(actual);QVariantList phases;
    // The autorelease pool and all temporary collections end BEFORE forwarding
    // sendEvent. The observation holds no strong event/touch/view over dispatch.
    @autoreleasepool {
        for (UITouch* touch in event.allTouches) {
            phases.push_back(contact(touch,"touch",static_cast<int>(touch.phase),touch.view,touch.window));
        }
        if ([event isKindOfClass:UIPressesEvent.class]) {
            for (UIPress* press in ((UIPressesEvent*)event).allPresses) {
                UIResponder* responder=press.responder;UIView* view=[responder isKindOfClass:UIView.class] ? (UIView*)responder : nil;
                phases.push_back(contact(press,"press",static_cast<int>(press.phase),view,view.window));
            }
        }
    }
    actual.dispatches.push_back(QVariantMap{{"sequence",static_cast<qulonglong>(entry)},{"event",id},{"entered",stamp},
        {"returned",QVariant()},{"finally",QVariant()},{"phases",phases}});return entry;
}
inline void finish(quint64 entry,bool returned) {
    if (!entry) { return; }auto& actual=state();
    if (!mainThread() || !actual.pending.contains(entry)) { invalidate("dispatch-finish-without-entry");return; }
    for (auto& value:actual.dispatches) { auto row=value.toMap();if (row.value("sequence").toULongLong()!=entry) { continue; }
        if (returned) { row["returned"]=clock(actual); }
        row["finally"]=clock(actual);value=row;actual.pending.remove(entry);sweep();return;
    }invalidate("dispatch-entry-lost");
}
inline void intercepted(id __unsafe_unretained application,SEL selector,UIEvent* __unsafe_unretained event) {
    // No Objective-C/C++ observer exception is allowed to replace an original
    // application exception. There is exactly ONE original call, outside those
    // catches. @finally records unwinding but never claims a normal return.
    auto original=state().original;quint64 entry=0;bool returned=false;
    try { @try { entry=entered(event); } @catch (NSException*) { invalidate("entry-exception"); } } catch (...) { invalidate("entry-exception"); }
    @try { original(application,selector,event);returned=true; }
    @finally { try { @try { finish(entry,returned); } @catch (NSException*) { invalidate("finish-exception"); } } catch (...) { invalidate("finish-exception"); } }
}
inline bool methodUnchanged() {
    auto& actual=state();return actual.installed && actual.runtimeClass
        && class_getMethodImplementation(actual.runtimeClass,@selector(sendEvent:))==reinterpret_cast<IMP>(&intercepted);
}
inline void install() noexcept {
    // Only the startup callsite invokes this. No snapshot/read retries or resets
    // it; a missing/late installation remains unavailable for this process.
    if (!enabled()) { return; }
    try { @try {
        auto& actual=state();if (actual.attempted) { invalidate("installation-repeated");return; }actual.attempted=true;
        if (!mainThread() || !qobject_cast<QGuiApplication*>(QCoreApplication::instance()) || !QGuiApplication::allWindows().isEmpty()) { invalidate("installation-after-qt-window");return; }
        UIApplication* app=UIApplication.sharedApplication;
        if (!app || app.windows.count!=0) { invalidate("installation-after-uikit-window");return; }
        const auto cls=object_getClass(app);Method method=class_getInstanceMethod(cls,@selector(sendEvent:));
        if (!method) { invalidate("missing-send-event");return; }
        NSMethodSignature* signature=[app methodSignatureForSelector:@selector(sendEvent:)];
        if (!signature || signature.numberOfArguments!=3 || strcmp(signature.methodReturnType,"v")!=0
                || strcmp([signature getArgumentTypeAtIndex:0],"@")!=0 || strcmp([signature getArgumentTypeAtIndex:1],":")!=0
                || strcmp([signature getArgumentTypeAtIndex:2],"@")!=0) { invalidate("unexpected-send-event-signature");return; }
        const auto original=method_getImplementation(method);if (!original || original==reinterpret_cast<IMP>(&intercepted)) { invalidate("unexpected-send-event-implementation");return; }
        actual.runtimeClass=cls;actual.applicationClass=QString::fromUtf8(class_getName(cls));actual.original=reinterpret_cast<SendEvent>(original);
        unsigned count=0;Method* methods=class_copyMethodList(cls,&count);bool own=false;
        for (unsigned i=0;i<count;++i) { if (method_getName(methods[i])==@selector(sendEvent:)) { own=true;break; } }std::free(methods);
        if (own) {
            const auto replaced=method_setImplementation(method,reinterpret_cast<IMP>(&intercepted));
            if (replaced!=original) { if (replaced) { actual.original=reinterpret_cast<SendEvent>(replaced); }invalidate("send-event-installation-race"); }
        } else if (!class_addMethod(cls,@selector(sendEvent:),reinterpret_cast<IMP>(&intercepted),method_getTypeEncoding(method))) {
            invalidate("send-event-add-failed");return;
        }
        actual.installed=true;actual.installation=clock(actual);
        if (!methodUnchanged()) { invalidate("send-event-replaced"); }
    } @catch (NSException*) { invalidate("installation-exception"); } } catch (...) { invalidate("installation-exception"); }
}
inline bool command(const QVariantMap& query) {
    if (QJsonObject::fromVariantMap(query).value("action")!=QJsonValue("feature-ios-uikit-input")) { return false; }
    auto original=query;original["action"]="feature-ios-tablet-sources";return overte::e2e::tablet_sources::command(original);
}
inline QVariantMap observe(const QVariantMap& query) {
    if (!enabled() || !mainThread() || !command(query)) { return {}; }auto& actual=state();
    if (!methodUnchanged()) { invalidate("send-event-replaced-or-uninstalled"); }const auto before=clock(actual);sweep();
    QVariantList objects,targets,contacts,pending;
    for (const auto& row:actual.objects) { objects.push_back(QVariantMap{{"id",row->id},{"kind",row->kind},{"born",row->born},
        {"expired",row->expired.isEmpty() ? QVariant() : QVariant(row->expired)},{"alive",static_cast<bool>(row->object!=nil)}}); }
    for (const auto& row:actual.targets) { targets.push_back(QVariantMap{{"view",row.object},{"identity",row.identity},{"bound",row.clock}}); }
    for (const auto& row:actual.contacts) { contacts.push_back(QVariantMap{{"id",row.id},{"kind",row.kind},{"object",row.object},
        {"target",row.target.isEmpty() ? QVariant() : QVariant(row.target)},{"window",row.window.isEmpty() ? QVariant() : QVariant(row.window)},
        {"source",row.source.isEmpty() ? QVariant() : QVariant(row.source)},{"began",row.began},{"ended",row.ended.isEmpty() ? QVariant() : QVariant(row.ended)},
        {"phase",row.phase},{"active",row.active}}); }
    for (const auto entry:actual.pending) { pending.push_back(static_cast<qulonglong>(entry)); }
    if (actual.sequence>=9007199254740991ULL) { invalidate("query-capacity");return {}; }
    QVariantMap packet{{"iosUIKitInputVersion",1},{"commandId",query.value("commandId")},{"runId",query.value("runId")},{"fixtureUrl",query.value("fixtureUrl")},
        {"instance",actual.instance},{"sequence",static_cast<qulonglong>(++actual.sequence)},{"processId",QCoreApplication::applicationPid()},
        {"clockDomain","native-main-ios-uikit-input"},{"clockBefore",before},{"clockAfter",clock(actual)},
        {"complete",actual.complete},{"installed",actual.installed},{"applicationClass",actual.applicationClass},
        {"installation",actual.installation.isEmpty() ? QVariant() : QVariant(actual.installation)},{"failure",actual.failure.isEmpty() ? QVariant() : QVariant(actual.failure)},
        {"dispatchSequence",static_cast<qulonglong>(actual.dispatchSequence)},{"pendingDispatches",pending},
        {"objects",objects},{"targets",targets},{"contacts",contacts},{"dispatches",actual.dispatches}};
    if (QJsonDocument(QJsonObject::fromVariantMap(packet)).toJson(QJsonDocument::Compact).size()>2097152) { invalidate("packet-capacity");return {}; }return packet;
}
} // namespace overte::ios::uikit_input
#endif
