// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
// Declared uncached scheduling/index endpoints; no ModelCache or cache receipt.
#include <QObject>
#include <QReadWriteLock>
#include <QHash>
#include <QUrl>
#include <QSharedPointer>
#include <QWeakPointer>
#include <QMap>
#include <atomic>
class Resource;
class ResourceCache:public QObject {
#if defined(ASSETS_ORIGINAL_MODEL_CACHE)
 Q_OBJECT
#endif
public:
 inline static int completed{0};
 static void requestCompleted(const QWeakPointer<Resource>&){++completed;}
 static void attemptRequest(const QSharedPointer<Resource>&);
 void addUnusedResource(const QSharedPointer<Resource>&){qFatal("Cache retention is outside the uncached Resource qualification");}
#if defined(ASSETS_ORIGINAL_MODEL_CACHE)
 QSharedPointer<Resource> getResource(const QUrl&,const QUrl&,void*,size_t);
 virtual QSharedPointer<Resource> createResource(const QUrl&)=0;
 virtual QSharedPointer<Resource> createResourceCopy(const QSharedPointer<Resource>&)=0;
 void removeUnusedResource(const QSharedPointer<Resource>&);
 void removeResource(const QUrl&,size_t,qint64);
 void resetTotalResourceCounter();
 void resetUnusedResourceCounter(){qFatal("Unused LRU accounting is outside this failed-resource join");}
 void updateTotalSize(const qint64&);
 QHash<QUrl, QMultiHash<size_t, QWeakPointer<Resource>>> _resources;
 QReadWriteLock _resourcesLock { QReadWriteLock::Recursive };
 std::atomic<size_t> _numTotalResources { 0 };
 std::atomic<qint64> _totalResourcesSize { 0 };
 QMap<int, QSharedPointer<Resource>> _unusedResources;
 QReadWriteLock _unusedResourcesLock { QReadWriteLock::Recursive };
 std::atomic<qint64> _unusedResourcesSize { 0 };
signals:
 void dirty();
#else
 void removeResource(const QUrl&,size_t,qint64){qFatal("Cache removal is outside the uncached Resource qualification");}
 void resetTotalResourceCounter(){qFatal("Cache counter reset is outside the uncached Resource qualification");}
 QReadWriteLock _resourcesLock;QHash<QUrl,QHash<size_t,QWeakPointer<Resource>>> _resources;
#endif
};
