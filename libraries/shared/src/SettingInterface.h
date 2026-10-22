//
//  SettingInterface.h
//
//
//  Created by Clement on 2/2/15.
//  Copyright 2015 High Fidelity, Inc.
//  Copyright 2022 Overte e.V.
//
//  Distributed under the Apache License, Version 2.0.
//  See the accompanying file LICENSE or http://www.apache.org/licenses/LICENSE-2.0.html
//

#ifndef hifi_SettingInterface_h
#define hifi_SettingInterface_h

#include <memory>
#include <QtCore/QWeakPointer>
#include <QtCore/QString>
#include <QtCore/QVariant>
#include <QLoggingCategory>
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include "../../../tests/device/native/AvatarPreferenceBarrier.h"
#include <QSharedPointer>
#endif

Q_DECLARE_LOGGING_CATEGORY(settings_interface)

namespace Setting {
    class Manager;
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
    class AvatarPreferenceMutation;
#endif

    void init();

    class Interface {
    public:
        const QString& getKey() const { return _key; }
        bool isSet() const { return _isSet; }

        virtual void setVariant(const QVariant& variant) = 0;
        virtual QVariant getVariant() = 0;

    protected:
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
        QVariantMap e2ePreferenceInterface() const;
#endif
        Interface(const QString& key) : _key(key) {}
        virtual ~Interface() = default;

        void init();
        void maybeInit() const;
        void deinit();

        void save();
        void load();

        bool _isSet = false;
        const QString _key;

    private:
        mutable bool _isInitialized = false;

        friend class Manager;
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
        friend class AvatarPreferenceMutation;
#endif
        mutable QWeakPointer<Manager> _manager;
    };
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
    // Defined in the original shared library. Every Handle and Manager uses
    // the same actual Manager member, not one inline singleton per DSO.
    class AvatarPreferenceMutation {
    public:
        explicit AvatarPreferenceMutation(Interface* handle);
        ~AvatarPreferenceMutation();
    private:
        QSharedPointer<Manager> _manager;
        std::unique_ptr<overte::e2e::AvatarPreferenceBarrier::Mutation> _mutation;
    };
#endif
}

#endif // hifi_SettingInterface_h
