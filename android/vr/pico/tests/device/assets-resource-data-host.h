// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
// Complete generic Resource declaration/selected bodies; uncached scheduling,
// cache index/storage and profiling remain explicit host boundaries. Generic
// Resource finished(success) never denotes parsed geometry or renderer ready.
#include <cfloat>
#include <cmath>
#include <QMetaEnum>
#include <QUrlQuery>
#include <QWriteLocker>
#include "assets-resource-cache-host.h"
#include "AssetsResource.h"
#ifndef PROFILE_ASYNC_BEGIN
#define PROFILE_ASYNC_BEGIN(...)
#define PROFILE_ASYNC_END(...)
#endif
inline void ResourceCache::attemptRequest(const QSharedPointer<Resource>& resource) {
 if(!resource){qFatal("An unowned Resource cannot be scheduled");}resource->makeRequest();
}
#include "AssetsResourceDataOriginals.inc"
class HostUncachedResource:public Resource {
public:
 explicit HostUncachedResource(const QUrl& url):Resource(url){}
 ResourceRequest* originalRequest()const{return _request;}
 bool started()const{return _startedLoading;}
};
