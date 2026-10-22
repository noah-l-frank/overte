// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "IOSSnapshotExportControls.h"
#include <QCryptographicHash>

namespace overte::e2e {
inline QString snapshotCaptureControlId(QQuickItem* item) {
    if (!snapshotExportRoot(item)) {return {};}
    const QMap<QString,QString> names{{"snapshotName","snapshot.name"},{"snapshotMode","snapshot.mode"},
        {"snapshotFormat","snapshot.format"},{"snapshotCapture","snapshot.capture"},{"snapshotCancelCapture","snapshot.cancel"}};
    return names.value(item->objectName());
}
inline QJsonObject snapshotCaptureControlObservation(QQuickItem* item) {
    const auto id=snapshotCaptureControlId(item);const auto root=snapshotExportRoot(item);if (id.isEmpty() || !root) {return {};}
    auto birth=root->property("_overteE2ESnapshotExportRootId").toString();
    if (birth.isEmpty()) {birth=QUuid::createUuid().toString(QUuid::WithoutBraces);root->setProperty("_overteE2ESnapshotExportRootId",birth);}
    const auto name=root->property("featureCaptureName").toString();
    const bool owned=QRegularExpression("\\Aparity-[0-9a-f]{16}-(still-png|still-jpg|animated|panorama|cubemap)\\z").match(name).hasMatch();
    const auto mode=root->property("featureCaptureMode");const auto format=root->property("featureCaptureFormat").toString();
    const auto images=root->property("featureImageCount");
    if (mode.userType()!=QMetaType::Int || mode.toInt()<0 || mode.toInt()>3 || images.userType()!=QMetaType::Int
            || images.toInt()<0 || images.toInt()>8 || !QStringList{"png","jpg","webp"}.contains(format)) {return {};}
    const bool blocked=overte::ios::featureSnapshotQtInputBlocked();const auto window=item->window();
    const auto point=item->mapToScene(QPointF(item->width()/2,item->height()/2));
    const bool ready=window && item->isEnabled() && !blocked && NormalControlUi::ownsPoint(item,window,point);
    return {{"snapshotCaptureControlVersion",1},{"snapshotRootId",birth},{"snapshotQmlSource",qmlContext(root)->baseUrl().toString()},
        {"snapshotNameSha256",QString::fromLatin1(QCryptographicHash::hash(name.toUtf8(),QCryptographicHash::Sha256).toHex())},
        {"snapshotName",owned ? name : QString()},{"snapshotNameOwned",owned},{"snapshotMode",mode.toInt()},{"snapshotFormat",format},
        {"snapshotCapturing",root->property("capturing").toBool()},{"snapshotProcessing",root->property("processing").toBool()},
        {"snapshotSettingsLoaded",root->property("captureSettingsLoaded").toBool()},{"snapshotStatusError",root->property("statusError").toBool()},
        {"snapshotImageCount",images.toInt()},{"snapshotSystemBlocked",blocked},{"inputReady",ready}};
}
inline QString snapshotCaptureControlSource(QQuickItem* item) {
    const auto value=snapshotCaptureControlObservation(item);
    return value.isEmpty()?QString():QString::fromUtf8(QJsonDocument(value).toJson(QJsonDocument::Compact));
}
}
#endif
