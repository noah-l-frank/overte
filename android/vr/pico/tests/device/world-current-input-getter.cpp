// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Whole original TSI getter; lifecycle/provider are explicit observation seams.
#include "tests/device/native/PicoWorldCurrentInputBridge.h"
#include "tests/device/native/AudioSettingsQueue.h"
#include "tests/device/native/PrivatePreviewFiles.h"
#include <QThread>
#include <QEventLoop>
#include <QTimer>
#include <QUuid>
#include <cstdio>
#include <cassert>
#include <thread>
struct TestScriptingInterface:QObject {
    struct Lifecycle {QVariantMap snapshot(){return {{"actual-lifecycle-seam",true}};}};
    QString _testResultsLocation;
    std::shared_ptr<Lifecycle> _featureLifecycle=std::make_shared<Lifecycle>();
    std::shared_ptr<overte::e2e::AudioSettingsQueue> _featurePicoCurrentInputQueue=std::make_shared<overte::e2e::AudioSettingsQueue>();
    QVariantMap featurePicoWorldCurrentInput(const QVariantMap& command);
};
#include "original-current-input-getter.inc"
void events(){QEventLoop loop;QTimer::singleShot(1,&loop,&QEventLoop::quit);loop.exec();}
int main(int argc,char**argv){
    QCoreApplication app(argc,argv);assert(argc>=2);TestScriptingInterface tsi;tsi._testResultsLocation=argv[1];int calls=0;
    overte::e2e::PicoCurrentInputProvider provider{[&](const QVariantMap& command,overte::e2e::PicoCurrentAnchor){++calls;return command;}};
    app.setProperty(overte::e2e::picoCurrentInputProperty(),QVariant::fromValue(provider));
    const auto command=[](){return QVariantMap{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
        {"action","pico-world-web"},{"operation","measure-current-ray"},{"documentNonce",QString(32,'9')},{"control","text"},{"ownerToken",QString(32,'2')},{"runId",QString(32,'1')},
        {"fixtureUrl","http://127.0.0.1/feature-fixture/v1/runs/"+QString(32,'1')+"/"}};};
#if defined(ANDROID_APP_PICO_INTERFACE)
    const auto first=command();assert(tsi.featurePicoWorldCurrentInput(first)==first && calls==1);
    auto changed=first;changed.insert("ownerToken",QString(32,'3'));assert(tsi.featurePicoWorldCurrentInput(changed).isEmpty() && calls==1);
    // Original provider return cannot bypass the immutable pre-dispatch anchor.
    provider=overte::e2e::PicoCurrentInputProvider{[&](const QVariantMap& command,overte::e2e::PicoCurrentAnchor){++calls;QThread::msleep(1550);return command;}};
    app.setProperty(overte::e2e::picoCurrentInputProperty(),QVariant::fromValue(provider));
    assert(tsi.featurePicoWorldCurrentInput(command()).isEmpty() && calls==2);
    provider=overte::e2e::PicoCurrentInputProvider{[&](const QVariantMap& command,overte::e2e::PicoCurrentAnchor){++calls;return command;}};
    app.setProperty(overte::e2e::picoCurrentInputProperty(),QVariant::fromValue(provider));
    const auto blocked=command();QVariantMap result;QElapsedTimer elapsed;elapsed.start();
    std::thread worker([&]{result=tsi.featurePicoWorldCurrentInput(blocked);});worker.join();
    assert(result.isEmpty() && elapsed.elapsed()>=900 && elapsed.elapsed()<1500 && calls==2);
    assert(!tsi._featurePicoCurrentInputQueue->settled());events();assert(tsi._featurePicoCurrentInputQueue->settled() && calls==2);
    QThread::msleep(600);assert(tsi.featurePicoWorldCurrentInput(blocked).isEmpty() && calls==2);
    puts("PASS actual TSI current-document getter clock before queue, bounded blocked worker, late provider and nonce collision");
#else
    assert(tsi.featurePicoWorldCurrentInput(command()).isEmpty() && calls==0);
    puts("PASS unchanged non-Pico unavailable current-document getter");
#endif
}
