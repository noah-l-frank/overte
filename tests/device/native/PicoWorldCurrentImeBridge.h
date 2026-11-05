// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "PicoWorldCurrentInputBridge.h"
namespace overte::e2e {
inline bool picoWorldCurrentImeCommand(const QVariantMap& input) {
    const QSet<QString> expected{"schemaVersion","commandId","action","runId","fixtureUrl","operation","ownerToken",
        "documentNonce","focusNonce","control","text"};
    const auto keys=input.keys();if(QSet<QString>(keys.begin(),keys.end())!=expected)return false;
    // Never allow QVariant arrays,byte arrays or converting custom values to
    // become IDs/text before admission or consume an original nonce.
    for(const auto& name:expected)if(name!="schemaVersion" && input.value(name).userType()!=QMetaType::QString)return false;
    const auto schemaType=input.value("schemaVersion").userType();
    if(schemaType!=QMetaType::Int && schemaType!=QMetaType::UInt && schemaType!=QMetaType::LongLong
        && schemaType!=QMetaType::ULongLong && schemaType!=QMetaType::Double && schemaType!=QMetaType::Float)return false;
    const auto object=QJsonObject::fromVariantMap(input);
    if(!object.value("schemaVersion").isDouble() || object.value("schemaVersion").toDouble()!=1
        || input.value("operation").toString()!="commit-current-text")return false;
    const auto nonce=QRegularExpression("\\A[0-9a-f]{32}\\z");
    const auto document=input.value("documentNonce").toString(),focus=input.value("focusNonce").toString(),id=input.value("commandId").toString();
    if(!nonce.match(document).hasMatch() || !nonce.match(focus).hasMatch() || document==id || focus==id || focus==document
        || !QStringList{"text","foreign"}.contains(input.value("control").toString()))return false;
    const auto text=input.value("text").toString();if(text.size()>512)return false;
    for(int at=0;at<text.size();++at) {
        const auto c=text.at(at);const auto unit=c.unicode();
        if(unit<32 || unit==127 || (unit>=0xE000 && unit<=0xE05E) || c.isLowSurrogate())return false;
        if(c.isHighSurrogate() && (++at>=text.size() || !text.at(at).isLowSurrogate()))return false;
    }
    auto base=input;for(const auto& key:{"documentNonce","focusNonce","control","text"})base.remove(key);
    base.insert("operation","observe-current-document");
    return picoWorldCurrentDocumentCommand(base)
        && QJsonDocument::fromVariant(input).toJson(QJsonDocument::Compact).size()<=4096;
}
Q_DECL_EXPORT PicoCurrentAnchor picoCurrentImeAnchor(const QVariantMap& command);
struct PicoCurrentImeProvider {
    std::function<QVariantMap(const QVariantMap&,PicoCurrentAnchor)> commit;
    explicit operator bool()const{return bool(commit);}
    QVariantMap operator()(const QVariantMap& command,PicoCurrentAnchor anchor)const{
        return commit ? commit(command,std::move(anchor)) : QVariantMap();
    }
};
inline const char* picoCurrentImeProperty(){return "_overteE2EPicoWorldCurrentImeProviderV1";}
}
Q_DECLARE_METATYPE(overte::e2e::PicoCurrentImeProvider)
#endif
