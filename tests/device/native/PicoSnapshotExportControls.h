// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "SnapshotReviewObservation.h"
#include <QCryptographicHash>
#include <QHash>
#include <QJsonDocument>

// Narrow selection of fixed Phone 5527d540 / NormalSnapshotControls.h.
// These are the existing QML buttons and model paths, not new product controls.
namespace overte::e2e {
inline bool picoSnapshotExportGui(QQuickItem* item) {
    return QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript")
        && QThread::currentThread()==QCoreApplication::instance()->thread() && item && item->thread()==QThread::currentThread();
}
inline QQuickItem* picoSnapshotExportPage(QQuickItem* item) {
    if(!picoSnapshotExportGui(item)) {return nullptr;}
    int depth=0;
    for(auto parent=item;parent && ++depth<=128;parent=parent->parentItem()) {
        if(parent->thread()!=QThread::currentThread()) {return nullptr;}
        if(!snapshotReviewComponent(parent).isEmpty() && parent->metaObject()->indexOfSignal("sendToScript(QVariant)")>=0) {return parent;}
    }
    return nullptr;
}
inline QString picoSnapshotExportPath(QQuickItem* item) {
    const auto page=picoSnapshotExportPage(item);if(!page) {return {};}
    const auto context=qmlContext(item);if(!context) {return {};}
    const auto row=snapshotReviewVariant(context->contextProperty("modelData")).toMap();const auto path=row.value("localPath");
    if(path.userType()!=QMetaType::QString || path.toString().isEmpty() || path.toString().size()>2048) {return {};}
    const auto images=snapshotReviewVariant(page->property("images"));if(images.userType()!=QMetaType::QVariantList) {return {};}
    int matches=0;for(const auto& image:images.toList()) {if(snapshotReviewVariant(image).toMap().value("localPath")==path) {++matches;}}
    return matches==1 ? path.toString() : QString();
}
inline QString picoSnapshotExportControlId(QQuickItem* item) {
    const auto page=picoSnapshotExportPage(item);
    if(!page || item->metaObject()->indexOfSignal("clicked()")<0) {return {};}
    if(item->objectName()=="snapshotCancelUpload") {return "snapshot.cancel-upload";}
    const auto label=item->property("text");if(label.userType()!=QMetaType::QString) {return {};}
    if(label.toString()=="Cancel system request") {return "snapshot.cancel-export";}
    const QHash<QString,QString> actions{{"Save to device","save"},{"System share","share"},{"Upload for URL","upload"}};
    const auto path=picoSnapshotExportPath(item);
    return actions.contains(label.toString()) && !path.isEmpty() ? "snapshot."+actions.value(label.toString())+'.'
        +QString::fromLatin1(QCryptographicHash::hash(path.toUtf8(),QCryptographicHash::Sha256).toHex()) : QString();
}
inline bool picoSnapshotExportControl(const QString& id) {
    return id.startsWith("snapshot.save.") || id.startsWith("snapshot.share.") || id.startsWith("snapshot.upload.")
        || id=="snapshot.cancel-export" || id=="snapshot.cancel-upload";
}
inline void appendPicoSnapshotExportControl(QJsonObject& row,QQuickItem* item,const QString& id) {
    const auto page=picoSnapshotExportPage(item);
    if(!page || picoSnapshotExportControlId(item)!=id) {return;}
    row["profile"]="native-pico-snapshot-export-v1";row["componentUrl"]=snapshotReviewComponent(page);
    const auto path=picoSnapshotExportPath(item);
    if(id=="snapshot.cancel-export") {row["exportTicket"]=page->property("exportTicket").toString();}
    else if(id=="snapshot.cancel-upload") {row["uploadPath"]=page->property("uploadPath").toString();}
    else {row["path"]=path;}
    row["inputReady"]=item->isEnabled() && item->isVisible();
}
inline QString picoSnapshotExportControlSource(QQuickItem* item,const QString& id) {
    QJsonObject row;appendPicoSnapshotExportControl(row,item,id);
    if(row.isEmpty()) {return {};}
    const auto point=item->mapToScene(QPointF(item->width()/2,item->height()/2));row["sceneX"]=point.x();row["sceneY"]=point.y();
    return QString::fromUtf8(QJsonDocument(row).toJson(QJsonDocument::Compact));
}
} // namespace overte::e2e
#endif
