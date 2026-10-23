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
class Resource;
class ResourceCache:public QObject {
public:
 inline static int completed{0};
 static void requestCompleted(const QWeakPointer<Resource>&){++completed;}
 static void attemptRequest(const QSharedPointer<Resource>&);
 void addUnusedResource(const QSharedPointer<Resource>&){qFatal("Cache retention is outside the uncached Resource qualification");}
 void removeResource(const QUrl&,size_t,qint64){qFatal("Cache removal is outside the uncached Resource qualification");}
 void resetTotalResourceCounter(){qFatal("Cache counter reset is outside the uncached Resource qualification");}
 QReadWriteLock _resourcesLock;QHash<QUrl,QHash<size_t,QWeakPointer<Resource>>> _resources;
};
