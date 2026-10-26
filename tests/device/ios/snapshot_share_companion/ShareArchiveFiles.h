// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#import <Foundation/Foundation.h>
FOUNDATION_EXPORT NSDictionary* OVTShareArchiveChunk(NSURL* root,NSDictionary* imported,NSString* nonce,NSString* offset);
@interface OVTShareArchiveRetirement : NSObject
+ (instancetype)ownerWithGroup:(NSURL*)group archive:(NSURL*)archive imported:(NSDictionary*)imported
    revisions:(NSDictionary*)revisions metadata:(NSData*)metadata intent:(NSData*)intent importedBytes:(NSData*)importedBytes;
- (BOOL)retire:(NSString*)nonce;
- (NSDictionary*)inspect:(NSString*)nonce;
@end
