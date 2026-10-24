// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Included in the existing owning UI host after its original initialization.
// Every requested source is captured now on the actual GUI/Handle owner;
// historical native journals are never used as the live SDK transport.
#if defined(AVATAR_ORIGINAL_MODEL_LOADER)
    const int serviceVersion=2;
#else
    const int serviceVersion=1;
#endif
    QFile inputChannel;assert(inputChannel.open(stdin,QIODevice::ReadOnly,QFileDevice::DontCloseHandle));
    bool validServiceBudget=false;const auto serviceBudgetMs=qEnvironmentVariableIntValue("OVERTE_AVATAR_PARENT_SERVICE_BUDGET_MS",&validServiceBudget);
    assert(validServiceBudget && serviceBudgetMs>0 && serviceBudgetMs<=60000);
    QSet<QString> serviceRequests;QElapsedTimer serviceClock;serviceClock.start();bool serviceClosed=false;
    while(serviceRequests.size()<512 && serviceClock.elapsed()<serviceBudgetMs) {
        pollfd ready{STDIN_FILENO,POLLIN,0};assert(::poll(&ready,1,qMax(1,serviceBudgetMs-static_cast<int>(serviceClock.elapsed())))==1);
        const auto raw=inputChannel.readLine(65537);assert(!raw.isEmpty() && raw.size()<=65536 && raw.endsWith('\n'));
        const auto request=QJsonDocument::fromJson(raw).object();assert(request.size()==4 && request.value("avatarParentServiceVersion")==QJsonValue(serviceVersion));
        const auto id=request.value("requestId").toString(),kind=request.value("kind").toString();
        assert(QRegularExpression("\\A[0-9a-f]{32}\\z").match(id).hasMatch() && !serviceRequests.contains(id));serviceRequests.insert(id);
        assert(request.value("command").isObject());const auto supplied=request.value("command").toObject();QJsonObject result;
        QCoreApplication::processEvents();renderControl.polishItems();
        if(kind=="widgets"){assert(supplied.isEmpty());result=capture();}
        else if(kind=="preferences"){result=QJsonObject::fromVariantMap(preferenceObserver.featurePicoAvatarPreferences(supplied.toVariantMap()));}
        else if(kind=="callbacks"){result=QJsonObject::fromVariantMap(preferenceObserver.featurePicoAvatarModelConnections(supplied.toVariantMap()));}
#if defined(AVATAR_ORIGINAL_MODEL_LOADER)
        else if(kind=="model"){assert(supplied.isEmpty());result=avatarOriginalModelSnapshot(nativeAvatar);}
#endif
        else if(kind=="bookmarks" || kind=="loads") {
            // Complete actual original storage/Qt-capture sources. The public
            // TSI wrappers' own birth/nonce handling remains a separate seam.
            assert(supplied.isEmpty());result=QJsonObject::fromVariantMap(kind=="bookmarks" ? nativeBookmarks.e2eBookmarkStorage() : nativeBookmarks.e2eBookmarkLoads());
        }
        else if(kind=="input") {
            const auto beforeInput=guardData();const auto observed=capture();
            result=ui.apply(root,&window,true,supplied,click,pointerAt,{});
            normalInputJournal.append(QJsonObject{{"command",supplied},{"snapshot",observed},{"reply",result},
                {"nativeBeforeInput",QJsonObject::fromVariantMap(beforeInput)}});
            if(result.value("performed").toBool()){drain();QTest::qWait(40);renderControl.polishItems();QCoreApplication::processEvents();}
        }
        else if(kind=="close") {
            assert(supplied.isEmpty());const auto actual=preferences(true);
            const auto handles=currentHandle();assert(typedOwner.originalData(originalUrlHandle,handles));
            const auto books=QJsonObject::fromVariantMap(nativeBookmarks.e2eBookmarkStorage());
            for(const auto& key:{"pathSha256","present","rawBase64","rawSha256","cacheBase64","mapSha256","bookmarks"}){
                assert(books.value(key)==originalDataBookmarks.value(key));}
            const auto connections=nativeAvatar->e2eModelConnections();assert(!connections.isEmpty());
            result=QJsonObject{{"originalPreferences",originalDataPreferences},{"restoredPreferences",actual},
                {"originalBookmarks",originalDataBookmarks},{"restoredBookmarks",books},{"modelConnections",QJsonObject::fromVariantMap(connections)},
                {"normalInputJournal",normalInputJournal},{"originalAvatarInputs",originalAvatarInputs},{"originalFavoritePreferences",originalFavoritePreferences},
                {"nativeProcessId",QCoreApplication::applicationPid()},{"originalBackendProcessId",backendProcessId}};
#if defined(AVATAR_ORIGINAL_MODEL_LOADER)
            result.insert("actualModel",avatarOriginalModelSnapshot(nativeAvatar));
            result.insert("originalInputReads",avatarOriginalByteScope.reads);result.insert("originalInputRequests",avatarOriginalByteScope.requests);
#endif
            serviceClosed=true;
        }
        else {qFatal("Unregistered original parent service request");}
        assert(!result.isEmpty());const auto reply=QJsonDocument(QJsonObject{{"avatarParentServiceVersion",serviceVersion},{"requestId",id},
            {"kind",kind},{"processId",QCoreApplication::applicationPid()},{"nativeMonotonicNs",static_cast<double>(serviceClock.nsecsElapsed())},
            {"source",result}}).toJson(QJsonDocument::Compact)+'\n';assert(reply.size()<=1024*1024);
        QTextStream stream(stdout);stream<<reply;stream.flush();
        if(serviceClosed){break;}
    }
    assert(serviceClosed);backend.closeWriteChannel();assert(backend.waitForFinished(2000));assert(backend.exitCode()==0);
    SettingsTests::stop(preferenceManager.data());return 0;
