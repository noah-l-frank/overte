// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "IOSSnapshotCaptureControls.h"
namespace overte::e2e {
inline QString snapshotPendingChoiceId(QQuickItem* item) {
    if (!item) {return {};}
    if (item->objectName()=="snapshotMode.option.animated") {return "snapshot.mode.animated";}
    if (item->objectName()=="snapshotMode.option.still") {return "snapshot.mode.still";}
    return {};
}
inline QJsonObject snapshotPendingChoiceObservation(QQuickItem* item) {
    const auto id=snapshotPendingChoiceId(item);if (id.isEmpty()) {return {};}
    // Popup items can be visually reparented. These readonly QML references
    // expose the actual delegate/combo/root bindings; no desired root is input.
    auto root=qobject_cast<QQuickItem*>(item->property("featureSnapshotPendingRoot").value<QObject*>());
    auto combo=qobject_cast<QQuickItem*>(item->property("featureSnapshotPendingCombo").value<QObject*>());
    if (!root || !combo || !combo->isEnabled() || snapshotExportRoot(root)!=root || snapshotExportRoot(combo)!=root
            || combo->objectName()!="snapshotMode" || !item->window() || item->window()!=combo->window()
            || !qmlContext(item) || qmlContext(item)->baseUrl()!=qmlContext(root)->baseUrl()) {return {};}
    auto popup=combo->property("popup").value<QObject*>();auto content=popup?qobject_cast<QQuickItem*>(popup->property("contentItem").value<QObject*>()):nullptr;
    if (!content || popup->property("visible")!=QVariant(true)) {return {};}
    bool member=false;for (auto ancestor=item;ancestor;ancestor=ancestor->parentItem()) {if (ancestor==content) {member=true;break;}}
    const auto captured=snapshotCaptureControlObservation(combo);const auto checked=item->property("checked");
    if (!member || captured.isEmpty() || checked.userType()!=QMetaType::Bool) {return {};}
    const bool animated=id=="snapshot.mode.animated";
    if (checked.toBool()!=(captured.value("snapshotMode").toInt()==(animated?1:0))) {return {};}
    auto comboId=combo->property("_overteE2ESnapshotPendingComboId").toString();
    if (comboId.isEmpty()) {comboId=QUuid::createUuid().toString(QUuid::WithoutBraces);combo->setProperty("_overteE2ESnapshotPendingComboId",comboId);}
    const bool ready=item->isEnabled() && !overte::ios::featureSnapshotQtInputBlocked()
        && NormalControlUi::ownsPoint(item,item->window(),item->mapToScene(QPointF(item->width()/2,item->height()/2)));
    return {{"snapshotPendingChoiceVersion",1},{"rootId",captured.value("snapshotRootId")},{"qmlSource",captured.value("snapshotQmlSource")},
        {"comboId",comboId},{"option",animated?"animated":"still"},{"selectedMode",captured.value("snapshotMode")},
        {"format",captured.value("snapshotFormat")},{"checked",checked.toBool()},{"popupOpen",true},{"inputReady",ready}};
}
inline QString snapshotPendingChoiceSource(QQuickItem* item) {
    const auto value=snapshotPendingChoiceObservation(item);
    return value.isEmpty()?QString():QString::fromUtf8(QJsonDocument(value).toJson(QJsonDocument::Compact));
}
}
#endif
