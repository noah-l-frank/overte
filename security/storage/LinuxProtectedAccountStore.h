// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "ProtectedAccountStore.h"

namespace overte { namespace security {
// Uses the user's native Secret Service. A missing or locked service never
// enables file persistence or an ephemeral substitute.
std::shared_ptr<ProtectedAccountStore> linuxProtectedAccountStore();
}}
