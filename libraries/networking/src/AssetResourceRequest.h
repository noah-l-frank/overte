//
//  AssetResourceRequest.h
//  libraries/networking/src
//
//  Created by Ryan Huffman on 2015/07/23
//  Copyright 2015 High Fidelity, Inc.
//
//  Distributed under the Apache License, Version 2.0.
//  See the accompanying file LICENSE or http://www.apache.org/licenses/LICENSE-2.0.html
//

#ifndef hifi_AssetResourceRequest_h
#define hifi_AssetResourceRequest_h

#include <QUrl>

#include <PortableHighResolutionClock.h>

#include "AssetRequest.h"
#include "ResourceRequest.h"

#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
namespace overte::e2e { class AssetsRequestLifetimes; }
#endif

class AssetResourceRequest : public ResourceRequest {
    Q_OBJECT
public:
    AssetResourceRequest(
        const QUrl& url,
        const bool isObservable = true,
        const qint64 callerId = -1,
        const QString& extra = "");
    virtual ~AssetResourceRequest() override;

protected:
    virtual void doSend() override;

private slots:
    void onDownloadProgress(qint64 bytesReceived, qint64 bytesTotal);

private:
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
    // Passive weak observation of actual child requests; no lifetime mutation.
    friend class overte::e2e::AssetsRequestLifetimes;
#endif
    static bool urlIsAssetHash(const QUrl& url);

    void requestMappingForPath(const AssetUtils::AssetPath& path);
    void requestHash(const AssetUtils::AssetHash& hash);

    GetMappingRequest* _assetMappingRequest { nullptr };
    AssetRequest* _assetRequest { nullptr };

    p_high_resolution_clock::time_point _lastProgressDebug;

    int64_t _lastRecordedBytesDownloaded { 0 };
};

#endif
