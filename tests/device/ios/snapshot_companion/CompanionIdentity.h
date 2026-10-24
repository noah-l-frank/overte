// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#import <UIKit/UIKit.h>

// Dedicated standalone target only. No expected identity or path is accepted.
@interface OVTSnapshotCompanionIdentity : NSObject
+ (instancetype)shared;
- (NSDictionary*)observe:(NSDictionary*)query;
- (BOOL)persist:(NSDictionary*)packet action:(NSString*)action;
@end

@interface OVTSnapshotCompanionIdentityPanel : UIStackView
- (instancetype)init;
@end
