// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCryptographicHash>
#include <QDateTime>
#include <QUrl>
#include <QUuid>
#include <QVariantMap>

namespace overte::e2e {
// Immutable metadata for the actual GeometryReader input. No desired entity
// URL, mapping state or renderer expectation enters this record. Bytes are
// hashed before the processed HFM is published; no body buffer is retained.
class GeometryInputOriginal {
public:
    GeometryInputOriginal(const QUrl& source,const QByteArray& bytes) :
        _instance(QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')),
        _source(QString::fromLatin1(QCryptographicHash::hash(source.toString().toUtf8(),QCryptographicHash::Sha256).toHex())),
        _body(QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex())),
        _bytes(bytes.size()),_recorded(QDateTime::currentMSecsSinceEpoch()),_valid(source.isValid() && !source.isEmpty() && !bytes.isEmpty()) {}
    QVariantMap snapshot() const {
        if (!_valid) { return {}; }
        return {{"geometryInputVersion",1},{"instance",_instance},{"sourceSha256",_source},
            {"originalSha256",_body},{"originalBytes",_bytes},{"recordedEpochMs",_recorded}};
    }
private:
    const QString _instance,_source,_body;
    const qint64 _bytes,_recorded;
    const bool _valid;
};
} // namespace overte::e2e
#endif
