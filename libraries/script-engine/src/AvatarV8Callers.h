// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "PlacesHttpObservation.h"
#include <QCryptographicHash>
#include <QVariant>

namespace overte::e2e {
// Resolve actual indexed V8 frame identities against the same manager's
// actually submitted module bytes. No wrapper-parent walk or expected source
// identities enter this helper. Unknown frames remain in the original stack.
struct AvatarV8Callers {
    QVariantMap stack;
    QVariantList modules;
    QStringList urls,submittedUrls;
    bool complete {false};
    static AvatarV8Callers resolve(const QVariantMap& actual,const QVariantList& submitted) {
        AvatarV8Callers result;result.stack=actual;
        for (const auto& item:submitted) { result.submittedUrls.append(item.toMap().value("url").toString()); }
        if (actual.value("emitStackVersion")!=QVariant(1) || actual.value("complete").userType()!=QMetaType::Bool
                || !actual.value("complete").toBool() || actual.value("frames").userType()!=QMetaType::QVariantList) { return result; }
        const auto frames=actual.value("frames").toList();if (frames.isEmpty() || frames.size()>32) { return result; }
        result.complete=true;
        for (int index=0;index<frames.size();++index) {
            const auto frame=frames[index].toMap(),compiled=frame.value("compiled").toMap();
            if (compiled.isEmpty() || frame.value("sourceUrlSha256")!=compiled.value("urlSha256")) { result.complete=false;return result; }
            QString matched;
            for (const auto& item:submitted) {
                const auto code=item.toMap();const auto url=code.value("url").toString();
                const auto urlHash=QString::fromLatin1(QCryptographicHash::hash(url.toUtf8(),QCryptographicHash::Sha256).toHex());
                if (urlHash!=frame.value("sourceUrlSha256").toString()) { continue; }
                if (code.value("encoding")!=compiled.value("encoding") || code.value("codeUnits")!=compiled.value("codeUnits")
                        || code.value("sha256")!=compiled.value("sha256")) { result.complete=false;return result; }
                if (!matched.isEmpty() && matched!=url) { result.complete=false;return result; }matched=url;
            }
            if (!matched.isEmpty()) {
                result.modules.append(QVariantMap{{"frame",index},{"url",matched}});result.urls.append(matched);
            }
        }
        return result;
    }
    bool has(const QString& suffix) const {
        if (!complete) { return false; }
        for (const auto& url:urls) { if (PlacesHttpObservation::installed(url,suffix)) { return true; } }return false;
    }
    bool top(const QString& suffix) const {
        if (!complete || modules.isEmpty()) { return false; }const auto first=modules.first().toMap();
        return first.value("frame").toInt()==0 && PlacesHttpObservation::installed(first.value("url").toString(),suffix);
    }
    bool hasSubmitted(const QString& suffix) const {
        for (const auto& url:submittedUrls) { if (PlacesHttpObservation::installed(url,suffix)) { return true; } }return false;
    }
    bool snapshotPreflightOpen() const {
        if (!top("/modules/request.js")) { return false; }
        int index {0};
        for (const auto& item:modules) {
            const auto module=item.toMap();if (module.value("frame").toInt()!=index++) { return false; }
            const auto url=module.value("url").toString();
            if (PlacesHttpObservation::installed(url,"/system/snapshot.js")) { return true; }
            if (!PlacesHttpObservation::installed(url,"/modules/request.js")) { return false; }
        }
        return false;
    }
    bool snapshotPreflightText() const { return top("/modules/request.js"); }
    bool snapshotCombinedKnown() const {
        if (!complete || modules.isEmpty() || modules.size()!=stack.value("frames").toList().size()) { return false; }
        int index {0};
        for (const auto& item:modules) {
            const auto module=item.toMap();const auto url=module.value("url").toString();
            if (module.value("frame").toInt()!=index++ || !(PlacesHttpObservation::installed(url,"/defaultScripts.js")
                    || PlacesHttpObservation::installed(url,"/system/snapshot.js") || PlacesHttpObservation::installed(url,"/modules/request.js")
                    || PlacesHttpObservation::installed(url,"/system/snapshot/featureSnapshotWork.js"))) { return false; }
        }
        return true;
    }
    bool snapshotCombinedWork() const { return snapshotCombinedKnown() && top("/system/snapshot/featureSnapshotWork.js"); }
    bool snapshotCombinedTimer() const {
        return snapshotCombinedKnown() && (has("/system/snapshot.js") || has("/system/snapshot/featureSnapshotWork.js"));
    }
};
// The owning observer's original mutex protects this metadata-only table.
// Exact repeated snapshots share one immutable entry; no stack is projected,
// restamped or replaced by an expected caller path.
class AvatarV8CallerTable {
public:
    QString retain(const AvatarV8Callers& actual) {
        if (!actual.complete || !_complete) { _complete=false;return {}; }
        for (const auto& item:_entries) {
            const auto row=item.toMap();
            if (row.value("callerStack")==QVariant(actual.stack) && row.value("callerModules")==QVariant(actual.modules)) {
                return row.value("id").toString();
            }
        }
        if (_entries.size()>=128) { _complete=false;return {}; }const auto id=PlacesHttpObservation::nonce();
        _entries.append(QVariantMap{{"id",id},{"callerStack",actual.stack},{"callerModules",actual.modules}});return id;
    }
    QVariantList snapshot() const { return _entries; }
    bool complete() const { return _complete; }
private:
    QVariantList _entries;bool _complete {true};
};
} // namespace overte::e2e
#endif
