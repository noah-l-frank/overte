// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "NormalAccountMenuControls.h"
#include <QJsonDocument>

namespace overte::e2e {
// Actual generic tablet QAction delegates. These are passive identities;
// pointer delivery remains in the existing ordinary iOS Qt input route.
inline QString viewMenuControlId(QQuickItem* item) {
    const auto source=accountMenuSource(item);
    if (!source) { return {}; }
    const auto label=item->property("text").toString();
    if (source->property("type").toInt()==2 && label=="View") { return "view.menu"; }
    if (source->property("type").toInt()!=1 || source->property("checkable").userType()!=QMetaType::Bool
            || !source->property("checkable").toBool() || source->property("checked").userType()!=QMetaType::Bool) { return {}; }
    // Menu.h: FirstPersonLookAt, LookAtCamera and SelfieCamera. In particular
    // the generic look-at camera action is labelled Third Person.
    if (label=="First Person") { return "view.first-person"; }
    if (label=="Third Person") { return "view.third-person"; }
    if (label=="Selfie") { return "view.selfie"; }
    return {};
}
inline QJsonObject viewMenuControlObservation(QQuickItem* item) {
    const auto id=viewMenuControlId(item);const auto source=accountMenuSource(item);
    if (id.isEmpty() || !source) { return {}; }
    return {{"viewMenuSourceVersion",1},{"sourceType",source->property("type").toInt()},
        {"labelSha256",QString::fromLatin1(QCryptographicHash::hash(
            item->property("text").toString().toUtf8(),QCryptographicHash::Sha256).toHex())},
        {"checked",id=="view.menu" ? QJsonValue(QJsonValue::Null) : QJsonValue(source->property("checked").toBool())}};
}
inline QString viewMenuControlSource(QQuickItem* item) {
    auto value=viewMenuControlObservation(item);const auto source=accountMenuSource(item);
    if (value.isEmpty() || !source) { return {}; }
    value["sourceIdentity"]=QString::number(reinterpret_cast<quintptr>(source),16);
    return QString::fromUtf8(QJsonDocument(value).toJson(QJsonDocument::Compact));
}
} // namespace overte::e2e
