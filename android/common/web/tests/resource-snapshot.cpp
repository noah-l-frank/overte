// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "NativeResourceMapping.h"
#include <QCoreApplication>
#include <QTemporaryDir>
#include <cassert>
#include <thread>
using namespace overte::android::web;
int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    NativeResourceSource source;
    source.creation = 7; source.grant = 11; source.revision = 5;
    source.inlineURL = QUrl("http://token.overte-inline.invalid/index.html#original");
    source.bytes = QByteArray::fromHex("003c803eff"); source.charset = "windows-1252";
    NativeResourceState state(source);
    assert(!state.begin(8,11,1,source.inlineURL)); assert(!state.begin(7,12,1,source.inlineURL));
    assert(!state.begin(7,11,0,source.inlineURL));
    auto load = state.begin(7,11,1,source.inlineURL); assert(load);
    auto get = state.response(7,11,load,1,source.inlineURL,true,"GET");
    assert(get.action == NativeResourceResponse::Local && get.bytes == source.bytes);
    assert(get.charset == "windows-1252" && get.mime == "text/html");
    auto head = state.response(7,11,load,1,source.inlineURL,true,"HEAD");
    assert(head.action == NativeResourceResponse::Local && head.bytes.isEmpty());
    for (auto url : {"http://other.overte-inline.invalid/index.html", "http://token.overte-inline.invalid/index.html?x", "http://token.overte-inline.invalid/other",
                     "http://token.overte-inline.invalid:80/index.html", "http://token.overte-inline.invalid./index.html", "http://user@token.overte-inline.invalid/index.html",
                     "https://token.overte-inline.invalid/index.html", "http://overte-inline.invalid/", "http://token.overte-inline.invalid/index.html/"}) {
        assert(state.response(7,11,load,1,QUrl(url),true,"GET").action == NativeResourceResponse::Denied);
    }
    assert(state.response(7,11,load,1,source.inlineURL,false,"GET").action == NativeResourceResponse::Denied);
    assert(state.response(7,11,load,1,source.inlineURL,true,"POST").action == NativeResourceResponse::Denied);
    assert(state.response(8,11,load,1,source.inlineURL,true,"GET").action == NativeResourceResponse::Denied);
    assert(state.response(7,12,load,1,source.inlineURL,true,"GET").action == NativeResourceResponse::Denied);
    assert(state.response(7,11,load,2,source.inlineURL,true,"GET").action == NativeResourceResponse::Denied);
    assert(state.response(7,11,load,1,QUrl("https://ordinary.test/"),false,"POST").action == NativeResourceResponse::Network);
    assert(state.response(7,11,load,1,QUrl("file:///private"),true,"GET").action == NativeResourceResponse::Denied);
    auto next = state.begin(7,11,2,source.inlineURL); assert(next > load);
    assert(!state.current(7,11,load,1)); assert(state.current(7,11,next,2));
    NativeResourceSource empty = source; empty.bytes.clear(); empty.valid = std::make_shared<std::atomic<bool>>(true);
    NativeResourceState emptyState(empty); auto emptyLoad = emptyState.begin(7,11,1,source.inlineURL);
    auto emptyResponse = emptyState.response(7,11,emptyLoad,1,source.inlineURL,true,"GET");
    assert(emptyResponse.action == NativeResourceResponse::Local && emptyResponse.bytes.isEmpty());
    // Real IO thread uses copied data only; revoke atomically denies later reads.
    std::thread io([&] {
        for (int i=0;i<1000;++i) {
            auto response = state.response(7,11,next,2,source.inlineURL,true,"GET");
            assert(response.action == NativeResourceResponse::Denied || response.bytes == source.bytes);
        }
    });
    state.revoke(); io.join(); assert(!state.current(7,11,next,2));
    assert(state.response(7,11,next,2,source.inlineURL,true,"GET").action == NativeResourceResponse::Denied);
    assert(emptyState.current(7,11,emptyLoad,1)); // Other view remains live.
    QTemporaryDir root; QFile file(root.filePath("empty.html")); assert(file.open(QFile::WriteOnly)); file.close();
    NativeResourceSource packaged; packaged.creation=3; packaged.grant=4; packaged.mapping=NativeResourceMapping(root.path(),99);
    NativeResourceState packagedState(packaged); const auto url = packaged.mapping.toBrowser(QUrl::fromLocalFile(file.fileName()));
    auto packagedLoad=packagedState.begin(3,4,1,url); assert(packagedLoad);
    auto packagedResponse=packagedState.response(3,4,packagedLoad,1,url,true,"GET");
    assert(packagedResponse.action == NativeResourceResponse::Local && packagedResponse.bytes.isEmpty());
    assert(packagedState.response(3,4,packagedLoad,1,QUrl("https://overte-embedded.invalid/98/empty.html"),true,"GET").action == NativeResourceResponse::Denied);
    puts("PASS: native exact inline bytes/charset and GET/HEAD, empty/deny distinction, reserved negatives, atomic revoke, page/view/creation leases, packaged empty file");
}
