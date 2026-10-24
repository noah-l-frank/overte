// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "PicoWorldCurrentDocumentBridge.h"
namespace overte::e2e {
inline bool picoWorldCurrentInputCommand(const QVariantMap& input){
    const auto object=QJsonObject::fromVariantMap(input);const auto keys=object.keys();
    if(QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"schemaVersion","commandId","action","runId","fixtureUrl","operation","ownerToken","documentNonce","control"}
        || !QStringList{"measure-current-ray","observe-current-focus"}.contains(object.value("operation").toString())
        || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(object.value("documentNonce").toString()).hasMatch()
        || object.value("documentNonce")==object.value("commandId")
        || !QStringList{"text","bridge","reference","second","recovery","back","reload","foreign","navigate","scroll-up","scroll-down"}.contains(object.value("control").toString())
        || (object.value("operation")==QJsonValue("observe-current-focus") && !QStringList{"text","foreign"}.contains(object.value("control").toString())))return false;
    auto base=input;base.remove("documentNonce");base.remove("control");base.insert("operation","observe-current-document");
    return picoWorldCurrentDocumentCommand(base);
}
Q_DECL_EXPORT PicoCurrentAnchor picoCurrentInputAnchor(const QVariantMap& command);
struct PicoCurrentInputProvider {
    std::function<QVariantMap(const QVariantMap&,PicoCurrentAnchor)> observe;
    explicit operator bool()const{return bool(observe);}
    QVariantMap operator()(const QVariantMap& command,PicoCurrentAnchor anchor)const{return observe ? observe(command,std::move(anchor)) : QVariantMap();}
};
inline const char* picoCurrentInputProperty(){return "_overteE2EPicoWorldCurrentInputProviderV1";}
}
Q_DECLARE_METATYPE(overte::e2e::PicoCurrentInputProvider)
#endif
