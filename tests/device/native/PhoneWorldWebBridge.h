// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "PhoneWebRuntimeBridge.h"
#include <cmath>
namespace overte::e2e {
inline bool phoneWorldWebCommand(const QVariantMap& input) {
    const auto object=QJsonObject::fromVariantMap(input);
    const auto operation=object.value("operation").toString();
    QSet<QString> keys{"schemaVersion","commandId","action","runId","fixtureUrl","operation","ownerToken"};
    if (operation=="input") { keys.unite({"handle","creation","grant","page","control","text"}); }
    const auto actual=object.keys();
    if (QSet<QString>(actual.begin(),actual.end())!=keys || object.value("action")!=QJsonValue("phone-world-web")
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(object.value("ownerToken").toString()).hasMatch()
            || !QStringList{"reserve","observe","input","retire"}.contains(operation)) { return false; }
    auto base=input;
    for (const auto& key:QStringList{"operation","ownerToken","handle","creation","grant","page","control","text"}) { base.remove(key); }
    base.insert("action","feature-phone-web-runtime-observe");
    if (!phoneWebRuntimeCommand(base)) { return false; }
    if (operation!="input") { return true; }
    if (!QRegularExpression("\\A[1-9][0-9]{0,18}\\z").match(object.value("handle").toString()).hasMatch()
            || !QStringList{"text","bridge","reference","second","recovery","back","reload","foreign","navigate"}.contains(object.value("control").toString())
            || !object.value("text").isString() || object.value("text").toString().size()>512) { return false; }
    for (const auto& key:QStringList{"creation","grant","page"}) {
        const auto number=object.value(key).toDouble(-1);
        if (!object.value(key).isDouble() || !std::isfinite(number) || number<1 || number>9007199254740991.0 || number!=quint64(number)) { return false; }
    }
    if (!QStringList{"text","foreign"}.contains(object.value("control").toString()) && !object.value("text").toString().isEmpty()) { return false; }
    if (object.value("text").toString().contains(QRegularExpression("[\\x00-\\x1f\\x7f]"))) { return false; }
    return true;
}
inline const char* phoneWorldWebProperty() { return "_overteE2EPhoneWorldWebProviderV1"; }
}
#endif
