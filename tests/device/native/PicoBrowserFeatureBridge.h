// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Closed owner/lease protocol reused from fixed Phone 5527d540e99cc6dba4204a5e904a854e6e1cd2b4.
// Actuation uses the original Pico surface provider, not the Phone JNI actuator.
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "PicoBrowserInputBridge.h"
#include <cmath>
namespace overte::e2e {
inline bool picoBrowserCommand(const QVariantMap& input) {
    const auto object=QJsonObject::fromVariantMap(input);
    const bool tablet=object.value("action")==QJsonValue("pico-tablet-web");
    const bool reference=object.value("action")==QJsonValue("pico-web-reference");
    const auto operation=object.value("operation").toString();
    QSet<QString> keys{"schemaVersion","commandId","action","runId","fixtureUrl","operation","ownerToken"};
    if (reference) { keys.insert("surface"); }
    if (operation=="input" || operation=="measure") { keys.unite({"handle","creation","grant","page","control"}); }
    if (operation=="input") { keys.insert("text"); }
    const auto actual=object.keys();
    if (QSet<QString>(actual.begin(),actual.end())!=keys || (object.value("action")!=QJsonValue("pico-world-web") && !reference && !tablet)
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(object.value("ownerToken").toString()).hasMatch()
            || !QStringList{"reserve","observe","measure","input","retire","arm-held","deliver-held","cancel-held"}.contains(operation)) { return false; }
    if (!tablet && QStringList{"arm-held","deliver-held","cancel-held"}.contains(operation)) { return false; }
    if (reference && !QStringList{"world","tablet"}.contains(object.value("surface").toString())) { return false; }
    auto base=input;base.remove("surface");
    for (const auto& key:QStringList{"operation","ownerToken","handle","creation","grant","page","control","text"}) { base.remove(key); }
    base.insert("action","feature-web-runtime-observe");
    if (!webRuntimeCommand(base)) { return false; }
    if (operation!="input" && operation!="measure") { return true; }
    if (!QRegularExpression("\\A[1-9][0-9]{0,18}\\z").match(object.value("handle").toString()).hasMatch()
            || !QStringList{"text","bridge","reference","second","recovery","back","reload","foreign","navigate","play","pause","seekStart","seek","scroll-up","scroll-down"}.contains(object.value("control").toString())
            || (operation=="input" && (!object.value("text").isString() || object.value("text").toString().size()>512))) { return false; }
    if (reference && !QStringList{"play","pause","seekStart","seek"}.contains(object.value("control").toString())) { return false; }
    if (!reference && QStringList{"play","pause","seekStart","seek"}.contains(object.value("control").toString())) { return false; }
    for (const auto& key:QStringList{"creation","grant","page"}) {
        const auto number=object.value(key).toDouble(-1);
        if (!object.value(key).isDouble() || !std::isfinite(number) || number<1 || number>9007199254740991.0 || number!=quint64(number)) { return false; }
    }
    if (!QStringList{"text","foreign"}.contains(object.value("control").toString()) && !object.value("text").toString().isEmpty()) { return false; }
    if (object.value("text").toString().contains(QRegularExpression("[\\x00-\\x1f\\x7f]"))) { return false; }
    return true;
}
inline bool picoTabletDOMCommand(const QVariantMap& input) {
    if (input.value("action")!="feature-pico-tablet-dom-observe" || input.value("surface")!="tablet") { return false; }
    auto original=input;original.insert("action","feature-web-dom-observe");return webDOMCommand(original);
}
inline const char* picoBrowserProperty() { return "_overteE2EPicoBrowserProviderV2"; }
}
#endif
