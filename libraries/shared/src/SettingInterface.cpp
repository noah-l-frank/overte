//
//  SettingInterface.cpp
//  libraries/shared/src
//
//  Created by Clement on 2/2/15.
//  Copyright 2015 High Fidelity, Inc.
//  Copyright 2022 Overte e.V.
//
//  Distributed under the Apache License, Version 2.0.
//  See the accompanying file LICENSE or http://www.apache.org/licenses/LICENSE-2.0.html
//

#include "SettingInterface.h"

#include <QCoreApplication>
#include <QDebug>
#include <QFile>
#include <QThread>

#include "PathUtils.h"
#include "SettingHelpers.h"
#include "SettingManager.h"
#include "SharedLogging.h"
#include "SharedUtil.h"
#include "ThreadHelpers.h"

Q_LOGGING_CATEGORY(settings_interface, "settings.interface")

namespace Setting {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
    AvatarPreferenceMutation::AvatarPreferenceMutation(Interface* handle) {
        if(!handle || !QCoreApplication::instance() || !QCoreApplication::arguments().contains("--testScript")
                || !overte::e2e::avatarPreferenceKey(handle->_key) || !DependencyManager::isSet<Manager>()) {return;}
        _manager=DependencyManager::get<Manager>();
        if(_manager) {_mutation=std::make_unique<overte::e2e::AvatarPreferenceBarrier::Mutation>(_manager->_featureAvatarPreferencesBarrier,handle->_key);}
    }
    AvatarPreferenceMutation::~AvatarPreferenceMutation()=default;
    QVariantMap Interface::e2ePreferenceInterface() const {
        if(!overte::e2e::avatarPreferenceKey(_key) || !DependencyManager::isSet<Manager>()) {return {};}
        const auto manager=DependencyManager::get<Manager>();if(!manager || !manager->_featureAvatarPreferencesBarrier.reading()) {return {};}
        const auto original=_manager.lock();if(_isInitialized && (!original || original!=manager)) {return {};}
        return {{"key",_key},{"isSet",_isSet},{"initialized",_isInitialized},{"managerBound",bool(original)}};
    }
#endif
    // This should only run as a post-routine in the QCoreApplication destructor
    void cleanupSettingsSaveThread() {
        auto globalManager = DependencyManager::get<Manager>();
        Q_ASSERT(qApp && globalManager);

        globalManager->terminateThread();
        qCDebug(shared) << "Settings thread stopped.";
    }

    // This should only run as a pre-routine in the QCoreApplication constructor
    void setupSettingsSaveThread() {
        auto globalManager = DependencyManager::get<Manager>();
        Q_ASSERT(qApp && globalManager);

        qAddPostRoutine(cleanupSettingsSaveThread);
    }

    // Sets up the settings private instance. Should only be run once at startup.
    void init() {
        // Set settings format
        QSettings::setDefaultFormat(JSON_FORMAT);
        QSettings settings;
        qCDebug(shared) << "Settings file:" << settings.fileName();

        // Backward compatibility for old settings file
        if (settings.allKeys().isEmpty()) {
            loadOldINIFile(settings);
        }

        // Delete Interface.ini.lock file if it exists, otherwise Interface freezes.
        QString settingsLockFilename = settings.fileName() + ".lock";
        QFile settingsLockFile(settingsLockFilename);
        if (settingsLockFile.exists()) {
            bool deleted = settingsLockFile.remove();
            qCDebug(shared) << (deleted ? "Deleted" : "Failed to delete") << "settings lock file" << settingsLockFilename;
        }

        // Setup settings manager, the manager will live until the process shuts down
        DependencyManager::set<Manager>();

        // Add pre-routine to setup threading
        qAddPreRoutine(setupSettingsSaveThread);
    }

    void Interface::init() {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
        AvatarPreferenceMutation avatarMutation(this);
#endif
        if (!DependencyManager::isSet<Manager>()) {
            // WARNING: As long as we are using QSettings this should always be triggered for each Setting::Handle
            // in an assignment-client - the QSettings backing we use for this means persistence of these
            // settings from an AC (when there can be multiple terminating at same time on one machine)
            // is currently not supported
            qCWarning(settings_interface) << "Setting::Interface::init() for key" << _key << "- Manager not yet created." <<
                "Settings persistence disabled.";
        } else {
            _manager = DependencyManager::get<Manager>();
            auto manager = _manager.lock();
            if (manager) {
                // Register Handle
                manager->registerHandle(this);
                _isInitialized = true;
            } else {
                qCWarning(settings_interface) << "Settings interface used after manager destroyed";
            }

            // Load value from disk
            load();
            //qCDebug(settings_interface) << "Setting" << this->getKey() << "initialized to" << getVariant();
        }
    }

    void Interface::deinit() {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
        AvatarPreferenceMutation avatarMutation(this);
#endif
        if (_isInitialized && _manager) {
            auto manager = _manager.lock();
            if (manager) {
                // Save value to disk
                save();
                manager->removeHandle(_key);
            }
        }
    }


    void Interface::maybeInit() const {
        if (!_isInitialized) {
            //qCDebug(settings_interface) << "Initializing setting" << this->getKey();
            const_cast<Interface*>(this)->init();
        }
    }

    void Interface::save() {
        auto manager = _manager.lock();
        if (manager) {
            manager->saveSetting(this);
        }
    }

    void Interface::load() {
        auto manager = _manager.lock();
        if (manager) {
            manager->loadSetting(this);
        }
    }
}
