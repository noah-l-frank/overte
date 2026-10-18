// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QNetworkReply>
#include <QTcpServer>
#include <QTcpSocket>
#include <QElapsedTimer>

// Android evaluation is an explicit output observer; the fetch, redirect,
// native descriptor consent, Qt reply cancellation and JNI remain production.
static void runInlineScriptCancellationTests(JNIEnv* env,jclass boundary,const QString& backendPath) {
    QQmlEngine engine; engine.addImportPath(QFileInfo(backendPath).absoluteDir().absoluteFilePath("../.."));
    QQmlFileSelector selector(&engine); selector.setExtraSelectors({"android"});
    QQmlComponent component(&engine);
    component.setData("import QtQuick 2.7\nimport controls 1.0 as Controls\nControls.EmbeddedWebView { width: 100; height: 100; url: authored; scriptUrl: approvedScript }",QUrl()); assert(component.isReady());
    auto spinUntil=[](auto predicate) { QElapsedTimer timer;timer.start();while(!predicate() && timer.elapsed()<5000) QCoreApplication::processEvents(QEventLoop::AllEvents,10);assert(predicate()); };
    auto evaluations=[&] { return env->GetStaticIntField(boundary,env->GetStaticFieldID(boundary,"evaluations","I")); };
    for(bool redirectAndRevoke:{false,true}) {
        QTcpServer server;assert(server.listen(QHostAddress::LocalHost));
        const QString script="http://127.0.0.1:"+QString::number(server.serverPort())+"/approved.js";
        const QString source="data:text/html,<p>script cancellation";
        QQmlContext context(engine.rootContext()); overte::web::InlineHtmlDocumentOwner owner;
        const auto descriptor=owner.issue(&context,"script-owner",source,script);
        context.setContextProperty("nativeInlineHtmlDocument",QVariant::fromValue(descriptor));
        context.setContextProperty("nativeWebSourceIdentity","script-owner");
        context.setContextProperty("authored",source);context.setContextProperty("approvedScript",script);
        std::unique_ptr<QObject> root(component.create(&context));assert(root);QCoreApplication::processEvents();
        auto* view=root->findChild<NativeWebViewItem*>();assert(view && view->generation());
        auto grant=view->generation();const auto url=descriptor.transportURL();view->acceptPage(grant,1,url);
        const auto before=evaluations();view->acceptState(grant,1,url,false,false,false,true,0);
        spinUntil([&]{return server.hasPendingConnections();});
        QPointer<QTcpSocket> socket=server.nextPendingConnection();assert(socket);spinUntil([&]{return socket->bytesAvailable()>0;});socket->readAll();
        if(redirectAndRevoke) {
            socket->write("HTTP/1.1 302 Found\r\nLocation: /delayed.js\r\nContent-Length: 0\r\nConnection: close\r\n\r\n");socket->flush();socket->disconnectFromHost();
            spinUntil([&]{return server.hasPendingConnections();});socket=server.nextPendingConnection();assert(socket);
            spinUntil([&]{return socket->bytesAvailable()>0;});socket->readAll();
        }
        QPointer<QNetworkReply> pending;
        for(auto* reply:view->findChildren<QNetworkReply*>()) if(!reply->isFinished()) pending=reply;
        assert(pending);assert(pending->url().path()==(redirectAndRevoke?"/delayed.js":"/approved.js"));
        bool finished=false;QNetworkReply::NetworkError failure=QNetworkReply::NoError;
        QObject::connect(pending,&QNetworkReply::finished,&engine,[&]{finished=true;failure=pending->error();});
        if(redirectAndRevoke) owner.revoke();else view->setScriptUrl(script+"#unapproved-change");
        spinUntil([&]{return finished;});assert(failure==QNetworkReply::OperationCanceledError);assert(!view->generation());
        if(socket && socket->state()==QAbstractSocket::ConnectedState) {
            const QByteArray body="window.staleOwnerScriptExecuted=true;";
            socket->write("HTTP/1.1 200 OK\r\nContent-Type: application/javascript\r\nContent-Length: "+QByteArray::number(body.size())+"\r\nConnection: close\r\n\r\n"+body);socket->flush();socket->disconnectFromHost();
        }
        QCoreApplication::processEvents();assert(evaluations()==before);assert(!env->ExceptionCheck());
    }
    puts("PASS: actual Qt HTTP script fetch and redirect are aborted by exact script-tuple change or owner revoke; delayed old script cannot reach JNI evaluation");
}
