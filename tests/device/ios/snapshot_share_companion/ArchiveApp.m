// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#import <UIKit/UIKit.h>
#import <CommonCrypto/CommonDigest.h>
#import "ShareJournal.h"
#import "CompanionIdentity.h"
#import "ShareArchiveFiles.h"
#include <sys/stat.h>
#include <unistd.h>

@interface OVTShareArchive : UIViewController
@property(nonatomic,strong) UITextField* runField;
@property(nonatomic,strong) UILabel* status;
@property(nonatomic,strong) UITextField* queryField;
@property(nonatomic,strong) UITextField* offsetField;
@property(nonatomic,strong) NSMutableSet<NSString*>* chunkNonces;
@property(nonatomic,strong) NSDictionary* importRecord;
@property(nonatomic,strong) NSURL* outputRoot;
@end
@implementation OVTShareArchive
- (void)viewDidLoad {
    [super viewDidLoad];self.view.backgroundColor=UIColor.systemBackgroundColor;
    UIStackView* stack=[UIStackView new];stack.axis=UILayoutConstraintAxisVertical;stack.spacing=16;stack.translatesAutoresizingMaskIntoConstraints=NO;
    [self.view addSubview:stack];[NSLayoutConstraint activateConstraints:@[
        [stack.leadingAnchor constraintEqualToAnchor:self.view.safeAreaLayoutGuide.leadingAnchor constant:20],
        [stack.trailingAnchor constraintEqualToAnchor:self.view.safeAreaLayoutGuide.trailingAnchor constant:-20],
        [stack.topAnchor constraintEqualToAnchor:self.view.safeAreaLayoutGuide.topAnchor constant:20]]];
    [stack addArrangedSubview:[OVTSnapshotCompanionIdentityPanel new]];
    self.runField=[UITextField new];self.runField.borderStyle=UITextBorderStyleRoundedRect;self.runField.placeholder=@"Completed Share run identifier";
    self.runField.autocorrectionType=UITextAutocorrectionTypeNo;self.runField.autocapitalizationType=UITextAutocapitalizationTypeNone;
    self.runField.accessibilityIdentifier=@"snapshot.share.archive.run";[stack addArrangedSubview:self.runField];
    UIButton* button=[UIButton buttonWithType:UIButtonTypeSystem];[button setTitle:@"Import unchanged Share original" forState:UIControlStateNormal];
    button.accessibilityIdentifier=@"snapshot.share.archive.import";[button addTarget:self action:@selector(importOriginal) forControlEvents:UIControlEventTouchUpInside];[stack addArrangedSubview:button];
    self.chunkNonces=[NSMutableSet new];
    self.queryField=[UITextField new];self.queryField.accessibilityIdentifier=@"snapshot.share.archive.query";self.queryField.placeholder=@"Fresh unchanged original chunk nonce";
    self.offsetField=[UITextField new];self.offsetField.accessibilityIdentifier=@"snapshot.share.archive.offset";self.offsetField.placeholder=@"Original byte offset";
    for (UITextField* field in @[self.queryField,self.offsetField]) {
        field.borderStyle=UITextBorderStyleRoundedRect;field.autocorrectionType=UITextAutocorrectionTypeNo;field.autocapitalizationType=UITextAutocapitalizationTypeNone;[stack addArrangedSubview:field];
    }
    UIButton* chunk=[UIButton buttonWithType:UIButtonTypeSystem];[chunk setTitle:@"Read unchanged imported original chunk" forState:UIControlStateNormal];
    chunk.accessibilityIdentifier=@"snapshot.share.archive.chunk";[chunk addTarget:self action:@selector(readOriginalChunk) forControlEvents:UIControlEventTouchUpInside];[stack addArrangedSubview:chunk];
    self.status=[UILabel new];self.status.numberOfLines=0;self.status.accessibilityIdentifier=@"snapshot.share.archive.status";
    self.status.text=@"No original imported";[stack addArrangedSubview:self.status];
}
- (void)importOriginal {
    NSString* run=self.runField.text;NSURL* group=OVTShareGroup();
    if (!group || !OVTShareMatch(run,@"\\A[0-9a-f]{32}\\z")) {self.status.text=@"Invalid original identity";return;}
    NSURL* original=[group URLByAppendingPathComponent:[@"snapshot-share-" stringByAppendingString:run] isDirectory:YES];
    NSData* metadata=OVTShareReadMetadata([original URLByAppendingPathComponent:@"share-original.json"]);
    id record=metadata?[NSJSONSerialization JSONObjectWithData:metadata options:0 error:nil]:nil;
    if (![record isKindOfClass:NSDictionary.class] || ![record[@"iosSnapshotShareOriginalVersion"] isEqual:@2]
            || ![record[@"runId"] isEqual:run] || ![record[@"phase"] isEqual:@"complete"]
            || ![record[@"artifact"] isEqual:@"original.bytes"]) {self.status.text=@"No completed original";return;}
    BOOL finished=NO;for (NSDictionary* event in record[@"events"]) {if ([event[@"kind"] isEqual:@"finish-issued"]) {finished=YES;}}
    if (!finished) {self.status.text=@"Finish the actual Share receiver first";return;}
    struct stat groupBefore,sourceBefore;
    if (lstat(original.fileSystemRepresentation,&groupBefore)!=0 || ![OVTShareRootIdentity(groupBefore) isEqual:record[@"rootIdentity"]]
        || lstat([original URLByAppendingPathComponent:@"original.bytes"].fileSystemRepresentation,&sourceBefore)!=0
        || !S_ISREG(sourceBefore.st_mode) || sourceBefore.st_nlink!=1 || sourceBefore.st_uid!=geteuid() || (sourceBefore.st_mode&0777)!=0600
        || ![OVTShareFileRevision(sourceBefore) isEqual:record[@"artifactRevision"]]) {self.status.text=@"Original source identity changed";return;}
    NSURL* documents=[NSFileManager.defaultManager URLsForDirectory:NSDocumentDirectory inDomains:NSUserDomainMask].firstObject;
    NSURL* output=[documents URLByAppendingPathComponent:[@"snapshot-share-" stringByAppendingString:run] isDirectory:YES];
    if (mkdir(output.fileSystemRepresentation,0700)!=0) {self.status.text=@"Existing responsibility; import will not repeat";return;}
    struct stat outputBirth;if (lstat(output.fileSystemRepresentation,&outputBirth)!=0 || !OVTShareRootIdentity(outputBirth)) {self.status.text=@"Import root identity unavailable";return;}
    NSDictionary* before=OVTShareClock();
    NSDictionary* intent=@{@"iosSnapshotShareImportVersion":@2,@"runId":run,@"phase":@"issued",@"clockBefore":before,
        @"instance":OVTShareID(),@"processId":@(NSProcessInfo.processInfo.processIdentifier),@"bundleId":NSBundle.mainBundle.bundleIdentifier,
        @"clockDomain":@"native-share-archive",@"basename":record[@"basename"],@"artifactRevision":NSNull.null,
        @"archiveRootIdentity":OVTShareRootIdentity(outputBirth),@"sourceArtifactRevision":record[@"artifactRevision"],@"groupRootIdentity":record[@"rootIdentity"]};
    if (!OVTShareWrite(output,@"import-intent.json",[NSJSONSerialization dataWithJSONObject:intent options:0 error:nil])) {self.status.text=@"Import intent failed";return;}
    NSString* hash=nil,*revision=nil;NSUInteger count=0;
    BOOL copied=OVTShareCopyFileAnchored([original URLByAppendingPathComponent:@"original.bytes"],[output URLByAppendingPathComponent:@"original.bytes"],&hash,&count,&revision);
    NSData* after=OVTShareReadMetadata([original URLByAppendingPathComponent:@"share-original.json"]);
    struct stat groupAfter,sourceAfter;
    copied=copied && lstat(original.fileSystemRepresentation,&groupAfter)==0 && [OVTShareRootIdentity(groupAfter) isEqual:record[@"rootIdentity"]]
        && lstat([original URLByAppendingPathComponent:@"original.bytes"].fileSystemRepresentation,&sourceAfter)==0
        && [OVTShareFileRevision(sourceAfter) isEqual:record[@"artifactRevision"]];
    if (!copied || ![metadata isEqualToData:after] || ![record[@"sha256"] isEqual:hash] || ![record[@"byteCount"] isEqual:@(count)]
            || !OVTShareWrite(output,@"original-extension.json",metadata)) {self.status.text=@"Original changed or failed; responsibility retained";return;}
    unsigned char raw[CC_SHA256_DIGEST_LENGTH];CC_SHA256(metadata.bytes,(CC_LONG)metadata.length,raw);NSMutableString* metadataHash=[NSMutableString new];
    for (NSUInteger index=0;index<sizeof(raw);++index) {[metadataHash appendFormat:@"%02x",raw[index]];}
    NSMutableDictionary* completed=[intent mutableCopy];completed[@"phase"]=@"complete";completed[@"clockAfter"]=OVTShareClock();
    completed[@"originalMetadataSha256"]=metadataHash;completed[@"byteCount"]=@(count);completed[@"sha256"]=hash;completed[@"artifactRevision"]=revision;
    BOOL saved=OVTShareWrite(output,@"import-original.json",[NSJSONSerialization dataWithJSONObject:completed options:0 error:nil]);
    if (saved) {self.importRecord=completed;self.outputRoot=output;}
    self.status.text=saved?@"Original bytes and unchanged extension ledger exposed in Documents":@"Import result failed; responsibility retained";
}
- (void)readOriginalChunk {
    NSString* nonce=self.queryField.text;
    if (!self.importRecord || !OVTShareMatch(nonce,@"\\Aios-[a-f0-9]{32}\\z") || [self.chunkNonces containsObject:nonce] || self.chunkNonces.count>=512) {self.status.text=@"Original chunk remains unavailable";return;}
    [self.chunkNonces addObject:nonce];NSDictionary* packet=OVTShareArchiveChunk(self.outputRoot,self.importRecord,nonce,self.offsetField.text);
    NSData* bytes=packet?[NSJSONSerialization dataWithJSONObject:packet options:0 error:nil]:nil;
    NSURL* documents=[NSFileManager.defaultManager URLsForDirectory:NSDocumentDirectory inDomains:NSUserDomainMask].firstObject;
    self.status.text=OVTShareWriteChunk(documents,bytes)?@"Unchanged imported original chunk persisted":@"Original chunk remains unavailable";
}
@end
@interface OVTShareArchiveDelegate : UIResponder <UIApplicationDelegate>
@property(nonatomic,strong) UIWindow* window;
@end
@implementation OVTShareArchiveDelegate
- (BOOL)application:(UIApplication*)application didFinishLaunchingWithOptions:(NSDictionary*)options {
    self.window=[[UIWindow alloc] initWithFrame:UIScreen.mainScreen.bounds];self.window.rootViewController=[OVTShareArchive new];
    [self.window makeKeyAndVisible];return YES;
}
@end
int main(int argc,char* argv[]) {@autoreleasepool {return UIApplicationMain(argc,argv,nil,NSStringFromClass(OVTShareArchiveDelegate.class));}}
