// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCryptographicHash>
#include <QMutex>
#include <QMutexLocker>
#include <QVariantMap>
namespace overte::e2e {
// A cross-thread passive snapshot. An overlapping/retired decoder is ambiguous,
// never rebound to newer expected bytes. The product decode path is unchanged.
class CreateTextureState {
public:
    void decode(const QByteArray& bytes) {
        QMutexLocker locker(&_mutex);_ambiguous|=_pending;_pending=true;++_revision;
        _sha=QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex());
        _bytes=bytes.size();_loaded=false;_failed=false;_width=_height=0;
    }
    void refresh() {
        QMutexLocker locker(&_mutex);_ambiguous|=_pending;_pending=false;++_revision;
        _sha.clear();_bytes=0;_loaded=false;_failed=false;_width=_height=0;
    }
    void resource(const QString& url,bool loaded,bool failed,int width,int height,bool ownerThread) {
        QMutexLocker locker(&_mutex);_ambiguous|=!ownerThread;++_revision;
        _url=url;_loaded=loaded;_failed=failed;_width=width;_height=height;
        if (loaded || failed) { _pending=false; }
    }
    QVariantMap read() const {
        QMutexLocker locker(&_mutex);
        return {{"complete",!_ambiguous},{"revision",_revision},{"urlSha256",_url},
            {"loaded",_loaded},{"failed",_failed},{"originalSha256",_sha},{"originalBytes",_bytes},
            {"gpuWidth",_width},{"gpuHeight",_height}};
    }
    void copyFrom(const CreateTextureState& original) {
        if (&original==this) { return; }
        // Never hold two independently ordered mutexes at once.
        const auto snapshot=original.read();QMutexLocker locker(&_mutex);
        _ambiguous=!snapshot.value("complete").toBool() || !snapshot.value("loaded").toBool();
        _revision=snapshot.value("revision").toULongLong();_url=snapshot.value("urlSha256").toString();
        _sha=snapshot.value("originalSha256").toString();_bytes=snapshot.value("originalBytes").toInt();
        _loaded=snapshot.value("loaded").toBool();_failed=snapshot.value("failed").toBool();
        _width=snapshot.value("gpuWidth").toInt();_height=snapshot.value("gpuHeight").toInt();
    }
private:
    mutable QMutex _mutex;
    quint64 _revision {0};QString _sha,_url;int _bytes {0},_width {0},_height {0};
    bool _pending {false},_ambiguous {false},_loaded {false},_failed {false};
};
}
#endif
