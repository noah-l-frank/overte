// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QJsonDocument>
#include <QUrl>
#include <QVariantMap>
#include <mutex>
#include <utility>

namespace overte::e2e {
// Observe the actual code handed to main/include/require evaluation. A later
// file read or requested source URL cannot substitute for this retained input.
class CreateSourceObservation {
public:
    explicit CreateSourceObservation(QString fragment="/system/create/",QString schema="createSourcesVersion",QString exactSuffix={}) :
        _fragment(std::move(fragment)),_schema(std::move(schema)),_exactSuffix(std::move(exactSuffix)) {}
    void submitted(const QString& url,const QString& code) {
        if (!QCoreApplication::arguments().contains("--testScript")) { return; }
        const QUrl original(url);
        if (!original.path().contains(_fragment) && (_exactSuffix.isEmpty() || !original.path().endsWith(_exactSuffix))) { return; }
        std::lock_guard<std::mutex> lock(_mutex);
        if (!_complete) { return; }
        if (!original.isValid() || !original.userInfo().isEmpty() || original.hasQuery() || original.hasFragment()
                || url.size()>4096 || code.isEmpty() || code.size()>4194304 || _evaluations.size()>=64) {
            _complete=false;return;
        }
        QByteArray bytes;bytes.reserve(code.size()*2);
        for (auto character:code) { const auto unit=character.unicode();
            bytes.append(static_cast<char>(unit&0xff));bytes.append(static_cast<char>((unit>>8)&0xff)); }
        _evaluations.append(QVariantMap{{"sequence",_evaluations.size()+1},{"url",url},
            {"submittedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"encoding","utf-16le-code-units"},
            {"codeUnits",code.size()},
            {"sha256",QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex())}});
    }
    QVariantMap snapshot() const {
        std::lock_guard<std::mutex> lock(_mutex);
        return {{_schema,1},{"complete",_complete},{"evaluations",_evaluations}};
    }
private:
    mutable std::mutex _mutex;bool _complete {true};QVariantList _evaluations;
    const QString _fragment,_schema,_exactSuffix;
};
} // namespace overte::e2e
#endif
