// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE) && (defined(Q_OS_ANDROID) || defined(OVERTE_PICO_SETUP))
#include "SnapshotReviewObservation.h"
#include "../../../android/common/snapshot/src/NativeSnapshotAdapter.h"
#include <QPointer>

namespace overte::e2e {
// Current ordinary QML -> Android backend -> actual native adapter association.
// A missing current page is not evidence that an earlier QObject has died.
inline QVariantMap picoSnapshotExportLease(QQuickItem* root,QQuickWindow* window) {
    if(!QCoreApplication::instance() || QThread::currentThread()!=QCoreApplication::instance()->thread()
            || !QCoreApplication::arguments().contains("--testScript") || !root || !window
            || root->thread()!=QThread::currentThread() || window->thread()!=root->thread() || root->window()!=window) {return {};}
    QQuickItem* page=nullptr;NativeSnapshotAdapter* native=nullptr;QObject* platform=nullptr;bool invalid=false;int count=0;
    std::function<void(QQuickItem*,int)> walk=[&](QQuickItem* item,int depth) {
        if(!item || invalid) {return;}
        if(++count>4096 || depth>128 || item->thread()!=QThread::currentThread()) {invalid=true;return;}
        if(item->objectName()=="snapshotReview") {
            if(page || snapshotReviewComponent(item).isEmpty()) {invalid=true;return;}page=item;
        }
        for(auto child:item->childItems()) {walk(child,depth+1);}
    };
    walk(root,0);if(invalid) {return {};}
    if(!page) {return {{"present",false}};}
    if(page->window()!=window) {return {};}
    count=0;
    std::function<void(QObject*,int)> children=[&](QObject* item,int depth) {
        if(!item || invalid) {return;}
        if(++count>4096 || depth>128 || item->thread()!=QThread::currentThread()) {invalid=true;return;}
        if(snapshotReviewId(item,"platform")) {if(platform && platform!=item) {invalid=true;return;}platform=item;}
        if(auto adapter=qobject_cast<NativeSnapshotAdapter*>(item)) {if(native && native!=adapter) {invalid=true;return;}native=adapter;}
        for(auto child:item->children()) {children(child,depth+1);}
    };
    children(page,0);if(invalid || !platform || !native) {return {};}
    const auto backend=platform->property("backend").value<QObject*>();
    if(!backend || backend->thread()!=QThread::currentThread()) {return {};}
    int matches=0,depth=0;for(auto object=static_cast<QObject*>(native);object;object=object->parent()) {
        if(++depth>128 || object->thread()!=QThread::currentThread()) {return {};}if(object==backend) {++matches;}
    }
    if(matches!=1 || !snapshotReviewId(native,"nativeAdapter")) {return {};}
    const auto lease=native->featureOriginalLease();if(lease.isEmpty()) {return {};}
    return {{"present",true},{"componentUrl",snapshotReviewComponent(page)},{"native",lease}};
}
} // namespace overte::e2e
#endif
