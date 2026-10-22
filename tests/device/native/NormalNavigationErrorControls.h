// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include <OffscreenUi.h>
#include <QCryptographicHash>
#include <QJsonObject>
#include <QJsonDocument>
#include <QQuickItem>
#include <cmath>

namespace overte::e2e {
inline QString navigationErrorControlId(QQuickItem* item) {
    return OffscreenUi::featureNavigationDialogControl(item).value("id").toString();
}
inline void appendNavigationErrorControl(QJsonObject& row,QQuickItem* item) {
    const auto original=OffscreenUi::featureNavigationDialogControl(item);
    for (auto it=original.cbegin();it!=original.cend();++it) { row.insert(it.key(),QJsonValue::fromVariant(it.value())); }
}
inline QString navigationErrorControlSource(QQuickItem* item) {
    QJsonObject original;appendNavigationErrorControl(original,item);
    if (!item || !item->window() || original.isEmpty()) { return {}; }
    const auto point=item->mapToScene(QPointF(item->width()/2,item->height()/2));
    if (!std::isfinite(point.x()) || !std::isfinite(point.y()) || !std::isfinite(item->width()) || !std::isfinite(item->height())) { return {}; }
    original["x"]=point.x();original["y"]=point.y();original["width"]=item->width();original["height"]=item->height();
    original["focused"]=item->hasActiveFocus();
    return QString::fromLatin1(QCryptographicHash::hash(QJsonDocument(original).toJson(QJsonDocument::Compact),QCryptographicHash::Sha256).toHex());
}
} // namespace overte::e2e
#endif
