// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "NormalControlUi.h"
#include "../../../ios/snapshot/IOSSnapshotObservation.h"
#include <QFileInfo>
#include <QRegularExpression>
#include <QQmlContext>
#include <QtQml/qqml.h>

namespace overte::e2e {
inline QQuickItem* snapshotExportRoot(QQuickItem* item) {
    for (int depth=0;item && depth<128;++depth,item=item->parentItem()) {
        if (item->objectName()!="snapshotReview") {continue;}
        const auto context=qmlContext(item);if (!context || item->property("featureObservation")!=QVariant(true)) {return nullptr;}
        const auto url=context->baseUrl();
        if (!QStringList{"file","qrc"}.contains(url.scheme()) || !url.authority().isEmpty()
                || url.hasQuery() || url.hasFragment() || !url.path().endsWith("/system/snapshot/NativeSnapshotReview.qml")) {return nullptr;}
        return item;
    }
    return nullptr;
}
inline QQuickItem* snapshotExportRow(QQuickItem* item,QQuickItem* root) {
    for (int depth=0;item && item!=root && depth<128;++depth,item=item->parentItem()) {
        if (item->objectName()=="snapshotImageRow" && item->property("featureSnapshotIndex").userType()==QMetaType::Int
                && item->property("featureSnapshotIndex").toInt()>=0 && item->property("featureSnapshotIndex").toInt()<8) {return item;}
    }
    return nullptr;
}
inline QString snapshotExportControlId(QQuickItem* item) {
    const auto root=snapshotExportRoot(item);if (!root) {return {};}
    const auto name=item->objectName();
    if (name=="snapshotCancelExport") {return "snapshot.export-cancel";}
    if (name=="snapshotCancelUpload") {return "snapshot.upload-cancel";}
    const QMap<QString,QString> names{{"snapshotSave","save"},{"snapshotShare","share"},{"snapshotUpload","upload"}};
    if (!names.contains(name)) {return {};}
    const auto row=snapshotExportRow(item,root);if (!row) {return {};}
    return "snapshot."+names.value(name)+"."+QString::number(row->property("featureSnapshotIndex").toInt());
}
inline QJsonObject snapshotExportControlObservation(QQuickItem* item) {
    const auto id=snapshotExportControlId(item);const auto root=snapshotExportRoot(item);if (id.isEmpty() || !root) {return {};}
    auto birth=root->property("_overteE2ESnapshotExportRootId").toString();
    if (birth.isEmpty()) {birth=QUuid::createUuid().toString(QUuid::WithoutBraces);root->setProperty("_overteE2ESnapshotExportRootId",birth);}
    const auto row=snapshotExportRow(item,root);const auto path=row ? row->property("featureSnapshotPath").toString()
        : id=="snapshot.upload-cancel" ? root->property("uploadPath").toString() : QString();
    const auto file=QFileInfo(path).fileName();
    const bool owned=QRegularExpression("\\Aparity-[0-9a-f]{16}-(still-png|still-jpg|animated|panorama|cubemap)-snap_[0-9]{1,20}_[0-9]{1,10}\\.(png|jpg|jpeg|webp|gif)\\z").match(file).hasMatch();
    const auto window=item->window();const auto point=item->mapToScene(QPointF(item->width()/2,item->height()/2));
    const bool blocked=overte::ios::featureSnapshotQtInputBlocked();
    const bool ready=window && item->isEnabled() && !blocked && NormalControlUi::ownsPoint(item,window,point)
        && (id=="snapshot.export-cancel" || owned);
    return {{"snapshotExportControlVersion",1},{"snapshotRootId",birth},{"snapshotQmlSource",qmlContext(root)->baseUrl().toString()},
        {"snapshotRow",row ? row->property("featureSnapshotIndex").toInt() : -1},{"snapshotFileName",owned ? file : QString()},
        {"snapshotFileOwned",owned},{"snapshotExportTicket",root->property("exportTicket").toString()},
        {"snapshotCapturing",root->property("capturing").toBool()},{"snapshotProcessing",root->property("processing").toBool()},
        {"snapshotSystemBlocked",blocked},{"inputReady",ready}};
}
inline QString snapshotExportControlSource(QQuickItem* item) {
    const auto value=snapshotExportControlObservation(item);
    return value.isEmpty()?QString():QString::fromUtf8(QJsonDocument(value).toJson(QJsonDocument::Compact));
}
}
#endif
