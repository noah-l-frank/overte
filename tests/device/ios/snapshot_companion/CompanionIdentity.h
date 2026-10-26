// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#import <UIKit/UIKit.h>

// Dedicated standalone target only. No expected identity or path is accepted.
@interface OVTSnapshotCompanionIdentity : NSObject
+ (instancetype)shared;
- (NSDictionary*)observe:(NSDictionary*)query;
- (BOOL)persist:(NSDictionary*)packet action:(NSString*)action;
#if defined(OVT_SNAPSHOT_SHARE_ARCHIVE)
// Share Archive only: closes this original source's actual retained reader.
// No paths, expected identities or desired close results are accepted.
- (NSDictionary*)sealArchiveAdmission:(NSString*)nonce;
- (NSDictionary*)archiveAdmissionSealOriginal;
- (NSData*)archiveAdmissionSealBytes;
- (BOOL)archiveAdmissionSealReady;
#endif
@end

@interface OVTSnapshotCompanionIdentityPanel : UIStackView
- (instancetype)init;
@end
