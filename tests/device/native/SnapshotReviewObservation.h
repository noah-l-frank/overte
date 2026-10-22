// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCoreApplication>
#include <QQuickItem>
#include <QQuickWindow>
#include <QJsonObject>
#include <QQmlContext>
#include <QQmlEngine>
#include <QJSValue>
#include <QThread>
#include <QVariantMap>
#include <QUrl>
#include <functional>

namespace overte::e2e {
inline QVariant snapshotReviewVariant(QVariant value) {
    return value.userType()==qMetaTypeId<QJSValue>() ? value.value<QJSValue>().toVariant() : value;
}
inline bool snapshotReviewId(QObject* object,const QString& id) {
    int depth=0;
    for (auto context=qmlContext(object);context && ++depth<=128;context=context->parentContext()) {
        if (context->nameForObject(object)==id) { return true; }
    }
    return false;
}
inline QString snapshotReviewComponent(QQuickItem* item) {
    if (!item || item->objectName()!="snapshotReview") { return {}; }
    int depth=0;
    for (auto context=qmlContext(item);context && ++depth<=128;context=context->parentContext()) {
        const auto url=context->baseUrl();
        if (context->nameForObject(item)=="root" && (url.scheme()=="file" || url.scheme()=="qrc")
                && url.authority().isEmpty() && !url.hasQuery() && !url.hasFragment()
                && url.path().endsWith("/system/snapshot/NativeSnapshotReview.qml")) { return url.toString(); }
    }
    return {};
}
// Selected from fixed Phone 5527d540e99cc6dba4204a5e904a854e6e1cd2b4.
// Passive properties from the original review component, including a hidden
// owned review during capture. Missing/ambiguous/malformed trees are distinct
// from an observed absence. There is no QML handler or property setter here.
inline QVariantMap snapshotReviewObservation(QQuickItem* root) {
    if (!QCoreApplication::instance() || QThread::currentThread()!=QCoreApplication::instance()->thread()
            || !QCoreApplication::arguments().contains("--testScript") || !root || !root->window()) { return {}; }
    bool invalid=false;int count=0;QQuickItem* page=nullptr;QString component;
    std::function<void(QQuickItem*,int)> walk=[&](QQuickItem* item,int depth) {
        if (!item || invalid) { return; }
        if (++count>4096 || depth>128 || item->thread()!=root->thread()) { invalid=true;return; }
        if (item->objectName()=="snapshotReview") {
            const auto source=snapshotReviewComponent(item);
            if (page || source.isEmpty()) { invalid=true;return; }
            page=item;component=source;
        }
        for (auto child:item->childItems()) { walk(child,depth+1); }
    };
    walk(root,0);if (invalid) { return {}; }
    if (!page) { return {{"snapshotReviewObservationVersion",2},{"present",false},{"review",QVariant()}}; }
    if (page->window()!=root->window() || page->metaObject()->indexOfSignal("sendToScript(QVariant)")<0) { return {}; }
    QVariantMap review{{"componentUrl",component},{"visible",page->isVisible()}};
    for (const auto& name:QStringList{"capturing","processing","loggedIn","canShare","canBlast","statusError","captureSettingsLoaded"}) {
        const auto value=page->property(name.toLatin1().constData());if (value.userType()!=QMetaType::Bool) { return {}; }
        review.insert(name,value);
    }
    for (const auto& name:QStringList{"statusText","uploadPath","exportTicket"}) {
        const auto value=page->property(name.toLatin1().constData());
        if (value.userType()!=QMetaType::QString || value.toString().size()>2048) { return {}; }
        review.insert(name,value);
    }
    QObject* mode=nullptr;QObject* format=nullptr;QObject* platform=nullptr;QObject* name=nullptr;count=0;
    std::function<void(QObject*,int)> children=[&](QObject* object,int depth) {
        if (!object || invalid) { return; }
        if (++count>4096 || depth>128 || object->thread()!=root->thread()) { invalid=true;return; }
        auto find=[&](const QString& id,QObject*& result) {
            if (snapshotReviewId(object,id)) { if (result && result!=object) { invalid=true; }else { result=object; } }
        };
        find("captureMode",mode);find("captureFormat",format);find("platform",platform);find("captureName",name);
        for (auto child:object->children()) { children(child,depth+1); }
    };
    children(page,0);if (invalid || !mode || !format || !platform || !name) { return {}; }
    const auto index=mode->property("currentIndex"),total=mode->property("count"),current=format->property("currentText");
    const auto captureName=name->property("text");
    if (name->objectName()!="snapshotName" || captureName.userType()!=QMetaType::QString || captureName.toString().size()>48) { return {}; }
    review.insert("captureName",captureName);
    const auto capabilities=snapshotReviewVariant(platform->property("capabilities"));
    const auto busy=platform->property("busy"),error=platform->property("error");
    if (index.userType()!=QMetaType::Int || total.userType()!=QMetaType::Int || total.toInt()!=4
            || index.toInt()<0 || index.toInt()>3 || current.userType()!=QMetaType::QString || current.toString().size()>16
            || (capabilities.userType()!=QMetaType::QVariantList && capabilities.userType()!=QMetaType::QStringList)
            || busy.userType()!=QMetaType::Bool || error.userType()!=QMetaType::QString || error.toString().size()>256) { return {}; }
    review.insert("mode",index);review.insert("format",current);review.insert("capabilities",capabilities);
    review.insert("exportBusy",busy);review.insert("exportError",error);
    const auto images=snapshotReviewVariant(page->property("images"));
    if (images.userType()!=QMetaType::QVariantList || images.toList().size()>8) { return {}; }
    QVariantList rows;
    for (const auto& raw:images.toList()) {
        const auto row=snapshotReviewVariant(raw);
        if (row.userType()!=QMetaType::QVariantMap) { return {}; }
        const auto image=row.toMap();const auto path=image.value("localPath");
        if (path.userType()!=QMetaType::QString || path.toString().isEmpty() || path.toString().size()>2048) { return {}; }
        const auto story=image.value("story_id");
        rows.append(QVariantMap{{"path",path},{"storyPresent",story.isValid() && !story.toString().isEmpty()}});
    }
    review.insert("images",rows);
    return {{"snapshotReviewObservationVersion",2},{"present",true},{"review",review}};
}
inline QJsonObject picoSnapshotReviewObservation(QQuickItem* root,QQuickWindow* window) {
    if (!QCoreApplication::instance() || QThread::currentThread()!=QCoreApplication::instance()->thread()
            || !QCoreApplication::arguments().contains("--testScript") || !root || !window
            || root->thread()!=QCoreApplication::instance()->thread() || window->thread()!=root->thread()
            || root->window()!=window) {return {};}
    return QJsonObject::fromVariantMap(snapshotReviewObservation(root));
}
} // namespace overte::e2e
#endif
