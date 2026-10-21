#!/usr/bin/env python3
"""Offline language-selection regressions, with disposable Git inventories."""

from copy import deepcopy
import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("trusted_codeql_selection", ROOT / "tools/repository-checks/codeql.py")
CODEQL = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(CODEQL)

# Exact deployed25 recipes remain test data after canonical26 is staged.
_BOOLEAN_RECIPE_BYTES = {'tools/repository-checks/workflows/producers/repository-checks.yml': ('15d1b9ca9d4b58831cd5f8226efcd47681dd3e8a', 'c-rk6Yi}Dj^1FWpohxb!ILfgTUvoO-a84}5?n4f2IftSs1ZtO(7_Z1J$(5~Z`rmK(+J|=ah+`W;Abrx3GedITGvwdUsgP5`HPSLun#L$4(G3|>G^U(NqM6|TLL|~`X8$8e|Hzo63jWL(y#)kK<d|xdiiAb;_6{dg+Ci5z6^dyg=O~)c=tk|xjAJ+V-JgG={V~&%Y}lqV%JsmEqt~y|UYaGzz$`(P-b3GikM=8oZL<;BgaM^7gY8<N-3m-JA$&|#dq@<uBpPQm(+NeNKA~n@5zkvKGrfER2^rGF>|l{d2`1wKs%5rP0kbo0d-PoZB|Mgb#W)dsjAKT|Tqw;VwbyD{+`Wq#m6{?Ba+pyxrJBS<6T}5irHHeLN;EsNyIBAgGG?5BB>u=q!bU7|k~F}7{k0=_X9uA&<IOihdY)3{{$eCj(1zH5NLu++a~@5k;Ou|Yk2ulz56=Mql`{msZ-u-WCE|7vGnEn@P26gXr<wLEBLr##`x=ABDdx87elb;%WT`m`Xj{gSo=_BtX_`<tc?`-KQ9P2Aq5>OfMrBUH9I%6iLL`*%65SEW65TQOK=V<r^>GJ{NTTRYO68PUns%d+;2K1#Isi!G9r%ngDJhTUW_Bz^mYS(x64;ppHil49iLw;hJev+driFG%Is$=NtgTt>waTbQOIU1mzoO(;!$CfTM>N5VV=xt~4PL$<#n1{cSQAzvlM!`l=DgKO2AajSAxP2tOQh+Ywi@n~b<{x{xH1d7pfu*Upg3;OF{(P|G^R3S7QlXi@=T_{Zc+Q7?e=vL%uF4m66XiCE8pq%e41FSTL2EbD!G&avm10ydv||#>$gA0Z?}y40aL*N=%7@T#vq;rh0Aq`B)4R)_U)?s7Ph?r3T{AwgR<LHSrmaX+oP-pzF}!<PV|(@=xpc;SQ+Wui<Vqr$PT=#SJ=4oY?yJK;iH%B=Pz9>Vp9q%#8bwBkwE|04#QA6RD`n+1W)EpV<DqSm6w}`ZdbsZf3Vmhre&lwA-uqW$pTbSaPLgdmx2d?0>y>mGJ+dfvVw-FGyog?2y9bJm#IJ%$UcJ`fY*x|oOJoIYLImz27WER8LXpDzz_y2*;<3F6WNRtjnH*sit4o_0H#3n#yu$F{}Sv)z&eTb(x^e!iL8`H8K{oRxUm8-xwZH?WFTT;Ln`Pj`mHfrV}N<xV0;|oV_ygO#a%4&KIFjKI)MG>Mf@Uqc|?y1iH?Wl)$`+5N5?Vw;U6y#pGSwU4v&6#F(m(dK0NeP%CX7hVk38iidQaNO53M!gQ0}5KPfn2^Z*Ej9T%fiDyB4!KyD_|LxvafyZ{3EsZ<n)19Z@*d<r2SXiFnT4b?#{;j2M_FVh%ORaiEnwOQvOumP&0GNJG=V@ZrF2~R~xmoyS%lb0jw>hkQ^#ZV!U370mPL6(VO6$W~42mCkXvx5Ea&IbL9pSrz@479kRyv*s|N&oyqckoNMe{y=#KN+0&`rTgN;WS68ntOJc$10*%Z_m1?*FT^4-hCEf1=5JK#3*Y{9AZxg{TmlLG1n8pUm$#r@D;*ug3=r;5v|khb~-O2dzphE6ZegtefRFXe|G(5(ER`m8N5H~pFIncwmx2j=$-u1H4yF?#q7m(|NV9U*@D1H><XdWg=kX(83Qu5O79>rSu15>XC~=bA0<tqV-n`QN3?5aocYf4@ezg65XUq%(??%qwPj1i)!f915sjpnS`N}XI2{NRdK<Mp-H&I+s*JxaYg|yXjkU}A_BFax2*1uujMan`h*xJPo9dS5lkX`!4ZGZ8>ls$|lwZs%$D^EM8}bTfjM!x05VoQ9qp~j9XMd%PxNujtHfT)hp#&&{G_&n>V4Lj`dFkxu-Jy)T(kO1Z&X5Dx3yyEoD!?a4mCW81GIno`<;$+Cx}k`2-w$%!-STmpz&!_ceZk}E%x%^BIaTYLE<)MZ8rug&%D+NDRsnsc-udE+bXob?P^&(w{rLl}FhCEHTi{n<M*B_h_0r6&G6FuAx(%D47!PftH{~YFWmK)jHx-!K;BUV>J>Ht{Lz=Hwz!mnJ3v0emcsB`cNySa?QW&7MvUio-8|vPiOuZekic(PldqzD$==CeDFntg4HJN@Bc&(LDIp@|GAJP~DYT$LFJvKL?HWJ;sF4QU_8?~WU5!k2?wTi$(BPteAHiZG(=y(E)uB^Aht}Aeh*8Q7Z@9!bi`MuH5H`u%n(w@xfOMoVz(EPu*lL$luLgmy0xNwFZ6lmP;)>%B3v#4;~cLuz}2tYW$ns|KksI9reL~5{Kdl1aev<-fbrq4B{Sdxv7;2JuAD`HAQNo-2$UufiHim7kX0dJz9&91u6ysf`}F#Z1QTkF-gX?ZWTNWVh&zSQY{!s|8DFD~7|+^-uS4*J2U-5l1K62{FvL{LqXt7f^|`~KJd*+uX4qSycL<$1sR=GT7r?Zs*L^<mKmwk_Y93$WEK^nlIVi^XR8x6^H^9c@JfuEFLJc*(Pq%1(D1-P}eFtW|Qx;Q?VD>~V0*{;QJW__11;SRAja4ldss;81ovn5kY;+u+MMnGpuQBB{T~^iQkMkdB1(S0zBabQ`kuvYUI^vOl1Aa8-S{?jeFxSs&r#H}n$WYYZ2Uers#Yn__pT@MVuOY^Z>yga)&mnwOv>me6oTSGI85JOQ7Wz)P>h_8-H2rxwV%!CYpQrxEZR;q6a@%kI_n&;2W>8Cv{!b<uM!wN+MtO`cKQ?}~WlV(glWPrD;*4i6BOjo;&1bm#v}IRwc'), 'tools/repository-checks/workflows/metadata-edits/codeql-metadata.yml': ('3b7a88765b7181a1bc7dd6f48b9b459e590055d3', 'c-rk*>vI}8693L$A+xCr<UE5PICjW7wIrqz?|HE|;MC=^E=tS@P%=mpNrOWk|NFHbGtA&2@A7?#Qx${MYIUo-fBo=p=!A<oW(v)T!Vy*&$uta!lw3SSi6D}Q1wrH;4i!o$V<bYD;duF;2>1{o$x{&$grhl?l5!T*7@m_3dcq^}_gPJ(%(n}7K72rpDOIy{9FPTJYNXfE@iFp}G>%7tyiJKz9=dxMHA;j5+zp%!DT$~eks;bD(S$S1rbGr~EQw)JxvQv(3HtaERiEY2vf0$zn+1sRn8aFwbtVOxlx0*+ElP>Z>;y*jEg*#_6r4tW%-PhBD4sGd6%D1=Y?`y)`GN>V5W|Xs9daWv&Jw|+Gz2p&_KY-Zq+CRlVX;JSQykL?4Y83=6My<tt8vz;A(W(Yrhg+e7MO)IB0K2S98<Q9aFWEtFMg(6Zlg?Kx8c4eGtS8B>p~Pi`w0#CmANIsY9@UOS_)$CMaW0>d-q!Rf_YRo60Ll}QmAEO#Nr77@7qR#WS`^`L>8RU_i(rMjH_EyM#2SA8ap+76oMcfRNp;B`{*A0Yu9VFga{WFQj>+8DewUhOAs8@YVbWwg&-_k>h0f97b)^i8CB3cl?pL%8i7L4hQ!Fysx^ah0o;-pLl9CW;j>I*6#%=b;Azr<OC$0&_I3C<N4)0Z%_Qd6;0MKJ>z~E<4_G=M!~H8)7i5y1`W2&Ivv?GcZbTy!h$RD=a6`_9K4m_{?G&s8UZ6xuYPHvVY`i0jZQnww^(%{=-Bis$FwK#mi{~pZF*J12L0<u^HUP^WsejhI(k|MUDzAaVhi}SD`U2lwP~1tS4!)ojSh-r6%gI(E{9I9U^E(wR=dn3;4aAvL1%Mk-BcM$oTaB$>S>#)?NYlVQ;1#e69i%csBCyYz$K}q1<7>Q>4RdY7&<1OyfrS|(r>hr?E?*{oLz6_SberC&l?U*oYU!KjEAH6<8<@vIcrt-sP~zC?1;t>|6oXL>DMYyRHOQyql&RF;YX>`Ro1*BP@KpJ8%2K60|G+H6Qj)4%wd`3&oW)D)%~Fv>I-5G`phRZDL;vKm6i))~v;1IAu{tCHb~e)M&5YD+uQIZ$;q()0Ei_U|m6d*yN|f-JhD%4E#k(_8%a{g^{jneIhwVLbfN^**#z#8`M|%emKD^)F-3fP(cJ~hV$N0g{co$ON;xO0=c5{YBC@^nNCRUG97(n9Vk}58iK}04PoNQ!M|LO&@s-u(XP+TVhbWwgNNTlHv$DqUn{wD<@nP4G_pXt;=9}Amcdd_3nS_xtaWd#j5h64Yia23Sb+EYI#A)o3(1{te|d=5nlfW3tp$nhFgY++zsIKO~K9lMmT5Vj~j-P32I;rYLN{nGm>{)VvfEA_j>(-*zbU%g@Xq&w`6PW!`Ne`rrt$Mp@5wLtxOwu2|ndMB4>r~Rkj#M+fxlue85AtXEKkzcgwQbGB)kNi{Q50L*jGka@;p{%n8$#R8;<<|ro*%eg3^YnE1?DFxb_W~YfbkQ9?t7n_0$yul9cmL{X3aiX&_xy5raXGBt^Z^_pNc67Tg6NEBq%%Hc`U;SFWps#!FJp&J4Z6ngZZA%4sO6#;b|yrHGe07UCfNJoD0G#@`WreR&*LXY^b8ywgc13}Z>a-M<LRcjd)yuLMuTVF3fw9c*}B#U<P6`a1;%6oZBk)b6P04?Nw<G;3Q=|Qo*SeqkGv_5t)bS#s)%!vDCCor!w4V&prvs|#C<W)Oe3Nr?Vl1l`o7@2=<dF+pTyTH)bC`ksN*OnaeF28>o?eDQCkegM_E5)GU02<SrvAm-+%WmUV4QsI#0MzNFUfnya?|T!RN;9V>-^rF5qjCFWiNW&EX*CIFb!b(D2qp@tT3IOGdgVZZw+(4y)9DY`DGh@)hr@K!+vFYm_6=kU7WRl`gz?&9H__%B0erNFzVLjbezt=1nGrJCD(;1&&jKz#)<SL>X#$ukixQP|!sArb{;;y=|z)%}YYzN+&D&oMBO74IoH2^bHOH$QBgZ=vQ6|D7`D-h=CcFuB7UeES(iv!8Me4q_KLMV-NkyzIv3-6S>m43G3cJ%xiv@kFJjl3#mk73|?Je&;&zX6Va&RlnBU!jl#X!95Af_&ltTSOL;s594VRi;-$thH&-h*eyap&%lFE<8>;jYO*McWX8>l#O0K|d<O8LY+5RPJnnHe}r-G`H(|y?a)C9xAnxOCUO0$`PhHEIS0F`~jmTiEcow474l2%(qtt#nFm0ME&R|EM?4dl1>KKnc0)Z5)?%}n&UrbGbPPnX$wop}5ShQVN|KCn)?!i3B_ZTM(>{&R5NZ&Z3m0TRBh6LRxz4O{wap=i0qB5QNSv?li{qk3ES6>cD3tX?RiYE5c4uW^~l>d?}3e}vJbeRMQAcyJIM?L_y<&LP>^kJ|SS+Y>U54)C~rFu@P@kF@yhVE-_9uu*<fA#~78DR}8t%Q+_0Y^}=c1(*!NNwy+>&2;|E_Q4e+809YZg1y6FZ*3J?h4kJ1cA&5b-b+=LOs#{gVOqIt8mBad`7m(q=#f;hBn5At(5XM6Fas`(x~vqLFqX(nxNcPYZ&M28oq(2*T(4#hkoyHFt`n^`Gv8QWJ~=<>{e3oi(R)5PJ?|I0d~L7X!<`_G*>_iYx_i|nSLxC^lq2@>*R|`~T=q5I<<j2IbTB<9okHme^Y~Vd2GzDUU07x;J5suh{OfMa!O!xQn-lV;6JBP~4THO~+*_6Ny06Qy&0?m1WzTG9Ma$LqO~`&^0Qf!AzDjV<B2oXXW$9{|!mMjk{0(|%y(h!b^WNa{Y`ED~N^mlOmZgHUY9eQUy8Z6i%m4N&ZgCG^an1L{bx9c=*3L^xK_&Hs!>DklELR;;NqOQ04%2ZgKAOzbag*OBdibzJdasE{IOE70WDoCvFrPI-&j;A6tVp`%d31O0A>bs;!gkBth{R#-i$l!J!Y+h<%`$)bEOWygOLvcy!3c;jEu;HerL#vd)7`oWZj4L*-*c=Cld`}0=02OJt_<YdE6N`o|GLcH`_BacLGNUA*6lyN>^|)cK7&^ke{uNSO!n(0L?fpVOp0osof6r>tFFH)N3*s60WK)(v;')}

def boolean_recipe_bytes(relative):
    import base64,zlib
    oid,encoded=_BOOLEAN_RECIPE_BYTES[relative]
    raw=zlib.decompress(base64.b85decode(encoded))
    if hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=oid:
        raise AssertionError('frozen Boolean recipe changed')
    return raw


def entry(sha="a", mode="100644"):
    return {"mode": mode, "type": "commit" if mode == "160000" else "blob", "sha": sha * 40}


def reviewed_tree():
    return {path: {"mode": "100644", "type": "blob", "sha": sha}
            for path, sha in CODEQL._REVIEWED_CONTROLS.items()} | {
                "tools/check.py": entry(), "browser/src/main.ts": entry(), "docs/design.md": entry(),
            }


class LanguageSelectionTests(unittest.TestCase):
    def pinned_trees(self):
        before = reviewed_tree()
        before['.github/workflows/codeql.yml']['sha'] = CODEQL._PINNED_RESULTS_WORKFLOW
        before.update({path: entry() for path in CODEQL._PYTHON_POLICY_JSONS | CODEQL._INERT_CI_JSONS})
        return before, deepcopy(before)

    def test_only_four_existing_ci_metadata_leaves_need_no_language_in_the_pinned_generation(self):
        self.assertEqual(CODEQL._INERT_CI_JSONS - {'.github/package-workflow-generations.json'}, {
            '.github/branch-cleanup.json', '.github/issue-policy.json',
            '.github/repository-health.json', '.github/dependency-releases.json'})
        for path in CODEQL._INERT_CI_JSONS:
            for event in ('pull_request', 'push'):
                before, after = self.pinned_trees()
                after[path] = entry('b')
                with self.subTest(path=path, event=event):
                    plan = CODEQL.select_languages(before, after, event=event)
                    self.assertEqual(plan['languages'], [])
                    self.assertFalse(plan['full_scan'])
                    self.assertEqual(plan['reasons'], [{'code': 'reviewed-pinned-ci-metadata', 'path': path}])
                    self.assertEqual([change['path'] for change in plan['changes']], [path])

    def test_exact_existing_generation_catalog_is_not_extracted_but_preserves_all_other_owners(self):
        catalog = '.github/package-workflow-generations.json'
        self.assertIn(catalog, CODEQL._INERT_CI_JSONS)
        for changed, expected in (({}, []), ({'tools/helper.py':entry('b')}, ['python']),
                ({'browser-client/main.ts':entry('b')}, ['javascript-typescript']),
                ({'tools/helper.py':entry('b'), 'browser-client/main.ts':entry('b')}, list(CODEQL.LANGUAGES)),
                ({'tools/repository-checks/codeql.py':entry('b')}, list(CODEQL.LANGUAGES)),
                ({'bin/unknown-input':entry('b')}, list(CODEQL.LANGUAGES)),
                ({'.github/unknown-metadata.json':entry('b')}, ['javascript-typescript'])):
            before, after = self.pinned_trees()
            before[catalog] = entry(); after[catalog] = entry('b'); after.update(changed)
            with self.subTest(changed=changed):
                plan = CODEQL.select_languages(before, after)
                self.assertEqual(plan['languages'], expected)
                self.assertIn({'code':'reviewed-pinned-ci-metadata','path':catalog}, plan['reasons']) \
                    if not plan['full_scan'] else None
        # Every immutable-inventory/control failure retains the original conservative route.
        for mutation in ('config','workflow','alias','gitlink','pack','unknown-inventory','schedule'):
            before, after = self.pinned_trees()
            before[catalog] = entry(); after[catalog] = entry('b')
            event = 'pull_request'
            if mutation == 'config': after['.github/codeql/codeql-config.yml'] = entry('c')
            elif mutation == 'workflow': after['.github/workflows/codeql.yml'] = entry('c')
            elif mutation in ('alias','gitlink'):
                before['unchanged-alias'] = after['unchanged-alias'] = entry(mode='120000' if mutation=='alias' else '160000')
            elif mutation == 'pack': before['.github/qlpack.yml'] = after['.github/qlpack.yml'] = entry()
            elif mutation == 'unknown-inventory': before = None
            else: event = 'schedule'
            with self.subTest(mutation=mutation):
                self.assertEqual(CODEQL.select_languages(before, after, event=event)['languages'], list(CODEQL.LANGUAGES))
        # A new/missing/renamed/executable JSON keeps its prior JS owner; aliases and gitlinks remain full above.
        for mutation in ('new','deleted','renamed','before-executable','after-executable'):
            before, after = self.pinned_trees(); before[catalog] = entry(); after[catalog] = entry('b')
            if mutation == 'new': del before[catalog]
            elif mutation == 'deleted': del after[catalog]
            elif mutation == 'renamed': after[catalog+'.other.json'] = after.pop(catalog)
            elif mutation == 'before-executable': before[catalog] = entry(mode='100755')
            else: after[catalog] = entry('b',mode='100755')
            with self.subTest(mutation=mutation):
                self.assertEqual(CODEQL.select_languages(before, after)['languages'], ['javascript-typescript'])

    def test_ci_metadata_mixed_changes_retain_every_existing_language_owner(self):
        for changed, expected in (
                ({'tools/helper.py'}, ['python']),
                ({'browser-client/main.ts'}, ['javascript-typescript']),
                ({'tools/helper.py', 'browser-client/main.ts'}, list(CODEQL.LANGUAGES)),
                ({'.github/android-orchestration.json'}, ['python']),
                ({'.github/test-suites.json'}, ['python']),
                ({'.github/workflows/branch-cleanup.yml'}, ['javascript-typescript']),
                ({'tools/repository-checks/workflows/producers/parent-qualification.yml'}, ['javascript-typescript']),
                ({'browser-client/package-lock.json'}, ['javascript-typescript']),
                ({'script-archive/marketplace/S3Server/package-lock.json'}, ['javascript-typescript']),
                ({'.github/unknown-metadata.json'}, ['javascript-typescript']),
                ({'tools/repository-checks/codeql.py'}, list(CODEQL.LANGUAGES)),
                ({'tools/repository-checks/check.py'}, list(CODEQL.LANGUAGES)),
                ({'bin/unknown-input'}, list(CODEQL.LANGUAGES)),
                ({'custom/qlpack.yml'}, list(CODEQL.LANGUAGES))):
            before, after = self.pinned_trees()
            for path in CODEQL._INERT_CI_JSONS | changed: after[path] = entry('b')
            with self.subTest(changed=changed):
                self.assertEqual(CODEQL.select_languages(before, after)['languages'], expected)

    def test_ci_metadata_cannot_omit_added_deleted_renamed_or_nonordinary_paths(self):
        for path in CODEQL._INERT_CI_JSONS:
            for mutation in ('addition', 'removal', 'renamed', 'before-executable', 'after-executable', 'symlink', 'gitlink'):
                before, after = self.pinned_trees()
                after[path] = entry('b')
                if mutation == 'addition': del before[path]
                elif mutation == 'removal': del after[path]
                elif mutation == 'renamed': after[path + '.other.json'] = after.pop(path)
                elif mutation == 'before-executable': before[path] = entry(mode='100755')
                else:
                    after[path] = entry('b', {'after-executable': '100755', 'symlink': '120000', 'gitlink': '160000'}[mutation])
                expected = list(CODEQL.LANGUAGES) if mutation in ('symlink', 'gitlink') else ['javascript-typescript']
                with self.subTest(path=path, mutation=mutation):
                    self.assertEqual(CODEQL.select_languages(before, after)['languages'], expected)

    def test_ci_metadata_requires_both_pinned_workflows_and_cannot_hide_pack_or_alias_inputs(self):
        for previous in (CODEQL._REVIEWED_CONTROLS['.github/workflows/codeql.yml'], CODEQL._SELECTIVE_WORKFLOW,
                         CODEQL._RESULTS_WORKFLOW, CODEQL._RETARGET_RESULTS_WORKFLOW):
            before, after = self.pinned_trees()
            for path in CODEQL._INERT_CI_JSONS: after[path] = entry('b')
            before['.github/workflows/codeql.yml']['sha'] = previous
            after['.github/workflows/codeql.yml']['sha'] = previous
            self.assertEqual(CODEQL.select_languages(before, after)['languages'], ['javascript-typescript'])
            after['.github/workflows/codeql.yml']['sha'] = CODEQL._PINNED_RESULTS_WORKFLOW
            self.assertTrue(CODEQL.select_languages(before, after)['full_scan'])
        for path in CODEQL._REVIEWED_CONTROLS:
            for side in ('before', 'after'):
                before, after = self.pinned_trees()
                after['.github/branch-cleanup.json'] = entry('b')
                (before if side == 'before' else after)[path] = entry('c')
                with self.subTest(path=path, side=side):
                    self.assertEqual(CODEQL.select_languages(before, after)['reasons'][0]['code'],
                                     'unreviewed-analysis-configuration')
        for unknown in ('.github/qlpack.yml', 'qlpack.yml', 'unchanged-alias.js', 'unchanged-submodule'):
            before, after = self.pinned_trees()
            mode = '120000' if unknown.endswith('.js') else '160000' if unknown == 'unchanged-submodule' else '100644'
            before[unknown] = after[unknown] = entry(mode=mode)
            after['.github/branch-cleanup.json'] = entry('b')
            with self.subTest(unknown=unknown):
                self.assertTrue(CODEQL.select_languages(before, after)['full_scan'])

    def test_ci_metadata_keeps_schedule_unknown_events_and_inventory_failures_conservative(self):
        before, after = self.pinned_trees()
        after['.github/branch-cleanup.json'] = entry('b')
        for event in ('schedule', 'workflow_dispatch', 'pull_request_target', 'unknown'):
            with self.subTest(event=event):
                self.assertTrue(CODEQL.select_languages(before, after, event=event)['full_scan'])
        for left, right in ((None, after), (before, None), ({}, after)):
            self.assertTrue(CODEQL.select_languages(left, right)['full_scan'])

    def test_only_existing_ordinary_policy_jsons_use_python_in_the_exact_pinned_generation(self):
        for path in CODEQL._PYTHON_POLICY_JSONS:
            for event in ('pull_request', 'push'):
                before, after = self.pinned_trees()
                after[path] = entry('b')
                with self.subTest(path=path, event=event):
                    self.assertEqual(CODEQL.select_languages(before, after, event=event)['languages'], ['python'])
                after['tools/check.py'] = entry('b')
                self.assertEqual(CODEQL.select_languages(before, after)['languages'], ['python'])

    def test_pinned_policy_exception_retains_javascript_and_unknown_input_owners(self):
        for path in ('client/main.ts', 'data.json', 'package.json', 'package-lock.json', 'yarn.lock',
                     '.github/workflows/branch-cleanup.yml', 'other.yaml', '.github/test-suites-extra.json',
                     'tools/new-unknown-input', 'tools/repository-checks/check.py', 'custom/qlpack.yml'):
            before, after = self.pinned_trees()
            after['.github/test-suites.json'] = entry('b')
            after[path] = entry('b')
            with self.subTest(path=path):
                self.assertEqual(CODEQL.select_languages(before, after)['languages'], list(CODEQL.LANGUAGES))

    def test_ios_host_policy_keeps_python_and_mixed_javascript_owners(self):
        path = '.github/ios-host-orchestration.json'
        for event in ('pull_request', 'push'):
            before, after = self.pinned_trees()
            before[path], after[path] = entry(), entry('b')
            after['tools/check.py'] = entry('b')
            with self.subTest(event=event):
                self.assertEqual(CODEQL.select_languages(before, after, event=event)['languages'], ['python'])
            for extra in ('browser/src/main.ts', '.github/ios-host-orchestration-extra.json'):
                mixed = deepcopy(after)
                mixed[extra] = entry('b')
                with self.subTest(event=event, extra=extra):
                    self.assertEqual(CODEQL.select_languages(before, mixed, event=event)['languages'],
                                     list(CODEQL.LANGUAGES))

    def test_policy_json_add_remove_and_modes_cannot_inherit_the_exception(self):
        for path in CODEQL._PYTHON_POLICY_JSONS:
            for mutation in ('addition', 'removal', 'executable', 'symlink', 'gitlink'):
                before, after = self.pinned_trees()
                if mutation == 'addition':
                    del before[path]
                elif mutation == 'removal':
                    del after[path]
                else:
                    after[path] = entry('b', {'executable': '100755', 'symlink': '120000', 'gitlink': '160000'}[mutation])
                expected = ['javascript-typescript'] if mutation in ('addition', 'removal', 'executable') else list(CODEQL.LANGUAGES)
                with self.subTest(path=path, mutation=mutation):
                    self.assertEqual(CODEQL.select_languages(before, after)['languages'], expected)

    def test_pinned_policy_requires_both_exact_workflows_and_unchanged_configuration(self):
        for workflow in (CODEQL._REVIEWED_CONTROLS['.github/workflows/codeql.yml'], CODEQL._SELECTIVE_WORKFLOW,
                         CODEQL._RESULTS_WORKFLOW, CODEQL._RETARGET_RESULTS_WORKFLOW):
            before, after = self.pinned_trees()
            before['.github/workflows/codeql.yml']['sha'] = workflow
            after['.github/workflows/codeql.yml']['sha'] = workflow
            after['.github/test-suites.json'] = entry('b')
            self.assertEqual(CODEQL.select_languages(before, after)['languages'], ['javascript-typescript'])
            after['.github/workflows/codeql.yml']['sha'] = CODEQL._PINNED_RESULTS_WORKFLOW
            self.assertTrue(CODEQL.select_languages(before, after)['full_scan'])
        for path in CODEQL._REVIEWED_CONTROLS:
            for side in ('base', 'candidate'):
                before, after = self.pinned_trees()
                after['.github/test-suites.json'] = entry('b')
                (before if side == 'base' else after)[path] = entry('b')
                self.assertEqual(CODEQL.select_languages(before, after)['reasons'][0]['code'],
                                 'unreviewed-analysis-configuration')

    def test_result_generations_advance_without_allowing_deployed_rollbacks(self):
        generations = CODEQL.result_workflow_blobs()
        self.assertEqual(generations[:6], (CODEQL._RESULTS_WORKFLOW, CODEQL._RETARGET_RESULTS_WORKFLOW,
                                      CODEQL._PINNED_RESULTS_WORKFLOW, CODEQL._METADATA_RESULTS_WORKFLOW,
                                      CODEQL._SCHEDULING_RESULTS_WORKFLOW, CODEQL._BOOLEAN_RESULTS_WORKFLOW))
        self.assertEqual(len(generations),8)
        self.assertEqual(generations[7],CODEQL._UPLOAD_RESULTS_WORKFLOW)
        self.assertEqual(generations[6],CODEQL._REQUIRED_CONTEXT_RESULTS_WORKFLOW)
        for old_index, old in enumerate(generations):
            for new_index, new in enumerate(generations):
                before, after = self.pinned_trees()
                before['.github/workflows/codeql.yml']['sha'] = old
                after['.github/workflows/codeql.yml']['sha'] = new
                rollback = CODEQL.result_workflow_rollback(before['.github/workflows/codeql.yml'], after['.github/workflows/codeql.yml'])
                with self.subTest(old=old, new=new):
                    self.assertEqual(rollback, new_index < old_index)

    def change(self, path, *, original=None, replacement=None, event="pull_request"):
        before = reviewed_tree()
        if original is not None:
            before[path] = original
        after = deepcopy(before)
        if replacement is None:
            after.pop(path, None)
        else:
            after[path] = replacement
        return CODEQL.select_languages(before, after, event=event)

    def test_pure_python_and_python_dependencies_do_not_select_javascript(self):
        for path in ("tools/check.py", "helper.pyw", "typing.pyi", "protocol.thrift", "requirements.txt",
                     "tests/requirements-host.txt", "constraints-ci.in", "docs/pyproject.toml", "setup.cfg"):
            with self.subTest(path=path):
                plan = self.change(path, replacement=entry("b"))
                self.assertEqual(plan["languages"], ["python"])
                self.assertFalse(plan["full_scan"])

    def test_requirement_names_keep_unknown_inputs_conservative_without_backtracking(self):
        for name in ('requirements.txt', 'constraints.in', 'requirements-dev.txt',
                     'constraints_ci.in', 'requirements.a-b.c.txt',
                     'constraints-' + '-' * 200 + '.txt'):
            with self.subTest(name=name):
                self.assertEqual(self.change(name, replacement=entry('b'))['languages'], ['python'])
        for name in ('requirementsX.txt', 'constraints-.in', 'requirements..txt',
                     'constraints--..txt', 'requirements.a..b.txt',
                     'constraints-' + '-' * 200 + '..txt'):
            with self.subTest(name=name):
                self.assertEqual(self.change(name, replacement=entry('b'))['languages'], list(CODEQL.LANGUAGES))

    def test_python_lock_and_yaml_manifests_are_also_javascript_data_inputs(self):
        for path in ("Pipfile.lock", "poetry.lock", "uv.lock", "environment.yml", "environment.yaml", "conda-lock.yml"):
            with self.subTest(path=path):
                self.assertEqual(self.change(path, replacement=entry("b"))["languages"], list(CODEQL.LANGUAGES))

    def test_javascript_closure_includes_templates_data_config_and_uncommon_source_extensions(self):
        for path in ("client/main.js", "client/view.jsx", "main.cjs", "main.mjs", "main.es6", "main.xsjslib",
                     "types/main.ts", "types/view.tsx", "types/main.mts", "types/main.cts", "web/index.HTML",
                     "web/view.vue", "web/view.html.erb", "web/view.njk", "web/view.hbs", "web/view.ejs",
                     "client/package.json", "client/package-lock.json", "client/tsconfig.json", "yarn.lock",
                     "api/model.raml", "client/data.yaml", "client/data.yml", "client/.babelrc", "client/.xsaccess"):
            with self.subTest(path=path):
                self.assertEqual(self.change(path, replacement=entry("b"))["languages"], ["javascript-typescript"])

    def test_markdown_and_identical_inputs_require_no_language_job(self):
        self.assertEqual(self.change("docs/design.md", replacement=entry("b"))["languages"], [])
        tree = reviewed_tree()
        self.assertEqual(CODEQL.select_languages(tree, deepcopy(tree))["languages"], [])

    def test_python_mixed_with_markdown_remains_python_only(self):
        before = reviewed_tree()
        after = deepcopy(before)
        after["tools/check.py"] = entry("b")
        after["docs/design.md"] = entry("b")
        self.assertEqual(CODEQL.select_languages(before, after)["languages"], ["python"])

    def test_rename_keeps_old_and_new_paths_and_both_language_closures(self):
        before = reviewed_tree()
        after = deepcopy(before)
        after["browser/renamed.js"] = after.pop("tools/check.py")
        plan = CODEQL.select_languages(before, after)
        self.assertEqual(plan["languages"], list(CODEQL.LANGUAGES))
        by_path = {item["path"]: item for item in plan["changes"]}
        self.assertIsNone(by_path["tools/check.py"]["after"])
        self.assertIsNone(by_path["browser/renamed.js"]["before"])

    def test_python_delete_and_executable_mode_only_change_select_python(self):
        self.assertEqual(self.change("tools/check.py", original=entry())["languages"], ["python"])
        plan = self.change("tools/check.py", original=entry(), replacement=entry(mode="100755"))
        self.assertEqual(plan["languages"], ["python"])
        self.assertEqual(plan["changes"][0]["before"]["sha"], plan["changes"][0]["after"]["sha"])
        self.assertNotEqual(plan["changes"][0]["before"]["mode"], plan["changes"][0]["after"]["mode"])

    def test_every_shared_analysis_control_and_query_pack_keeps_both_languages(self):
        for path in (".github/workflows/codeql.yml",
                     ".github/codeql/model.py", "custom/queries/check.ql", "custom/queries/lib.qll", "queries/security.qls",
                     "custom/qlpack.yml", "packs/codeql-pack.lock.yml", "custom/codeql-config.yml",
                     "custom/codeql-python/model.py", "custom/qlpacks/model.yaml", "AGENTS.md", ".gitignore",
                     ".gitattributes", ".gitmodules", ".codeqlignore", ".tool-versions",
                     "tools/repository-checks/codeql.py", "tools/test-evidence/inputs.py"):
            with self.subTest(path=path):
                self.assertTrue(self.change(path, replacement=entry("b"))["full_scan"])

    def test_verifier_and_regression_python_changes_do_not_change_javascript_extraction(self):
        for path in ('tools/repository-checks/codeql_results.py', 'tests/codeql-selection-test.py'):
            with self.subTest(path=path):
                self.assertEqual(self.change(path, replacement=entry('b'))['languages'], ['python'])

    def test_unrelated_workflow_data_and_local_actions_keep_their_own_language(self):
        self.assertEqual(self.change('.github/workflows/new.yml', replacement=entry('b'))['languages'],
                         ['javascript-typescript'])
        self.assertEqual(self.change('.github/actions/scan/index.py', replacement=entry('b'))['languages'],
                         ['python'])

    def test_reviewed_selective_workflow_supports_pure_language_changes(self):
        for digest in (CODEQL._REVIEWED_CONTROLS['.github/workflows/codeql.yml'], CODEQL._SELECTIVE_WORKFLOW):
            before = reviewed_tree()
            before['.github/workflows/codeql.yml']['sha'] = digest
            after = deepcopy(before)
            after['tools/check.py'] = entry('b')
            self.assertEqual(CODEQL.select_languages(before, after)['languages'], ['python'])
        before = reviewed_tree()
        after = deepcopy(before)
        after['.github/workflows/codeql.yml']['sha'] = CODEQL._SELECTIVE_WORKFLOW
        self.assertTrue(CODEQL.select_languages(before, after)['full_scan'])

    def test_saved_workflow_digest_matches_the_actual_reviewed_activation(self):
        actual = subprocess.check_output(['git', 'hash-object', '.github/workflows/codeql.yml'],
                                         cwd=ROOT, text=True).strip()
        self.assertIn(actual, {CODEQL._SELECTIVE_WORKFLOW, *CODEQL.result_workflow_blobs()})
        canonical = ROOT / "tools/repository-checks/workflows/codeql-results.yml"
        expected = subprocess.check_output(["git", "hash-object", str(canonical)], cwd=ROOT, text=True).strip()
        self.assertEqual(expected, CODEQL._RESULTS_WORKFLOW)
        successor = ROOT / 'tools/repository-checks/workflows/metadata-edits/codeql.yml'
        self.assertEqual(subprocess.check_output(['git', 'hash-object', str(successor)], cwd=ROOT, text=True).strip(),
                         CODEQL._RETARGET_RESULTS_WORKFLOW)
        pinned = successor.with_name('codeql-pinned.yml')
        self.assertEqual(subprocess.check_output(['git', 'hash-object', str(pinned)], cwd=ROOT, text=True).strip(),
                         CODEQL._PINNED_RESULTS_WORKFLOW)
        # Changing the tool pin or its required version check cannot keep admission.
        for source in (pinned.read_bytes().replace(b'v2.27.2/', b'v2.27.3/'),
                       pinned.read_bytes().replace(b'= 2.27.2', b'= 2.27.3')):
            modified = subprocess.check_output(['git', 'hash-object', '--stdin'], input=source, cwd=ROOT).decode().strip()
            before, after = self.pinned_trees()
            before['.github/workflows/codeql.yml']['sha'] = modified
            after['.github/test-suites.json'] = entry('b')
            self.assertEqual(CODEQL.select_languages(before, after)['reasons'][0]['code'], 'unreviewed-analysis-configuration')

    def test_retarget_generation_is_exact_and_classification_control_is_shared(self):
        before = reviewed_tree()
        before['.github/workflows/codeql.yml']['sha'] = CODEQL._RETARGET_RESULTS_WORKFLOW
        for path, expected in (('app/main.py', ['python']), ('app/main.ts', ['javascript-typescript']),
                               ('tools/repository-checks/check.py', list(CODEQL.LANGUAGES))):
            after = deepcopy(before); after[path] = entry('b')
            self.assertEqual(CODEQL.select_languages(before, after)['languages'], expected)
        after = deepcopy(before)
        after['.github/workflows/codeql.yml']['sha'] = CODEQL._RESULTS_WORKFLOW
        selected = CODEQL.select_languages(before, after)
        self.assertTrue(selected['full_scan'])
        self.assertEqual(selected['reasons'][0]['code'], 'analysis-workflow-rollback')
        self.assertTrue(CODEQL.result_workflow_rollback(before['.github/workflows/codeql.yml'],
                                                       after['.github/workflows/codeql.yml']))

    def test_both_sides_must_match_reviewed_actual_workflow_and_configuration(self):
        for path in CODEQL._REVIEWED_CONTROLS:
            before = reviewed_tree()
            after = deepcopy(before)
            after["tools/check.py"] = entry("b")
            for action in ("changed-both", "missing-base", "missing-candidate", "executable-control"):
                left, right = deepcopy(before), deepcopy(after)
                if action == "changed-both":
                    left[path] = right[path] = entry("c")
                elif action == "missing-base":
                    del left[path]
                elif action == "missing-candidate":
                    del right[path]
                else:
                    left[path]["mode"] = right[path]["mode"] = "100755"
                with self.subTest(path=path, action=action):
                    self.assertEqual(CODEQL.select_languages(left, right)["reasons"][0]["code"],
                                     "unreviewed-analysis-configuration")

    def test_querypack_helpers_and_models_keep_the_complete_pack_directory_global(self):
        for manifest in ("custom/security/qlpack.yml", "qlpack.yml"):
            for changed in ("custom/security/helpers/generate.py", "custom/security/models/library.yaml"):
                before = reviewed_tree() | {manifest: entry(), changed: entry()}
                after = deepcopy(before)
                after[changed] = entry("b")
                with self.subTest(manifest=manifest, changed=changed):
                    plan = CODEQL.select_languages(before, after)
                    self.assertTrue(plan["full_scan"])
                    self.assertEqual(plan["reasons"][0]["code"], "shared-analysis-control")

    def test_ignored_javascript_remains_conservative_for_import_and_type_dependencies(self):
        path = "interface/resources/qml/controls/CpuShadowPixels.js"
        self.assertEqual(self.change(path, replacement=entry("b"))["languages"], ["javascript-typescript"])

    def test_unknown_inputs_and_extensionless_shebangs_never_disappear(self):
        for path in ("bin/script", "web/new.extractor-input", "interface/model.qml", "CMakeLists.txt"):
            with self.subTest(path=path):
                plan = self.change(path, replacement=entry("b"))
                self.assertTrue(plan["full_scan"])
                self.assertEqual(plan["reasons"][0]["code"], "unknown-analysis-input")

    def test_unchanged_aliases_and_gitlinks_still_require_full_scan(self):
        for mode in ("120000", "160000"):
            before = reviewed_tree() | {"browser/alias.js": entry(mode=mode)}
            after = deepcopy(before)
            after["tools/check.py"] = entry("b")
            plan = CODEQL.select_languages(before, after)
            self.assertTrue(plan["full_scan"])
            self.assertEqual(plan["reasons"][0]["code"], "unresolved-source-alias-or-submodule")

    def test_schedules_and_unsupported_events_always_scan_both_languages(self):
        self.assertEqual(CODEQL.select_languages(None, None, event="schedule")["languages"], list(CODEQL.LANGUAGES))
        for event in ("workflow_dispatch", "pull_request_target", "unrecognized"):
            with self.subTest(event=event):
                self.assertTrue(self.change("tools/check.py", replacement=entry("b"), event=event)["full_scan"])

    def test_missing_or_malformed_inventory_fails_closed(self):
        for tree in (None, [], ["tools/check.py"], {"tools/check.py": {"sha": "a" * 40}},
                     {"../other.py": entry()}, {"tools/check.py": entry(mode="100664")}):
            for left, right in ((tree, reviewed_tree()), (reviewed_tree(), tree)):
                with self.subTest(tree=tree):
                    plan = CODEQL.select_languages(left, right)
                    self.assertTrue(plan["full_scan"])
                    self.assertEqual(plan["reasons"][0]["code"], "unavailable-complete-inventory")


class NpmLockSelectionTests(unittest.TestCase):
    def trees(self, workflow=None):
        before = reviewed_tree()
        before['.github/workflows/codeql.yml']['sha'] = workflow or CODEQL._PINNED_RESULTS_WORKFLOW
        before.update({path: entry() for path in CODEQL._PINNED_NPM_LOCKS})
        after = deepcopy(before)
        for path in CODEQL._PINNED_NPM_LOCKS:
            after[path] = entry('b')
        return before, after

    def test_only_two_existing_lockfiles_omit_analysis_under_both_pinned_recipes(self):
        self.assertEqual(CODEQL._PINNED_NPM_LOCKS, {
            'browser-client/package-lock.json', 'script-archive/marketplace/S3Server/package-lock.json'})
        for workflow in (CODEQL._PINNED_RESULTS_WORKFLOW, CODEQL._METADATA_RESULTS_WORKFLOW):
            for event in ('pull_request', 'push'):
                before, after = self.trees(workflow)
                with self.subTest(workflow=workflow, event=event):
                    plan = CODEQL.select_languages(before, after, event=event)
                    self.assertEqual(plan['languages'], [])
                    self.assertEqual(plan['reasons'], [{'code': 'reviewed-pinned-npm-lock', 'path': path}
                                                       for path in sorted(CODEQL._PINNED_NPM_LOCKS)])

    def test_lockfiles_cannot_hide_source_manifests_or_unknown_neighbors(self):
        for path, expected in (
                ('browser-client/main.ts', ['javascript-typescript']),
                ('tools/helper.py', ['python']),
                ('browser-client/package.json', ['javascript-typescript']),
                ('script-archive/marketplace/S3Server/package.json', ['javascript-typescript']),
                ('other/package-lock.json', ['javascript-typescript']),
                ('browser-client/package-lock.json.backup', list(CODEQL.LANGUAGES)),
                ('.github/codeql/custom.ql', list(CODEQL.LANGUAGES))):
            before, after = self.trees()
            after[path] = entry('c')
            with self.subTest(path=path):
                self.assertEqual(CODEQL.select_languages(before, after)['languages'], expected)

    def test_membership_modes_and_aliases_require_conservative_checks(self):
        for path in CODEQL._PINNED_NPM_LOCKS:
            for mutation in ('added', 'deleted', 'renamed', 'before-mode', 'after-mode', 'alias', 'gitlink'):
                before, after = self.trees()
                if mutation == 'added': del before[path]
                elif mutation == 'deleted': del after[path]
                elif mutation == 'renamed': after[path + '.other.json'] = after.pop(path)
                elif mutation == 'before-mode': before[path] = entry(mode='100755')
                elif mutation == 'after-mode': after[path] = entry('b', '100755')
                else: after[path] = entry('b', '120000' if mutation == 'alias' else '160000')
                expected = list(CODEQL.LANGUAGES) if mutation in ('alias', 'gitlink') else ['javascript-typescript']
                with self.subTest(path=path, mutation=mutation):
                    self.assertEqual(CODEQL.select_languages(before, after)['languages'], expected)

    def test_pins_configuration_packs_and_unchanged_aliases_precede_lock_exceptions(self):
        for workflow in (CODEQL._REVIEWED_CONTROLS['.github/workflows/codeql.yml'], CODEQL._SELECTIVE_WORKFLOW,
                         CODEQL._RESULTS_WORKFLOW, CODEQL._RETARGET_RESULTS_WORKFLOW):
            before, after = self.trees(workflow)
            self.assertEqual(CODEQL.select_languages(before, after)['languages'], ['javascript-typescript'])
        for path, mode in (('.github/codeql/codeql-config.yml', '100644'), ('qlpack.yml', '100644'),
                           ('unchanged/source.py', '120000'), ('unchanged/submodule', '160000')):
            before, after = self.trees()
            if path in before: after[path] = entry('c', mode)
            else: before[path] = after[path] = entry(mode=mode)
            with self.subTest(path=path):
                self.assertTrue(CODEQL.select_languages(before, after)['full_scan'])
        before, after = self.trees()
        after['.github/workflows/codeql.yml']['sha'] = CODEQL._METADATA_RESULTS_WORKFLOW
        self.assertTrue(CODEQL.select_languages(before, after)['full_scan'])

    def test_unknown_context_and_schedule_keep_full_analysis(self):
        before, after = self.trees()
        for event in ('schedule', 'workflow_dispatch', 'pull_request_target', 'unknown'):
            self.assertTrue(CODEQL.select_languages(before, after, event=event)['full_scan'])
        for left, right in ((None, after), (before, None), ({}, after)):
            self.assertTrue(CODEQL.select_languages(left, right)['full_scan'])


class PythonControlSelectionTests(unittest.TestCase):
    controls = ('tools/repository-checks/check.py', 'tools/repository-checks/codeql.py',
                'tools/test-evidence/inputs.py')

    def trees(self, workflow=None):
        before = reviewed_tree() | {path: entry() for path in self.controls}
        before['.github/workflows/codeql.yml']['sha'] = workflow or CODEQL._PINNED_RESULTS_WORKFLOW
        return before, deepcopy(before)

    def test_only_three_existing_ordinary_controls_need_fresh_python_under_both_pinned_recipes(self):
        self.assertEqual(CODEQL._PINNED_PYTHON_CONTROLS, set(self.controls))
        for workflow in (CODEQL._PINNED_RESULTS_WORKFLOW, CODEQL._METADATA_RESULTS_WORKFLOW):
            for path in self.controls:
                for event in ('pull_request', 'push'):
                    before, after = self.trees(workflow); after[path] = entry('b')
                    with self.subTest(workflow=workflow, path=path, event=event):
                        plan = CODEQL.select_languages(before, after, event=event,
                            read_blob=lambda _: self.fail('Python selection must not load candidate source'))
                        self.assertEqual(plan['languages'], ['python'])
                        self.assertEqual(plan['reasons'], [{'code': 'reviewed-pinned-python-control', 'path': path}])
                        self.assertFalse(plan['full_scan'])

    def test_global_controls_queries_and_pack_roots_override_the_exception(self):
        for subject in self.controls:
            for path in ('AGENTS.md', '.gitattributes', 'custom/query.ql', 'custom/model.qll',
                         'custom/security.qls', 'custom/codeql-config.yml', 'custom/qlpack.yml'):
                before, after = self.trees(); after[subject] = entry('b'); after[path] = entry('c')
                with self.subTest(subject=subject, path=path):
                    self.assertEqual(CODEQL.select_languages(before, after)['languages'], list(CODEQL.LANGUAGES))
            for manifest in ('qlpack.yml', str(Path(subject).parent / 'qlpack.yml')):
                before, after = self.trees(); before[manifest] = after[manifest] = entry()
                after[subject] = entry('b')
                with self.subTest(subject=subject, manifest=manifest):
                    self.assertEqual(CODEQL.select_languages(before, after)['reasons'][0]['code'], 'shared-analysis-control')

    def test_membership_modes_and_unchanged_aliases_cannot_inherit_python_control_ownership(self):
        for path in self.controls:
            for mutation in ('addition', 'deletion', 'rename', 'before-mode', 'after-mode',
                             'symlink', 'gitlink', 'unchanged-alias', 'unchanged-gitlink'):
                before, after = self.trees(); after[path] = entry('b')
                if mutation == 'addition': del before[path]
                elif mutation == 'deletion': del after[path]
                elif mutation == 'rename': after[path + '.renamed.py'] = after.pop(path)
                elif mutation == 'before-mode': before[path] = entry(mode='100755')
                elif mutation == 'after-mode': after[path] = entry('b', mode='100755')
                elif mutation in ('symlink', 'gitlink'):
                    after[path] = entry('b', mode='120000' if mutation == 'symlink' else '160000')
                else:
                    before['unrelated'] = after['unrelated'] = entry(mode='120000' if mutation == 'unchanged-alias' else '160000')
                with self.subTest(path=path, mutation=mutation):
                    self.assertTrue(CODEQL.select_languages(before, after)['full_scan'])

    def test_unpinned_changed_or_unknown_controls_and_extractor_options_stay_full(self):
        for workflow in (CODEQL._REVIEWED_CONTROLS['.github/workflows/codeql.yml'], CODEQL._SELECTIVE_WORKFLOW,
                         CODEQL._RESULTS_WORKFLOW, CODEQL._RETARGET_RESULTS_WORKFLOW):
            before, after = self.trees(workflow); after[self.controls[0]] = entry('b')
            self.assertTrue(CODEQL.select_languages(before, after)['full_scan'])
        for side in ('before', 'after'):
            for path in CODEQL._REVIEWED_CONTROLS:
                before, after = self.trees(); after[self.controls[0]] = entry('b')
                (before if side == 'before' else after)[path] = entry('c')
                with self.subTest(side=side, path=path):
                    self.assertEqual(CODEQL.select_languages(before, after)['reasons'][0]['code'], 'unreviewed-analysis-configuration')
        before, after = self.trees(); after[self.controls[0]] = entry('b')
        after['.github/workflows/codeql.yml']['sha'] = CODEQL._METADATA_RESULTS_WORKFLOW
        self.assertTrue(CODEQL.select_languages(before, after)['full_scan'])
        for name in ('LGTM_INDEX_FILETYPES', 'CODEQL_EXTRACTOR_JAVASCRIPT_OPTION_TEST',
                     'CODEQL_EXTRACTOR_PYTHON_OPTION_TEST'):
            before, after = self.trees(); after[self.controls[0]] = entry('b')
            with self.subTest(name=name), patch.dict(CODEQL.os.environ, {name: 'unreviewed'}):
                self.assertTrue(CODEQL.select_languages(before, after)['full_scan'])

    def test_mixed_delta_unions_every_language_and_unknown_input_without_prefix_waivers(self):
        for path, expected in (('browser/src/main.ts', list(CODEQL.LANGUAGES)),
                               ('other.py', ['python']), ('docs/design.md', ['python']),
                               ('.github/test-suites.json', ['python']),
                               ('.github/ci37-runtime.json', list(CODEQL.LANGUAGES)),
                               ('tools/repository-checks/check.py.unknown', list(CODEQL.LANGUAGES)),
                               ('tools/test-evidence/inputs.py.unknown', list(CODEQL.LANGUAGES))):
            before, after = self.trees(); after[self.controls[0]] = entry('b')
            if path == '.github/test-suites.json': before[path] = entry()
            after[path] = entry('c')
            with self.subTest(path=path):
                self.assertEqual(CODEQL.select_languages(before, after)['languages'], expected)
        before, after = self.trees(); after[self.controls[0]] = entry('b')
        for event in ('schedule', 'workflow_dispatch', 'pull_request_target'):
            self.assertTrue(CODEQL.select_languages(before, after, event=event)['full_scan'])
        for left, right in ((None, after), (before, None), ({}, after)):
            self.assertTrue(CODEQL.select_languages(left, right)['full_scan'])


class BooleanRecipeSelectionTests(unittest.TestCase):
    recipes = {
        'tools/repository-checks/workflows/producers/repository-checks.yml':
            ('81bcf1933edc435826e2de411a777cccd4dec7c7','15d1b9ca9d4b58831cd5f8226efcd47681dd3e8a'),
        'tools/repository-checks/workflows/metadata-edits/codeql-metadata.yml':
            ('e9aaaed9693efc5ffb4701697ac2a4d51f5f5ba1','3b7a88765b7181a1bc7dd6f48b9b459e590055d3'),
    }

    def trees(self):
        before=reviewed_tree()
        before['.github/workflows/codeql.yml']={'mode':'100644','type':'blob','sha':CODEQL._SCHEDULING_RESULTS_WORKFLOW}
        before['.github/workflows/pr-metadata-context.yml']={'mode':'100644','type':'blob','sha':CODEQL._SCHEDULING_SOURCE_WORKFLOW}
        before['.github/workflows/repository-checks.yml']={'mode':'100644','type':'blob',
            'sha':'81bcf1933edc435826e2de411a777cccd4dec7c7'}
        for path,(old,_) in self.recipes.items():before[path]={'mode':'100644','type':'blob','sha':old}
        for path in CODEQL._PINNED_PYTHON_CONTROLS:before[path]=entry()
        return before,deepcopy(before)

    def transition(self,path):
        before,after=self.trees()
        after[path]={'mode':'100644','type':'blob','sha':self.recipes[path][1]}
        return before,after

    def test_exact_existing_passive_pairs_need_no_analysis_and_keep_python_owner(self):
        self.assertEqual(CODEQL._BOOLEAN_PASSIVE_RECIPES,self.recipes)
        for path in self.recipes:
            for event in ('pull_request','push'):
                before,after=self.transition(path)
                with self.subTest(path=path,event=event):
                    plan=CODEQL.select_languages(before,after,event=event,
                        read_blob=lambda _:self.fail('selection must not load candidate recipe code'))
                    self.assertEqual(plan['languages'],[])
                    self.assertEqual(plan['reasons'],[{'code':'reviewed-boolean-metadata-recipe','path':path}])
                    after['tools/repository-checks/check.py']=entry('b')
                    self.assertEqual(CODEQL.select_languages(before,after,event=event)['languages'],['python'])
        before,after=self.trees()
        for path,(_,new) in self.recipes.items():after[path]['sha']=new
        self.assertEqual(CODEQL.select_languages(before,after)['languages'],[])

    def test_exact_forward_active_pair_keeps_zero_or_python_only_analysis(self):
        for control in CODEQL._PINNED_PYTHON_CONTROLS:
            before,after=self.trees();after['.github/workflows/codeql.yml']['sha']=CODEQL._BOOLEAN_RESULTS_WORKFLOW
            self.assertEqual(CODEQL.select_languages(before,after)['languages'],[])
            after[control]=entry('b')
            with self.subTest(control=control):
                plan=CODEQL.select_languages(before,after)
                self.assertEqual(plan['languages'],['python'])
                self.assertIn({'code':'reviewed-pinned-python-control','path':control},plan['reasons'])
                after['browser/src/main.ts']=entry('b')
                self.assertEqual(CODEQL.select_languages(before,after)['languages'],list(CODEQL.LANGUAGES))

    def test_real_two_caller_activation_needs_zero_or_only_changed_python_analysis(self):
        before,after=self.trees()
        after['.github/workflows/repository-checks.yml']['sha']=CODEQL._BOOLEAN_REPOSITORY_PAIR[1]
        after['.github/workflows/codeql.yml']['sha']=CODEQL._BOOLEAN_RESULTS_WORKFLOW
        self.assertEqual(CODEQL.select_languages(before,after)['languages'],[])
        for control in CODEQL._PINNED_PYTHON_CONTROLS:
            mixed=deepcopy(after);mixed[control]=entry('b')
            with self.subTest(control=control):
                plan=CODEQL.select_languages(before,mixed)
                self.assertEqual(plan['languages'],['python'])
                self.assertFalse(plan['full_scan'])
        for mutation in ('unknown-before','unknown-after','removal','addition','mode','rollback'):
            left,right=deepcopy(before),deepcopy(after)
            path='.github/workflows/repository-checks.yml'
            if mutation=='unknown-before':left[path]['sha']='f'*40
            elif mutation=='unknown-after':right[path]['sha']='f'*40
            elif mutation=='removal':del right[path]
            elif mutation=='addition':del left[path]
            elif mutation=='mode':right[path]['mode']='100755'
            else:left[path],right[path]=right[path],left[path]
            with self.subTest(mutation=mutation):
                self.assertTrue(CODEQL.select_languages(left,right)['full_scan'])

    def test_passive_unknown_bytes_membership_modes_and_rollback_stay_full(self):
        for path in self.recipes:
            for mutation in ('new-path','removal','before-unknown','after-unknown','before-mode','after-mode',
                    'symlink','gitlink','rollback'):
                before,after=self.transition(path)
                if mutation=='new-path':del before[path]
                elif mutation=='removal':del after[path]
                elif mutation=='before-unknown':before[path]['sha']='f'*40
                elif mutation=='after-unknown':after[path]['sha']='f'*40
                elif mutation=='before-mode':before[path]['mode']='100755'
                elif mutation=='after-mode':after[path]['mode']='100755'
                elif mutation=='symlink':after[path]['mode']='120000'
                elif mutation=='gitlink':after[path].update(mode='160000',type='commit')
                else:before[path],after[path]=after[path],before[path]
                with self.subTest(path=path,mutation=mutation):
                    self.assertEqual(CODEQL.select_languages(before,after)['languages'],list(CODEQL.LANGUAGES))

    def test_configuration_helpers_packs_aliases_options_and_unknown_inputs_cannot_hide(self):
        for subject in (*self.recipes,'.github/workflows/codeql.yml','.github/workflows/repository-checks.yml'):
            for mutation in ('config','helper','helper-mode','pack','overlap-pack','alias','unknown','javascript'):
                before,after=self.trees()
                after[subject]['sha']=CODEQL._BOOLEAN_RESULTS_WORKFLOW if subject=='.github/workflows/codeql.yml' else CODEQL._BOOLEAN_REPOSITORY_PAIR[1] if subject=='.github/workflows/repository-checks.yml' else self.recipes[subject][1]
                after['tools/repository-checks/check.py']=entry('b')
                if mutation=='config':after['.github/codeql/codeql-config.yml']=entry('b')
                elif mutation=='helper':after['.github/workflows/pr-metadata-context.yml']=entry('b')
                elif mutation=='helper-mode':after['.github/workflows/pr-metadata-context.yml']['mode']='100755'
                elif mutation in ('pack','overlap-pack'):
                    name='custom/qlpack.yml' if mutation=='pack' else str(Path(subject).parent/'qlpack.yml')
                    before[name]=after[name]=entry()
                elif mutation=='alias':before['unmodified-alias']=after['unmodified-alias']=entry(mode='120000')
                elif mutation=='unknown':after['unreviewed-source']=entry('b')
                else:after['browser/src/main.ts']=entry('b')
                with self.subTest(subject=subject,mutation=mutation):
                    self.assertEqual(CODEQL.select_languages(before,after)['languages'],list(CODEQL.LANGUAGES))
            before,after=self.trees();after[subject]['sha']=CODEQL._BOOLEAN_RESULTS_WORKFLOW if subject=='.github/workflows/codeql.yml' else CODEQL._BOOLEAN_REPOSITORY_PAIR[1] if subject=='.github/workflows/repository-checks.yml' else self.recipes[subject][1]
            for name in ('LGTM_INDEX_FILTERS','CODEQL_EXTRACTOR_JAVASCRIPT_OPTION_TEST','CODEQL_EXTRACTOR_PYTHON_OPTION_TEST'):
                with self.subTest(subject=subject,option=name),patch.dict(CODEQL.os.environ,{name:'unreviewed'}):
                    self.assertTrue(CODEQL.select_languages(before,after)['full_scan'])

    def test_other_active_transitions_and_wrong_relative_helper_remain_full(self):
        for old,new in ((CODEQL._PINNED_RESULTS_WORKFLOW,CODEQL._METADATA_RESULTS_WORKFLOW),
                (CODEQL._METADATA_RESULTS_WORKFLOW,CODEQL._SCHEDULING_RESULTS_WORKFLOW),
                (CODEQL._BOOLEAN_RESULTS_WORKFLOW,CODEQL._SCHEDULING_RESULTS_WORKFLOW)):
            before,after=self.trees();before['.github/workflows/codeql.yml']['sha']=old;after['.github/workflows/codeql.yml']['sha']=new
            with self.subTest(old=old,new=new):self.assertTrue(CODEQL.select_languages(before,after)['full_scan'])
        before,after=self.trees();after['.github/workflows/codeql.yml']['sha']=CODEQL._BOOLEAN_RESULTS_WORKFLOW
        after['.github/workflows/pr-metadata-context.yml']['sha']='f'*40
        self.assertTrue(CODEQL.select_languages(before,after)['full_scan'])

    def test_known_raw_pairs_change_only_boolean_metadata_input_not_analysis_payload(self):
        import yaml
        spec=importlib.util.spec_from_file_location('boolean_recipe_frozen_sources',ROOT/'tests/workflow-contract-test.py')
        frozen=importlib.util.module_from_spec(spec);spec.loader.exec_module(frozen)
        for path,(old,new) in self.recipes.items():
            name='codeql' if path.endswith('codeql-metadata.yml') else 'repository-checks'
            before=frozen.original_default_workflow(name);after=boolean_recipe_bytes(path)
            with self.subTest(path=path):
                for raw,oid in ((before,old),(after,new)):
                    self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),oid)
                old_lines=before.splitlines(keepends=True);new_lines=after.splitlines(keepends=True)
                self.assertEqual(len(old_lines),len(new_lines))
                changes=[(a,b) for a,b in zip(old_lines,new_lines) if a!=b]
                self.assertEqual(len(changes),1)
                old_line,new_line=changes[0]
                self.assertIn(b'nonproducer_intent: ${{ ',old_line)
                self.assertEqual(new_line,old_line.replace(b'${{ ',b'${{ !(!(',1).replace(b' }}',b')) }}',1))
                a,b=yaml.safe_load(before),yaml.safe_load(after)
                a['jobs']['metadata-source']['with'].pop('nonproducer_intent')
                b['jobs']['metadata-source']['with'].pop('nonproducer_intent')
                self.assertEqual(a,b)
        helper=(ROOT/'tools/repository-checks/workflows/metadata-edits/pr-metadata-context.yml').read_bytes()
        self.assertEqual(hashlib.sha1(b'blob '+str(len(helper)).encode()+b'\0'+helper).hexdigest(),CODEQL._SCHEDULING_SOURCE_WORKFLOW)


class NativeLeafSelectionTests(unittest.TestCase):
    def setUp(self):
        self.before = reviewed_tree()
        self.before['.github/workflows/codeql.yml']['sha'] = CODEQL._PINNED_RESULTS_WORKFLOW
        self.after, self.blobs = deepcopy(self.before), {}

    def put(self, tree, path, raw, mode='100644'):
        oid = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        self.blobs[oid] = raw
        tree[path] = {'mode': mode, 'type': 'blob', 'sha': oid}

    def native(self, path='native/Example.cpp', old=b'int value = 1;\n', new=b'int value = 2;\n'):
        self.put(self.before, path, old); self.put(self.after, path, new)

    def select(self, **options):
        return CODEQL.select_languages(self.before,self.after,read_blob=self.blobs.__getitem__,**options)

    def test_exact_existing_suffixes_skip_both_pinned_languages_with_old_and_new_blob_proof(self):
        self.assertEqual(CODEQL._PINNED_NATIVE_EXTENSIONS,
            {'.c','.cpp','.h','.hpp','.m','.mm','.qml','.vert','.frag','.glsl'})
        for suffix in CODEQL._PINNED_NATIVE_EXTENSIONS:
            self.native('native/Example'+suffix)
        for event in ('pull_request','push'):
            plan = self.select(event=event)
            self.assertEqual(plan['languages'], [])
            self.assertEqual(len(plan['changes']),10)
            self.assertTrue(all(row['code']=='reviewed-pinned-native-source' for row in plan['reasons']))
        self.assertTrue(CODEQL.select_languages(self.before,self.after)['full_scan'], 'no blob proof means full scans')

    def test_shebang_binary_invalid_utf8_missing_or_mismatching_immutable_bytes_decline(self):
        for raw in (b'#!/usr/bin/env python\nprint(1)\n', b'#!/usr/bin/env node\n',
                    b'\xef\xbb\xbf#!/bin/unknown\n', b'\0native', b'\xffnative'):
            self.native(new=raw)
            with self.subTest(raw=raw):self.assertTrue(self.select()['full_scan'])
        self.native()
        for reader in (lambda oid: b'unbound bytes',lambda oid: 'not bytes',lambda oid: None):
            self.assertTrue(CODEQL.select_languages(self.before,self.after,read_blob=reader)['full_scan'])
        with patch.object(CODEQL,'_NATIVE_BLOB_BYTES',1):self.assertTrue(self.select()['full_scan'])
        for failure in (OSError('unavailable'),CODEQL.inputs.InputError('unavailable'),subprocess.TimeoutExpired('git',10)):
            with self.subTest(failure=type(failure).__name__):
                def unavailable(_oid):raise failure
                self.assertTrue(CODEQL.select_languages(self.before,self.after,read_blob=unavailable)['full_scan'])

    def test_exact_case_membership_modes_and_both_endpoint_contents_are_mandatory(self):
        for mutation in ('addition','deletion','rename','before-executable','after-executable','old-shebang'):
            self.setUp();self.native()
            if mutation=='addition':self.before.pop('native/Example.cpp')
            elif mutation=='deletion':self.after.pop('native/Example.cpp')
            elif mutation=='rename':self.after['native/Renamed.cpp']=self.after.pop('native/Example.cpp')
            elif mutation=='before-executable':self.before['native/Example.cpp']['mode']='100755'
            elif mutation=='after-executable':self.after['native/Example.cpp']['mode']='100755'
            else:self.put(self.before,'native/Example.cpp',b'#!/usr/bin/python\n')
            with self.subTest(mutation=mutation):self.assertTrue(self.select()['full_scan'])
        for path in ('native/Example.CPP','native/Example.H','native/Example.cc','native/.eslintrc.cpp','native/.hidden.h'):
            self.setUp();self.native(path)
            with self.subTest(path=path):self.assertTrue(self.select()['full_scan'])

    def test_mixed_known_languages_remain_selected_and_global_alias_pack_unknown_stay_full(self):
        for changes,expected in (({'tools/check.py'},['python']),({'browser/src/main.ts'},['javascript-typescript']),
                ({'tools/check.py','browser/src/main.ts'},list(CODEQL.LANGUAGES)),
                ({'unknown.data'},list(CODEQL.LANGUAGES)),({'tools/repository-checks/codeql.py'},list(CODEQL.LANGUAGES))):
            self.setUp();self.native()
            for path in changes:self.after[path]=entry('b')
            with self.subTest(changes=changes):self.assertEqual(self.select()['languages'],expected)
        for mutation in ('old-workflow','config','symlink','gitlink','pack'):
            self.setUp();self.native()
            if mutation=='old-workflow':self.before['.github/workflows/codeql.yml']['sha']=CODEQL._RETARGET_RESULTS_WORKFLOW
            elif mutation=='config':self.after['.github/codeql/codeql-config.yml']=entry('b')
            elif mutation in ('symlink','gitlink'):
                self.before['unrelated']=self.after['unrelated']=entry(mode='120000' if mutation=='symlink' else '160000')
            else:
                self.before['native/qlpack.yml']=self.after['native/qlpack.yml']=entry()
            def no_blob(_oid):raise AssertionError('global safeguards precede native blob reads')
            with self.subTest(mutation=mutation):
                self.assertTrue(CODEQL.select_languages(self.before,self.after,read_blob=no_blob)['full_scan'])


class ImmutableRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="overte-codeql-selection-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.git("init", "-q", "--initial-branch=main")
        self.git("config", "user.name", "CodeQL selection fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        for relative in CODEQL._REVIEWED_CONTROLS:
            self.write(relative, (ROOT / relative).read_text())
        # Historical transitions start at the exact predecessor even after the
        # checkout activates its successor; do not inherit ROOT's active version.
        self.write(".github/workflows/codeql.yml",
                   (ROOT / "tools/repository-checks/workflows/codeql-results.yml").read_text())
        self.write("tools/check.py", "raise RuntimeError('candidate source must never be imported')\n")
        self.write("tools/test-evidence/inputs.py", "raise RuntimeError('candidate inventory must never be imported')\n")
        self.write("browser/main.ts", "export const value = 1;\n")
        self.base = self.commit()
        self.assertEqual(self.git("rev-parse", self.base + ":.github/workflows/codeql.yml"),
                         CODEQL._RESULTS_WORKFLOW)

    def git(self, *arguments):
        return subprocess.check_output(["git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *arguments],
                                       cwd=self.root, text=True, stderr=subprocess.PIPE).strip()

    def write(self, relative, source):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-qm", "Immutable CodeQL selection fixture")
        return self.git("rev-parse", "HEAD")

    def test_complete_git_inventory_ignores_dirty_candidate_and_never_imports_candidate_code(self):
        self.write("tools/check.py", "raise RuntimeError('changed candidate must never be imported')\n")
        candidate = self.commit()
        self.write("browser/main.ts", "uncommitted worktree file is not the candidate object\n")
        plan = CODEQL.select_repository(self.root, self.base, candidate)
        self.assertEqual(plan["languages"], ["python"])
        self.assertEqual(plan["commits"], {"base": self.base, "candidate": candidate})
        self.assertEqual([change["path"] for change in plan["changes"]], ["tools/check.py"])
        self.assertEqual(plan, json.loads(json.dumps(plan)))

    def test_real_git_rename_delete_and_mode_changes_are_retained(self):
        original = self.git("rev-parse", "HEAD:tools/check.py")
        self.git("mv", "tools/check.py", "tools/renamed.py")
        (self.root / "tools/renamed.py").chmod(0o755)
        (self.root / "browser/main.ts").unlink()
        candidate = self.commit()
        plan = CODEQL.select_repository(self.root, self.base, candidate)
        self.assertTrue(plan["full_scan"])
        by_path = {change["path"]: change for change in plan["changes"]}
        self.assertIsNone(by_path["tools/check.py"]["after"])
        self.assertIsNone(by_path["browser/main.ts"]["after"])
        self.assertEqual(by_path["tools/renamed.py"]["after"], {"mode": "100755", "type": "blob", "sha": original})

    def test_unavailable_history_or_nonimmutable_reference_never_yields_partial_selection(self):
        for sha in ("HEAD", "a" * 40, "0" * 40, ""):
            with self.subTest(sha=sha):
                self.assertTrue(CODEQL.select_repository(self.root, sha, self.base)["full_scan"])
                self.assertTrue(CODEQL.select_repository(self.root, self.base, sha)["full_scan"])
        self.assertTrue(CODEQL.select_repository("/missing-repository", "", "", event="schedule")["full_scan"])

    def test_retarget_reselects_from_new_base_and_actual_merge_without_importing_sources(self):
        self.write('.github/workflows/codeql.yml',
                   (ROOT / 'tools/repository-checks/workflows/metadata-edits/codeql.yml').read_text())
        base = self.commit()
        for changes, expected in (({'app.py': 'raise RuntimeError("never import")\n'}, ['python']),
                                  ({'app.ts': 'export const value=2;\n'}, ['javascript-typescript']),
                                  ({'app.py': '# changed\n', 'app.ts': '// changed\n'}, list(CODEQL.LANGUAGES)),
                                  ({'unknown.input': 'unknown\n'}, list(CODEQL.LANGUAGES))):
            self.git('checkout', '-q', '--detach', base)
            for path, source in changes.items(): self.write(path, source)
            head = self.commit()
            merge = self.git('commit-tree', self.git('rev-parse', head + '^{tree}'),
                             '-p', base, '-p', head, '-m', 'Retarget exact merge fixture')
            with self.subTest(changes=changes):
                plan = CODEQL.select_repository(self.root, base, merge, event='pull_request')
                self.assertEqual(plan['languages'], expected)
                self.assertEqual(plan['commits'], {'base': base, 'candidate': merge})

    def pinned_native_base(self):
        self.write('.github/workflows/codeql.yml',
                   (ROOT/'tools/repository-checks/workflows/metadata-edits/codeql-pinned.yml').read_text())
        self.write('native/Example.cpp','int value = 1;\n')
        return self.commit()

    def test_python_control_uses_complete_target_delta_and_never_loads_candidate_controllers(self):
        self.write('.github/workflows/codeql.yml',
                   (ROOT/'tools/repository-checks/workflows/metadata-edits/codeql-pinned.yml').read_text())
        base = self.commit()
        self.write('tools/test-evidence/inputs.py', 'raise RuntimeError("never import candidate controls")\n')
        head = self.commit()
        merge = self.git('commit-tree', self.git('rev-parse', head+'^{tree}'), '-p', base, '-p', head,
                         '-m', 'Ordinary Python controller merge fixture')
        self.assertEqual(CODEQL.select_repository(self.root, base, merge)['languages'], ['python'])
        self.write('browser/main.ts', 'export const changedEarlier = true;\n')
        first_head = self.commit()
        self.write('tools/test-evidence/inputs.py', 'raise RuntimeError("corrective source still never imports")\n')
        second_head = self.commit()
        current_merge = self.git('commit-tree', self.git('rev-parse', second_head+'^{tree}'),
                                '-p', base, '-p', second_head, '-m', 'Whole PR retains earlier JavaScript change')
        # The prior-head delta is insufficient input for a PR decision.
        self.assertEqual(CODEQL.select_repository(self.root, first_head, second_head)['languages'], ['python'])
        plan = CODEQL.select_repository(self.root, base, current_merge)
        self.assertEqual(plan['languages'], list(CODEQL.LANGUAGES))
        self.assertEqual({row['path'] for row in plan['changes']}, {'browser/main.ts', 'tools/test-evidence/inputs.py'})
        self.write('tools/test-evidence/inputs.py', 'uncommitted candidate data never changes selection\n')
        self.assertEqual(CODEQL.select_repository(self.root, base, current_merge), plan)

    def test_real_native_blob_selection_ignores_dirty_checkout_and_bounds_unknown_inputs(self):
        base=self.pinned_native_base()
        self.write('native/Example.cpp','int value = 2;\n');head=self.commit()
        self.write('native/Example.cpp','#!/usr/bin/python\nraise RuntimeError("dirty source must never execute")\n')
        for event in ('pull_request','push'):
            plan=CODEQL.select_repository(self.root,base,head,event=event)
            self.assertEqual(plan['languages'],[])
            self.assertEqual([x['path'] for x in plan['changes']],['native/Example.cpp'])
        for constant,value in (('_NATIVE_BLOB_BYTES',1),('_NATIVE_TOTAL_BYTES',1),('_NATIVE_BLOB_COUNT',1)):
            with self.subTest(constant=constant),patch.object(CODEQL,constant,value):
                self.assertTrue(CODEQL.select_repository(self.root,base,head)['full_scan'])
        for variable in ('LGTM_INDEX_FILETYPES','CODEQL_EXTRACTOR_JAVASCRIPT_OPTION_TEST',
                         'CODEQL_EXTRACTOR_PYTHON_OPTION_TEST'):
            with self.subTest(variable=variable),patch.dict(CODEQL.os.environ,{variable:'unreviewed'}):
                self.assertTrue(CODEQL.select_repository(self.root,base,head)['full_scan'])

    def test_genuine_native_merge_keeps_historical_language_inputs_and_native_membership_changes(self):
        base=self.pinned_native_base()
        self.write('tools/history.py','# historical child difference\n');historical=self.commit()
        self.write('native/Example.cpp','int value = 2;\n');head=self.commit()
        merge=self.git('commit-tree',self.git('rev-parse',head+'^{tree}'),'-p',base,'-p',head,'-m','Full history merge fixture')
        plan=CODEQL.select_repository(self.root,base,merge)
        self.assertEqual(plan['languages'],['python'])
        self.assertEqual({x['path'] for x in plan['changes']},{'native/Example.cpp','tools/history.py'})
        self.git('checkout','-q','--detach',base)
        self.git('mv','native/Example.cpp','native/Renamed.cpp');renamed=self.commit()
        self.assertTrue(CODEQL.select_repository(self.root,base,renamed)['full_scan'])


RESULT_SPEC = importlib.util.spec_from_file_location("trusted_codeql_results", ROOT / "tools/repository-checks/codeql_results.py")
RESULTS = importlib.util.module_from_spec(RESULT_SPEC)
assert RESULT_SPEC.loader
RESULT_SPEC.loader.exec_module(RESULTS)


class FakeCodeScanningApi:
    """Authenticated server response fixture; never executes gh or a candidate."""
    def __init__(self, owner):
        self.owner, self.calls = owner, []
        self.error = None
        self.change = None

    def json(self, endpoint):
        from urllib.parse import parse_qs, urlsplit
        self.calls.append(endpoint)
        if self.error:
            raise self.error
        if self.change:
            self.change(endpoint)
        assert endpoint == RESULTS.PREFIX or endpoint.startswith(RESULTS.PREFIX + '/')
        parsed = urlsplit(endpoint[len(RESULTS.PREFIX):])
        path, query, o = parsed.path.lstrip('/'), parse_qs(parsed.query), self.owner
        objects = {'': o.repo, 'actions/workflows/codeql.yml': o.workflow,
                   'actions/runs/12': o.run, 'actions/runs/12/attempts/1': o.run,
                   'pulls/42': o.pr, 'commits/refs/pull/42/merge': o.merge}
        if path in objects:
            if path == 'commits/refs/pull/42/merge':
                assert query == {'per_page': ['1'], 'page': ['1']}
            return deepcopy(objects[path])
        if path.startswith('git/ref/'):
            ref = path[len('git/ref/'):]
            return {'ref': 'refs/' + ref, 'object': {'type': 'commit', 'sha': o.refs[ref]}}
        if path.startswith('git/commits/'):
            revision = path.removeprefix('git/commits/')
            return {'sha': revision, 'tree': {'sha': o.git('rev-parse', revision + '^{tree}')},
                    'parents': [{'sha': x} for x in o.git('show', '-s', '--format=%P', revision).split()]}
        if path.startswith('branches/'):
            ref = path[len('branches/'):]
            return {'name': ref, 'protected': True, 'commit': {'sha': o.refs['heads/' + ref]}}
        if path.startswith('compare/'):
            before, after = path[len('compare/'):].split('...')
            ancestor = o.git('merge-base', before, after)
            ahead = int(o.git('rev-list', '--count', before + '..' + after))
            behind = int(o.git('rev-list', '--count', after + '..' + before))
            return {'status': 'ahead' if ancestor == before and ahead else 'diverged',
                    'base_commit': {'sha': before}, 'merge_base_commit': {'sha': ancestor},
                    'ahead_by': ahead, 'behind_by': behind, 'total_commits': ahead,
                    'commits': [{'sha': after}], 'files': []}
        if path == 'actions/runs/12/attempts/1/jobs':
            items = o.jobs
            count = len(items) if o.job_total is None else o.job_total
            field = 'jobs'
        elif path == 'code-scanning/analyses':
            assert query['ref'] == [o.env['GITHUB_REF']] and query['tool_name'] == ['CodeQL']
            items, field = o.analyses, None
        elif path.startswith('code-scanning/analyses/'):
            return deepcopy(next(x for x in o.analyses if x['id'] == int(path.rsplit('/', 1)[1])))
        elif path == 'code-scanning/alerts':
            assert query['state'] == ['open'] and query['ref'] == [o.env['GITHUB_REF']]
            items, field = o.alerts, None
        elif path.startswith('code-scanning/alerts/') and path.endswith('/instances'):
            assert query['ref'] == [o.env['GITHUB_REF']]
            items, field = o.instances[int(path.split('/')[2])], None
        else:
            raise AssertionError('Unexpected fixed API endpoint: ' + path)
        page = int(query['page'][0])
        assert query['per_page'] == ['100']
        rows = deepcopy(items[(page - 1) * 100:page * 100])
        return {'total_count': count, field: rows} if field else rows


class SelectedResultTests(unittest.TestCase):
    git = ImmutableRepositoryTests.git
    write = ImmutableRepositoryTests.write
    commit = ImmutableRepositoryTests.commit

    def setUp(self):
        ImmutableRepositoryTests.setUp(self)
        self.write('tools/check.py', '# immutable changed Python source\n')
        self.head = self.commit()
        tree = self.git('rev-parse', 'HEAD^{tree}')
        self.candidate = self.git('commit-tree', tree, '-p', self.base, '-p', self.head, '-m', 'Exact merge fixture')
        self.git('checkout', '-q', '--detach', self.candidate)
        self.repo = {'id': RESULTS.REPOSITORY_ID, 'full_name': RESULTS.REPOSITORY, 'default_branch': 'main'}
        side = lambda ref, revision: {'ref': ref, 'sha': revision, 'repo': deepcopy(self.repo)}
        self.pr = {'number': 42, 'state': 'open', 'base': side('main', self.base),
                   'head': side('fix/main/example', self.head), 'merge_commit_sha': self.candidate}
        self.event = {'repository': deepcopy(self.repo), 'number': 42, 'pull_request': deepcopy(self.pr)}
        self.env = {'GITHUB_ACTIONS': 'true', 'GITHUB_REPOSITORY': RESULTS.REPOSITORY,
                    'GITHUB_REPOSITORY_ID': str(RESULTS.REPOSITORY_ID), 'GITHUB_EVENT_NAME': 'pull_request',
                    'GITHUB_SHA': self.candidate, 'GITHUB_RUN_ID': '12', 'GITHUB_RUN_ATTEMPT': '1',
                    'GITHUB_REF': 'refs/pull/42/merge', 'GITHUB_HEAD_REF': 'fix/main/example',
                    'GITHUB_BASE_REF': 'main', 'CODEQL_EXPECTED_LANGUAGES': '["python"]',
                    'GITHUB_WORKFLOW_SHA': self.candidate,
                    'GITHUB_WORKFLOW_REF': RESULTS.REPOSITORY + '/' + RESULTS.WORKFLOW + '@refs/pull/42/merge'}
        self.refs = {'heads/main': self.base, 'heads/fix/main/example': self.head, 'pull/42/merge': self.candidate}
        self.merge = {'sha': self.candidate, 'parents': [{'sha': self.base}, {'sha': self.head}]}
        self.workflow = {'id': 7, 'path': RESULTS.WORKFLOW, 'state': 'active'}
        self.run = {'id': 12, 'run_attempt': 1, 'workflow_id': 7, 'path': RESULTS.WORKFLOW,
                    'repository': deepcopy(self.repo), 'head_repository': deepcopy(self.repo),
                    'head_sha': self.head, 'head_branch': 'fix/main/example', 'event': 'pull_request',
                    'status': 'in_progress', 'conclusion': None, 'run_started_at': '2026-10-15T21:00:00Z'}
        self.jobs = [{'id': 81, 'name': 'CodeQL (python)', 'run_id': 12, 'run_attempt': 1,
                      'head_sha': self.head, 'status': 'completed', 'conclusion': 'success',
                      'started_at': '2026-10-15T21:00:01Z', 'completed_at': '2026-10-15T21:00:21Z',
                      'steps': [{'name': 'Analyze', 'status': 'completed', 'conclusion': 'success',
                                 'started_at': '2026-10-15T21:00:10Z', 'completed_at': '2026-10-15T21:00:20Z'}]}]
        self.jobs.append(dict(self.jobs[0], id=80, name='Select affected CodeQL languages', steps=[],
                              started_at='2026-10-15T21:00:00Z', completed_at='2026-10-15T21:00:01Z'))
        self.job_total = None
        self.analyses = [{'id': 91, 'ref': self.env['GITHUB_REF'], 'commit_sha': self.candidate,
                          'analysis_key': RESULTS.ANALYSIS_KEY, 'environment': '{"language":"python"}',
                          'category': '/language:python', 'error': '', 'rules_count': 43, 'results_count': 1,
                          'created_at': '2026-10-15T21:00:15Z', 'tool': {'name': 'CodeQL', 'version': '2.27.2'}}]
        self.alerts, self.instances = [], {}
        self.api = FakeCodeScanningApi(self)

    def verify(self, **options):
        return RESULTS.Verifier(self.root, self.event, self.env, api=self.api, **options).verify(processing_seconds=0)

    def regenerated_merge(self, *, tree=None, parents=None):
        tree = tree or self.git('rev-parse', self.candidate + '^{tree}')
        arguments = [arg for parent in (parents or [self.base, self.head]) for arg in ('-p', parent)]
        live = self.git('commit-tree', tree, *arguments, '-m', 'Regenerated GitHub test merge')
        self.merge = {'sha': live, 'parents': [{'sha': x} for x in (parents or [self.base, self.head])]}
        self.pr['merge_commit_sha'] = live
        return live

    def test_regenerated_test_merge_keeps_original_analysis_identity(self):
        live = self.regenerated_merge()
        self.assertNotEqual(live, self.candidate)
        result = self.verify()
        self.assertEqual(result['source_commit'], self.candidate)
        self.assertEqual(result['observed_merge_commits'], sorted([live, self.candidate]))
        self.assertEqual(self.analyses[0]['commit_sha'], self.candidate)

    def test_equivalent_regeneration_at_final_bookend_is_accepted(self):
        reads = [0]
        def regenerate(endpoint):
            if endpoint.endswith('/commits/refs/pull/42/merge?per_page=1&page=1'):
                reads[0] += 1
                if reads[0] == 2:
                    self.regenerated_merge()
        self.api.change = regenerate
        self.assertEqual(self.verify()['source_commit'], self.candidate)
        self.assertEqual(reads[0], 2)

    def test_regenerated_merge_with_changed_tree_or_ordered_parents_rejects(self):
        for shape in ('tree', 'reversed', 'extra', 'base', 'head'):
            self.setUp()
            parents = {'reversed': [self.head, self.base], 'extra': [self.base, self.head, self.candidate],
                       'base': [self.candidate, self.head], 'head': [self.base, self.candidate]}.get(shape)
            self.regenerated_merge(tree=self.git('rev-parse', self.base + '^{tree}') if shape == 'tree' else None,
                                   parents=parents)
            with self.subTest(shape=shape), self.assertRaises(RESULTS.ResultError):
                self.verify()

    def test_live_merge_cannot_replace_original_sarif_identity(self):
        live = self.regenerated_merge()
        self.analyses[0]['commit_sha'] = live
        with self.assertRaises(RESULTS.ResultError):
            self.verify()

    def pinned_policy_candidate(self, changed_path='.github/test-suites.json', extra_sources=None,
                                existing_sources=None,replacement='{"fixture":2}\n'):
        """Real immutable two-parent candidate; only fake authenticated API I/O."""
        self.write(RESULTS.WORKFLOW,
                   (ROOT / 'tools/repository-checks/workflows/metadata-edits/codeql-pinned.yml').read_text())
        for path in CODEQL._PYTHON_POLICY_JSONS | CODEQL._INERT_CI_JSONS: self.write(path, '{"fixture":1}\n')
        for path,source in (existing_sources or {}).items():self.write(path,source)
        self.base = self.commit()
        self.write(changed_path,replacement)
        for path, source in (extra_sources or {}).items(): self.write(path, source)
        self.head = self.commit()
        self.candidate = self.git('commit-tree', self.git('rev-parse', self.head + '^{tree}'),
                                  '-p', self.base, '-p', self.head, '-m', 'Pinned policy merge fixture')
        self.git('checkout', '-q', '--detach', self.candidate)
        self.pr['base']['sha'], self.pr['head']['sha'] = self.base, self.head
        self.pr['merge_commit_sha'] = self.candidate
        self.event['pull_request'] = deepcopy(self.pr)
        self.env.update(GITHUB_SHA=self.candidate, GITHUB_WORKFLOW_SHA=self.candidate)
        self.refs = {'heads/main': self.base, 'heads/fix/main/example': self.head, 'pull/42/merge': self.candidate}
        self.merge = {'sha': self.candidate, 'parents': [{'sha': self.base}, {'sha': self.head}]}
        self.run['head_sha'] = self.head
        for job in self.jobs: job['head_sha'] = self.head
        self.jobs[0]['steps'].insert(0, {'name': 'Require reviewed CodeQL extractor version',
            'status': 'completed', 'conclusion': 'success',
            'started_at': '2026-10-15T21:00:02Z', 'completed_at': '2026-10-15T21:00:03Z'})
        self.analyses[0]['commit_sha'] = self.candidate

    def test_pinned_native_edit_recomputed_from_real_git_still_requires_successful_current_selector(self):
        self.pinned_policy_candidate('native/Example.cpp',existing_sources={'native/Example.cpp':'int value = 1;\n'},
                                     replacement='int value = 2;\n')
        self.env['CODEQL_EXPECTED_LANGUAGES']='[]'
        selector=deepcopy(self.jobs[-1]);self.jobs,self.analyses=[selector],[]
        self.assertEqual(self.verify()['languages'],[])
        self.assertFalse(any('/code-scanning/' in call for call in self.api.calls))
        self.jobs[0]['conclusion']='failure'
        with self.assertRaises(RESULTS.ResultError):self.verify()
        self.jobs=[selector]
        self.env['CODEQL_EXPECTED_LANGUAGES']='["python"]'
        with self.assertRaisesRegex(RESULTS.ResultError,'caller language plan differs'):self.verify()

    def test_pinned_ci_metadata_uses_real_git_and_still_requires_current_successful_selector(self):
        self.pinned_policy_candidate('.github/branch-cleanup.json')
        self.env['CODEQL_EXPECTED_LANGUAGES'] = '[]'
        selector = deepcopy(self.jobs[-1])
        self.jobs, self.analyses = [selector], []
        self.write('browser/main.ts', '// dirty worktree never changes immutable selection\n')
        self.assertEqual(self.verify()['languages'], [])
        self.assertFalse(any('/code-scanning/' in call for call in self.api.calls))
        for mutation in ('missing', 'failure', 'skipped', 'stale-head', 'wrong-attempt', 'duplicate'):
            self.jobs = [deepcopy(selector)]
            if mutation == 'missing': self.jobs.clear()
            elif mutation == 'failure': self.jobs[0]['conclusion'] = 'failure'
            elif mutation == 'skipped': self.jobs[0]['conclusion'] = 'skipped'
            elif mutation == 'stale-head': self.jobs[0]['head_sha'] = self.base
            elif mutation == 'wrong-attempt': self.jobs[0]['run_attempt'] = 2
            else: self.jobs.append(deepcopy(selector))
            with self.subTest(mutation=mutation), self.assertRaises(RESULTS.ResultError): self.verify()

    def test_ci_metadata_cannot_hide_changed_python_or_an_open_current_python_finding(self):
        self.pinned_policy_candidate('.github/issue-policy.json', {'tools/check.py': '# changed Python\n'})
        self.env['CODEQL_EXPECTED_LANGUAGES'] = '[]'
        with self.assertRaisesRegex(RESULTS.ResultError, 'independent immutable selection'): self.verify()
        self.env['CODEQL_EXPECTED_LANGUAGES'] = '["python"]'
        self.assertEqual(self.verify()['languages'], ['python'])
        self.alerts = [{'number': 9, 'state': 'open', 'tool': {'name': 'CodeQL'}}]
        self.instances = {9: [{'ref': self.env['GITHUB_REF'], 'commit_sha': self.candidate,
            'category': '/language:python', 'state': 'open', 'analysis_key': RESULTS.ANALYSIS_KEY}]}
        with self.assertRaisesRegex(RESULTS.ResultError, 'open CodeQL finding'): self.verify()

    def test_lock_only_real_git_still_requires_a_fresh_successful_native_selector(self):
        path = 'browser-client/package-lock.json'
        self.pinned_policy_candidate(path, existing_sources={path: '{"lockfileVersion":3,"packages":{}}\n'})
        self.env['CODEQL_EXPECTED_LANGUAGES'] = '[]'
        selector = deepcopy(self.jobs[-1])
        self.jobs, self.analyses = [selector], []
        self.assertEqual(self.verify()['languages'], [])
        self.assertFalse(any('/code-scanning/' in call for call in self.api.calls))
        for mutation in ('missing', 'failure', 'skipped', 'stale-head', 'wrong-attempt', 'duplicate'):
            self.jobs = [deepcopy(selector)]
            if mutation == 'missing': self.jobs.clear()
            elif mutation in ('failure', 'skipped'): self.jobs[0]['conclusion'] = mutation
            elif mutation == 'stale-head': self.jobs[0]['head_sha'] = self.base
            elif mutation == 'wrong-attempt': self.jobs[0]['run_attempt'] = 2
            else: self.jobs.append(deepcopy(selector))
            with self.subTest(mutation=mutation), self.assertRaises(RESULTS.ResultError): self.verify()

    def test_lock_change_with_javascript_still_checks_current_analysis_and_findings(self):
        path = 'script-archive/marketplace/S3Server/package-lock.json'
        self.pinned_policy_candidate(path, {'browser/main.ts': 'const changed = true;\n'},
                                     existing_sources={path: '{"lockfileVersion":3,"packages":{}}\n'})
        self.env['CODEQL_EXPECTED_LANGUAGES'] = '[]'
        with self.assertRaises(RESULTS.ResultError): self.verify()
        self.env['CODEQL_EXPECTED_LANGUAGES'] = '["javascript-typescript"]'
        self.jobs[0]['name'] = 'CodeQL (javascript-typescript)'
        self.analyses[0].update(environment='{"language":"javascript-typescript"}', category='/language:javascript-typescript')
        self.assertEqual(self.verify()['languages'], ['javascript-typescript'])
        self.alerts = [{'number': 9, 'state': 'open', 'tool': {'name': 'CodeQL'}}]
        self.instances = {9: [{'ref': self.env['GITHUB_REF'], 'commit_sha': self.candidate,
            'category': '/language:javascript-typescript', 'state': 'open', 'analysis_key': RESULTS.ANALYSIS_KEY}]}
        with self.assertRaisesRegex(RESULTS.ResultError, 'open CodeQL finding'): self.verify()

    def test_pinned_policy_json_uses_python_results_bound_to_actual_candidate_and_extractor(self):
        old_candidate = self.candidate
        self.pinned_policy_candidate()
        # Worktree content and supplied languages cannot replace Git object selection.
        self.write('browser/main.ts', '// dirty JavaScript is outside the candidate\n')
        self.assertEqual(self.verify()['languages'], ['python'])
        self.env['CODEQL_EXPECTED_LANGUAGES'] = '[]'
        with self.assertRaisesRegex(RESULTS.ResultError, 'independent immutable selection'): self.verify()
        self.env['CODEQL_EXPECTED_LANGUAGES'] = '["python"]'
        self.analyses[0]['commit_sha'] = old_candidate
        with self.assertRaises(RESULTS.ResultError): self.verify()
        self.analyses[0]['commit_sha'] = self.candidate
        for version in ('2.27.1', '2.27.3', None):
            self.analyses[0]['tool']['version'] = version
            with self.subTest(version=version), self.assertRaisesRegex(RESULTS.ResultError, 'reviewed extractor version'):
                self.verify()

    def test_pinned_result_requires_the_successful_version_step_before_analysis(self):
        self.pinned_policy_candidate()
        original = deepcopy(self.jobs[0]['steps'])
        mutations = [original[1:], original + [original[0]]]
        for key, value in (('conclusion', 'failure'), ('status', 'in_progress'),
                           ('started_at', '2026-10-15T21:00:12Z'),
                           ('completed_at', '2026-10-15T21:00:11Z')):
            changed = deepcopy(original); changed[0][key] = value; mutations.append(changed)
        for steps in mutations:
            self.jobs[0]['steps'] = steps
            with self.subTest(steps=steps), self.assertRaises(RESULTS.ResultError): self.verify()
        self.jobs[0]['steps'] = original
        self.assertEqual(self.verify()['languages'], ['python'])

    def test_pinned_policy_json_keeps_current_python_findings_required(self):
        self.pinned_policy_candidate()
        self.alerts = [{'number': 9, 'state': 'open', 'tool': {'name': 'CodeQL'}}]
        self.instances = {9: [{'ref': self.env['GITHUB_REF'], 'commit_sha': self.candidate,
            'category': '/language:python', 'state': 'open', 'analysis_key': RESULTS.ANALYSIS_KEY}]}
        with self.assertRaisesRegex(RESULTS.ResultError, 'open CodeQL finding'): self.verify()

    def test_pinned_python_control_still_requires_current_analysis_and_cannot_hide_failed_or_pending_jobs(self):
        self.pinned_policy_candidate('tools/test-evidence/inputs.py', replacement='raise RuntimeError("never import")\n')
        self.assertEqual(self.verify()['languages'], ['python'])
        self.env['CODEQL_EXPECTED_LANGUAGES'] = '[]'
        with self.assertRaisesRegex(RESULTS.ResultError, 'independent immutable selection'): self.verify()
        self.env['CODEQL_EXPECTED_LANGUAGES'] = '["python"]'
        original = deepcopy(self.jobs)
        for conclusion, status in (('failure', 'completed'), (None, 'in_progress')):
            self.jobs = deepcopy(original); self.jobs[0].update(conclusion=conclusion, status=status)
            with self.subTest(conclusion=conclusion, status=status), self.assertRaises(RESULTS.ResultError): self.verify()
        self.jobs = original
        self.analyses[0]['commit_sha'] = self.base
        with self.assertRaises(RESULTS.ResultError): self.verify()

    def test_pinned_result_verifier_independently_rejects_every_older_result_workflow(self):
        self.pinned_policy_candidate()
        for template in ('codeql-results.yml', 'metadata-edits/codeql.yml'):
            self.git('checkout', '-q', '--detach', self.base)
            self.write(RESULTS.WORKFLOW, (ROOT / 'tools/repository-checks/workflows' / template).read_text())
            head = self.commit()
            candidate = self.git('commit-tree', self.git('rev-parse', head + '^{tree}'),
                                 '-p', self.base, '-p', head, '-m', 'Reject pinned rollback fixture')
            self.git('checkout', '-q', '--detach', candidate)
            self.event['pull_request']['base']['sha'] = self.base
            self.event['pull_request']['head']['sha'] = head
            env = dict(self.env, GITHUB_SHA=candidate, GITHUB_WORKFLOW_SHA=candidate,
                       CODEQL_EXPECTED_LANGUAGES='["javascript-typescript","python"]')
            with self.subTest(template=template), self.assertRaisesRegex(RESULTS.ResultError, 'cannot be reverted'):
                RESULTS.Verifier(self.root, self.event, env, api=self.api).plan()

    def test_real_immutable_selection_success_accepts_nonzero_dismissed_result_count(self):
        result = self.verify()
        self.assertEqual(result['languages'], ['python'])
        self.assertEqual(result['analyses'], [{'id': 91, 'category': '/language:python', 'rules_count': 43, 'job_id': 81}])
        self.assertEqual(result['open_selected_findings'], 0)
        self.assertEqual(self.api.calls.count(RESULTS.PREFIX + '/pulls/42'), 2)
        self.assertNotIn('results_count', json.dumps(result))
        self.assertNotIn('location', json.dumps(result))

    def test_server_workflow_identity_and_fresh_api_replace_unreliable_event_merge_field(self):
        for event_merge in (None, self.base):
            self.event['pull_request']['merge_commit_sha'] = event_merge
            self.assertEqual(self.verify()['languages'], ['python'])
        self.assertFalse(any('/git/ref/pull/' in call for call in self.api.calls))
        for key, value in [('GITHUB_WORKFLOW_SHA', self.base),
                           ('GITHUB_WORKFLOW_REF', RESULTS.REPOSITORY + '/' + RESULTS.WORKFLOW + '@refs/heads/main')]:
            old = self.env[key]
            self.env[key] = value
            with self.subTest(key=key):
                with self.assertRaisesRegex(RESULTS.ResultError, 'executed workflow source'):
                    self.verify()
            self.env[key] = old

    def test_latest_api_without_merge_sha_requires_the_current_ref_and_ordered_parents(self):
        del self.pr['merge_commit_sha']
        self.assertEqual(self.verify()['languages'], ['python'])
        self.assertEqual(self.api.calls.count(RESULTS.PREFIX + '/commits/refs/pull/42/merge?per_page=1&page=1'), 2)
        self.merge['sha'] = self.base
        with self.assertRaisesRegex(RESULTS.ResultError, 'ordered merge parents'):
            self.verify()
        self.merge['sha'] = self.candidate
        self.merge['parents'] = [{'sha': self.head}, {'sha': self.base}]
        with self.assertRaisesRegex(RESULTS.ResultError, 'ordered merge parents'):
            self.verify()

    def test_live_merge_ref_advancement_is_rejected_at_the_final_bookend(self):
        del self.pr['merge_commit_sha']
        seen = [0]
        def advance(endpoint):
            if endpoint.endswith('/commits/refs/pull/42/merge?per_page=1&page=1'):
                seen[0] += 1
                if seen[0] == 2:
                    self.merge['sha'] = self.base
        self.api.change = advance
        with self.assertRaisesRegex(RESULTS.ResultError, 'ordered merge parents'):
            self.verify()
        self.assertEqual(seen[0], 2)

    def test_original_child_workflow_is_base_only_and_unknown_workflows_still_reject(self):
        workflow = RESULTS.WORKFLOW
        original = 'name: Original child workflow fixture\non: push\njobs: {}\n'
        self.git('checkout', '-q', '--detach', self.base)
        self.write(workflow, original)
        base = self.commit()
        original_blob = self.git('rev-parse', base + ':' + workflow)
        self.write(workflow, (ROOT / workflow).read_text())
        head = self.commit()

        def select_at_merge(head):
            candidate = self.git('commit-tree', self.git('rev-parse', head + '^{tree}'),
                                 '-p', base, '-p', head, '-m', 'Child workflow transition fixture')
            self.git('checkout', '-q', '--detach', candidate)
            self.pr['base']['sha'], self.pr['head']['sha'] = base, head
            self.event['pull_request'] = deepcopy(self.pr)
            env = dict(self.env, GITHUB_SHA=candidate, GITHUB_WORKFLOW_SHA=candidate,
                       CODEQL_EXPECTED_LANGUAGES='["javascript-typescript","python"]')
            return RESULTS.Verifier(self.root, self.event, env, api=self.api).plan()

        # A synthetic approved baseline avoids relying on historical objects in
        # hosted shallow checkouts; the real six base blobs are checked offline.
        with patch.dict(RESULTS.codeql._REVIEWED_CONTROLS, {workflow: original_blob}):
            self.assertEqual(select_at_merge(head), ['javascript-typescript', 'python'])
        with self.assertRaisesRegex(RESULTS.ResultError, 'not approved'):
            select_at_merge(head)
        self.write(workflow, original)
        legacy_head = self.commit()
        with patch.dict(RESULTS.codeql._REVIEWED_CONTROLS, {workflow: original_blob}):
            with self.assertRaisesRegex(RESULTS.ResultError, 'not approved'):
                select_at_merge(legacy_head)

    def test_candidate_json_cannot_choose_languages_or_import_policy(self):
        self.event['languages'] = []
        self.env['CODEQL_EXPECTED_LANGUAGES'] = '[]'
        with self.assertRaisesRegex(RESULTS.ResultError, 'independent immutable selection'):
            self.verify()

    def test_selected_result_plan_rejects_deployed_successor_rollback_independently(self):
        workflow = RESULTS.WORKFLOW
        self.write(workflow, (ROOT / 'tools/repository-checks/workflows/metadata-edits/codeql.yml').read_text())
        base = self.commit()
        self.write(workflow, (ROOT / 'tools/repository-checks/workflows/codeql-results.yml').read_text())
        head = self.commit()
        candidate = self.git('commit-tree', self.git('rev-parse', head + '^{tree}'),
                             '-p', base, '-p', head, '-m', 'Forbidden rollback fixture')
        self.git('checkout', '-q', '--detach', candidate)
        self.event['pull_request']['base']['sha'] = base
        self.event['pull_request']['head']['sha'] = head
        env = dict(self.env, GITHUB_SHA=candidate, GITHUB_WORKFLOW_SHA=candidate,
                   CODEQL_EXPECTED_LANGUAGES='["javascript-typescript","python"]')
        with self.assertRaisesRegex(RESULTS.ResultError, 'cannot be reverted'):
            RESULTS.Verifier(self.root, self.event, env, api=self.api).plan()

    def test_successor_retarget_verifies_current_candidate_results_and_rejects_old_sarif(self):
        old_candidate = self.candidate
        self.write(RESULTS.WORKFLOW, (ROOT / 'tools/repository-checks/workflows/metadata-edits/codeql.yml').read_text())
        self.base = self.commit()
        self.write('tools/check.py', '# changed Python after retarget baseline\n')
        self.head = self.commit()
        self.candidate = self.git('commit-tree', self.git('rev-parse', self.head + '^{tree}'),
                                  '-p', self.base, '-p', self.head, '-m', 'Current retarget merge fixture')
        self.git('checkout', '-q', '--detach', self.candidate)
        self.pr['base'].update(ref='apple-main', sha=self.base)
        self.pr['head']['sha'] = self.head
        self.pr['merge_commit_sha'] = self.candidate
        self.event.update(action='edited', changes={'base': {'ref': {'from': 'main'},
                                                            'sha': {'from': '1' * 40}}},
                          pull_request=deepcopy(self.pr))
        self.env.update(GITHUB_SHA=self.candidate, GITHUB_WORKFLOW_SHA=self.candidate, GITHUB_BASE_REF='apple-main')
        self.refs = {'heads/apple-main': self.base, 'heads/fix/main/example': self.head,
                     'pull/42/merge': self.candidate}
        self.merge = {'sha': self.candidate, 'parents': [{'sha': self.base}, {'sha': self.head}]}
        self.run['head_sha'] = self.head
        for job in self.jobs: job['head_sha'] = self.head
        self.analyses[0]['commit_sha'] = self.candidate
        self.assertEqual(self.verify()['languages'], ['python'])
        self.analyses[0]['commit_sha'] = old_candidate
        with self.assertRaises(RESULTS.ResultError): self.verify()

    def test_unknown_duplicate_languages_and_foreign_actions_repository_reject(self):
        for key, value in [('CODEQL_EXPECTED_LANGUAGES', '["python","python"]'),
                           ('CODEQL_EXPECTED_LANGUAGES', '["ruby"]'),
                           ('GITHUB_REPOSITORY', 'overte-org/overte'), ('GITHUB_RUN_ATTEMPT', '2')]:
            with self.subTest(key=key, value=value):
                env = dict(self.env, **{key: value})
                with self.assertRaises(RESULTS.ResultError):
                    RESULTS.Verifier(self.root, self.event, env, api=self.api).verify(processing_seconds=0)

    def test_foreign_api_repository_and_workflow_identity_reject(self):
        for target, key, value in [(self.run['repository'], 'full_name', 'overte-org/overte'),
                                   (self.run['head_repository'], 'id', 1),
                                   (self.run, 'workflow_id', 8), (self.run, 'path', '.github/workflows/fake.yml'),
                                   (self.run, 'head_sha', self.base), (self.run, 'run_attempt', 2)]:
            old = target[key]
            with self.subTest(key=key):
                target[key] = value
                with self.assertRaises(RESULTS.ResultError): self.verify()
                target[key] = old

    def test_failed_skipped_missing_duplicate_and_carried_old_jobs_reject(self):
        original = deepcopy(self.jobs)
        mutations = [[], original * 2]
        for key, value in [('conclusion', 'failure'), ('conclusion', 'skipped'), ('status', 'in_progress'),
                           ('run_attempt', 2), ('conclusion', 'cancelled'), ('head_sha', self.base), ('started_at', '2026-10-14T21:00:01Z')]:
            row = deepcopy(original[0]); row[key] = value
            mutations.append([row])
        for jobs in mutations:
            with self.subTest(jobs=jobs):
                self.jobs = jobs
                with self.assertRaises(RESULTS.ResultError): self.verify()
        self.jobs = original
        self.jobs[0]['steps'][0]['conclusion'] = 'skipped'
        with self.assertRaises(RESULTS.ResultError): self.verify()

    def test_stale_or_missing_analysis_wrong_category_environment_errors_and_zero_rules_reject(self):
        original = deepcopy(self.analyses[0])
        changes = [('commit_sha', self.base), ('category', '/language:javascript-typescript'),
                   ('environment', '{"language":"python","other":true}'), ('analysis_key', 'other:analyze'),
                   ('error', 'extractor failed'), ('rules_count', 0), ('rules_count', True),
                   ('created_at', '2026-10-15T20:59:00Z'), ('ref', 'refs/heads/main'),
                   ('tool', {'name': 'different'})]
        for key, value in changes:
            with self.subTest(key=key):
                self.analyses = [dict(original, **{key: value})]
                with self.assertRaises(RESULTS.ResultError): self.verify()
        self.analyses = []
        with self.assertRaises(RESULTS.ResultError): self.verify()
        self.analyses = [original, dict(original, id=92)]
        with self.assertRaisesRegex(RESULTS.ResultError, 'ambiguous'): self.verify()

    def test_any_open_selected_finding_blocks_without_severity_threshold(self):
        self.alerts = [{'number': 9, 'state': 'open', 'tool': {'name': 'CodeQL'}}]
        self.instances = {9: [{'ref': self.env['GITHUB_REF'], 'commit_sha': self.candidate,
                               'category': '/language:python', 'state': 'open', 'analysis_key': RESULTS.ANALYSIS_KEY}]}
        with self.assertRaisesRegex(RESULTS.ResultError, 'open CodeQL finding'): self.verify()
        self.instances[9][0]['commit_sha'] = self.base
        with self.assertRaisesRegex(RESULTS.ResultError, 'stale'): self.verify()
        self.instances[9][0]['state'] = 'fixed'
        self.assertEqual(self.verify()['open_selected_findings'], 0)
        self.instances[9][0]['state'] = 'dismissed'
        self.assertEqual(self.verify()['open_selected_findings'], 0)
        self.instances[9][0]['state'] = 'open'
        self.instances[9][0]['category'] = '/language:javascript-typescript'
        self.assertEqual(self.verify()['open_selected_findings'], 0)

    def test_changed_pr_branch_refs_merge_and_ordered_parents_reject(self):
        for target, key, value in [(self.pr['base'], 'sha', self.head), (self.pr['head'], 'ref', 'foreign'),
                                   (self.pr, 'merge_commit_sha', self.head), (self.refs, 'heads/main', self.head),
                                   (self.refs, 'heads/fix/main/example', self.base),
                                   (self.merge, 'parents', [{'sha': self.head}, {'sha': self.base}])]:
            old = deepcopy(target[key]); target[key] = value
            with self.subTest(key=key):
                with self.assertRaises(RESULTS.ResultError): self.verify()
            target[key] = old

    def test_fresh_bookends_reject_pr_advancement_future_attempt_and_analysis_replacement(self):
        for mutation in ('pr', 'attempt', 'analysis'):
            seen = [0]
            def change(endpoint):
                trigger = '/pulls/42' if mutation == 'pr' else '/actions/runs/12' if mutation == 'attempt' else '/code-scanning/analyses/91'
                if endpoint.endswith(trigger):
                    seen[0] += 1
                    if mutation == 'pr' and seen[0] == 2: self.pr['head']['sha'] = self.base
                    if mutation == 'attempt' and seen[0] == 2: self.run['run_attempt'] = 2
                    if mutation == 'analysis': self.analyses[0]['rules_count'] += 1
            self.api.change = change
            with self.subTest(mutation=mutation):
                with self.assertRaises(RESULTS.ResultError): self.verify()
            self.pr['head']['sha'] = self.head; self.run['run_attempt'] = 1; self.analyses[0]['rules_count'] = 43

    def test_all_pages_are_read_for_analyses_alerts_instances_and_jobs(self):
        self.jobs = [dict(self.jobs[0], id=1000 + i, name='unrelated') for i in range(100)] + self.jobs
        self.analyses = [dict(self.analyses[0], id=2000 + i, commit_sha=self.base) for i in range(100)] + self.analyses
        self.alerts = [{'number': i, 'state': 'open', 'tool': {'name': 'CodeQL'}} for i in range(1, 102)]
        self.instances = {i: [{'ref': self.env['GITHUB_REF'], 'commit_sha': self.candidate,
                              'category': '/language:javascript-typescript', 'state': 'open'}] for i in range(1, 102)}
        self.instances[101] = [dict(self.instances[101][0], ordinal=i) for i in range(100)] + [
            {'ref': self.env['GITHUB_REF'], 'commit_sha': self.candidate, 'category': '/language:python', 'state': 'open'}]
        with self.assertRaisesRegex(RESULTS.ResultError, 'open CodeQL finding'): self.verify()
        for endpoint in ('/jobs?', '/analyses?', '/alerts?', '/101/instances?'):
            self.assertTrue(any(endpoint in call and 'page=2' in call for call in self.api.calls), endpoint)

    def test_truncated_counted_inventory_and_api_errors_never_become_success_or_poll(self):
        self.job_total = len(self.jobs) + 1
        with self.assertRaisesRegex(RESULTS.ResultError, 'truncated'): self.verify()
        self.job_total = None
        self.api.error = RuntimeError('fake HTTP 403')
        with self.assertRaises(RuntimeError): self.verify()

    def test_repeated_and_excessive_array_pagination_reject_incomplete_inventory(self):
        record = deepcopy(self.analyses[0])
        self.analyses = [dict(record, id=1000 + index, commit_sha=self.base) for index in range(1000)]
        with self.assertRaisesRegex(RESULTS.ResultError, 'bounded pagination'): self.verify()
        self.analyses = [record, deepcopy(record)]
        with self.assertRaisesRegex(RESULTS.ResultError, 'repeated API'): self.verify()

    def test_only_missing_sarif_processing_can_poll_then_current_results_must_arrive(self):
        clock = [0]
        saved = deepcopy(self.analyses)
        self.analyses = []
        def sleep(seconds):
            clock[0] += seconds
            self.analyses = deepcopy(saved)
        result = RESULTS.Verifier(self.root, self.event, self.env, api=self.api,
                                  clock=lambda: clock[0], sleep=sleep).verify(processing_seconds=5)
        self.assertEqual(clock[0], 5)
        self.assertEqual(result['languages'], ['python'])

    def test_empty_languages_still_require_current_selector_success_but_no_analysis_or_alert_api(self):
        self.git('checkout', '-q', '--detach', self.base)
        self.write('docs/design.md', 'Changed Markdown only\n')
        self.head = self.commit()
        self.candidate = self.git('commit-tree', self.git('rev-parse', 'HEAD^{tree}'),
                                  '-p', self.base, '-p', self.head, '-m', 'Documentation merge')
        self.git('checkout', '-q', '--detach', self.candidate)
        self.env.update(CODEQL_EXPECTED_LANGUAGES='[]', GITHUB_SHA=self.candidate, GITHUB_WORKFLOW_SHA=self.candidate)
        self.pr['head']['sha'] = self.head
        self.pr['merge_commit_sha'] = self.candidate
        self.event['pull_request'] = deepcopy(self.pr)
        self.refs.update({'heads/fix/main/example': self.head, 'pull/42/merge': self.candidate})
        self.merge = {'sha': self.candidate, 'parents': [{'sha': self.base}, {'sha': self.head}]}
        self.run['head_sha'] = self.head
        self.jobs = [dict(self.jobs[-1], head_sha=self.head)]
        self.analyses = []
        self.assertEqual(self.verify()['analyses'], [])
        self.assertFalse(any('/code-scanning/' in call for call in self.api.calls))
        self.jobs[0]['conclusion'] = 'failure'
        with self.assertRaises(RESULTS.ResultError): self.verify()

    def test_seven_permanent_pr_targets_are_bound_and_arbitrary_target_is_rejected(self):
        for target in sorted(RESULTS.TARGETS):
            self.env['GITHUB_BASE_REF'] = target
            self.event['pull_request']['base']['ref'] = target
            self.pr['base']['ref'] = target
            self.refs['heads/' + target] = self.base
            with self.subTest(target=target):
                self.assertEqual(self.verify()['languages'], ['python'])
        self.env['GITHUB_BASE_REF'] = 'unreviewed-target'
        self.event['pull_request']['base']['ref'] = 'unreviewed-target'
        with self.assertRaisesRegex(RESULTS.ResultError, 'permanent target'):
            self.verify()

    def test_all_seven_push_targets_require_their_actual_branch_source(self):
        self.env.update(GITHUB_EVENT_NAME='push', GITHUB_REF_TYPE='branch')
        self.run.update(event='push', head_sha=self.candidate)
        for job in self.jobs: job['head_sha'] = self.candidate
        for target in sorted(RESULTS.TARGETS):
            ref = 'refs/heads/' + target
            self.env['GITHUB_REF'] = ref
            self.env['GITHUB_WORKFLOW_REF'] = RESULTS.REPOSITORY + '/' + RESULTS.WORKFLOW + '@' + ref
            self.event = {'repository': deepcopy(self.repo), 'before': self.base, 'after': self.candidate,
                          'deleted': False, 'ref': ref}
            self.refs['heads/' + target] = self.candidate
            self.run['head_branch'] = target
            self.analyses[0]['ref'] = ref
            with self.subTest(target=target):
                self.assertEqual(self.verify()['languages'], ['python'])

    def test_cli_uses_only_server_event_and_withholds_untrusted_error_details(self):
        from contextlib import redirect_stdout, redirect_stderr
        import io
        import os
        import sys
        from unittest.mock import patch
        event_file = self.root / 'server-event.json'
        event_file.write_text(json.dumps(self.event))
        env = {**self.env, 'GITHUB_EVENT_PATH': str(event_file)}
        output, errors = io.StringIO(), io.StringIO()
        arguments = ['codeql_results.py', '--root', str(self.root), '--event-file', str(event_file)]
        with patch.dict(os.environ, env), patch.object(sys, 'argv', arguments), \
                patch.object(RESULTS, 'default_api', return_value=self.api), \
                redirect_stdout(output), redirect_stderr(errors):
            self.assertEqual(RESULTS.main(), 0)
        self.assertEqual(json.loads(output.getvalue())['languages'], ['python'])
        self.assertEqual(errors.getvalue(), '')
        self.api.error = RuntimeError('fake private API response must not appear')
        output, errors = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, env), patch.object(sys, 'argv', arguments), \
                patch.object(RESULTS, 'default_api', return_value=self.api), \
                redirect_stdout(output), redirect_stderr(errors):
            self.assertEqual(RESULTS.main(), 1)
        self.assertEqual(output.getvalue(), '')
        self.assertNotIn('fake private', errors.getvalue())
        self.assertIn('phase=current-context code=runtime-error;', errors.getvalue())

    def test_cli_failure_stage_identifies_actual_failed_gate_without_disclosing_details(self):
        from contextlib import redirect_stdout, redirect_stderr
        import io, os, sys
        event_file = self.root / 'server-event.json'
        event_file.write_text(json.dumps(self.event))
        env = {**self.env, 'GITHUB_EVENT_PATH': str(event_file)}
        arguments = ['codeql_results.py', '--root', str(self.root), '--event-file', str(event_file)]
        original_jobs = deepcopy(self.jobs)
        for failure, phase in [('failed-job','selected-jobs'), ('open-finding','selected-findings'),
                               ('invalid-event','server-event'), ('invalid-invocation','invocation')]:
            self.jobs=deepcopy(original_jobs);self.alerts=[];self.instances={}
            event_file.write_text(json.dumps(self.event))
            current_env=dict(env)
            if failure=='failed-job':self.jobs[0]['conclusion']='failure'
            elif failure=='open-finding':
                self.alerts=[{'number':1,'state':'open','tool':{'name':'CodeQL'},'private':'private fixture'}]
                self.instances[1]=[{'ref':self.env['GITHUB_REF'],'category':'/language:python',
                                   'state':'open','commit_sha':self.candidate}]
            elif failure=='invalid-event':event_file.write_text('{"private fixture":')
            else:current_env['GITHUB_REPOSITORY']='private fixture'
            output,errors=io.StringIO(),io.StringIO()
            with self.subTest(failure=failure), patch.dict(os.environ,current_env), patch.object(sys,'argv',arguments), \
                    patch.object(RESULTS,'default_api',return_value=self.api), redirect_stdout(output),redirect_stderr(errors):
                self.assertEqual(RESULTS.main(),1)
            self.assertEqual(output.getvalue(),'')
            self.assertIn('phase='+phase+' code=',errors.getvalue())
            self.assertNotIn('private fixture',errors.getvalue())
            self.assertNotIn(str(event_file),errors.getvalue())
            self.assertFalse(any('sarif' in endpoint.lower() for endpoint in self.api.calls))

    def test_push_and_schedule_bind_exact_branch_run_source_and_selection(self):
        for event_name in ('push', 'schedule'):
            with self.subTest(event=event_name):
                self.env.update(GITHUB_EVENT_NAME=event_name, GITHUB_REF='refs/heads/main', GITHUB_REF_TYPE='branch',
                                GITHUB_WORKFLOW_REF=RESULTS.REPOSITORY + '/' + RESULTS.WORKFLOW + '@refs/heads/main')
                self.event = {'repository': deepcopy(self.repo), 'before': self.base, 'after': self.candidate,
                              'deleted': False, 'ref': 'refs/heads/main'}
                self.refs['heads/main'] = self.candidate
                self.run.update(event=event_name, head_sha=self.candidate, head_branch='main')
                for job in self.jobs: job['head_sha'] = self.candidate
                self.analyses[0].update(ref='refs/heads/main')
                if event_name == 'schedule':
                    self.env['CODEQL_EXPECTED_LANGUAGES'] = json.dumps(list(CODEQL.LANGUAGES))
                    js = dict(self.jobs[0], id=82, name='CodeQL (javascript-typescript)')
                    self.jobs.append(js)
                    self.analyses.append(dict(self.analyses[0], id=92, category='/language:javascript-typescript',
                                              environment='{"language":"javascript-typescript"}'))
                self.assertEqual(self.verify()['languages'], json.loads(self.env['CODEQL_EXPECTED_LANGUAGES']))
                self.refs['heads/main'] = self.base
                with self.assertRaisesRegex(RESULTS.ResultError, 'advanced'): self.verify()



class EffectiveBaseResultTests(unittest.TestCase):
    git = ImmutableRepositoryTests.git
    write = ImmutableRepositoryTests.write
    commit = ImmutableRepositoryTests.commit
    verify = SelectedResultTests.verify

    def setUp(self):
        SelectedResultTests.setUp(self)
        snapshot = self.base
        self.git('checkout', '-q', '--detach', snapshot)
        self.write('browser/main.ts', 'export const value = 2;\n')
        live = self.commit()
        self.write('tools/check.py', '# Only this Python input is newly changed\n')
        self.head = self.commit()
        tree = self.git('rev-parse', 'HEAD^{tree}')
        self.candidate = self.git('commit-tree', tree, '-p', live, '-p', self.head, '-m', 'Current native merge')
        self.git('checkout', '-q', '--detach', self.candidate)
        self.live_base, self.snapshot = live, snapshot
        self.pr['head']['sha'] = self.head
        self.pr['merge_commit_sha'] = self.candidate
        self.event['pull_request'] = deepcopy(self.pr)
        self.env.update(GITHUB_SHA=self.candidate, GITHUB_WORKFLOW_SHA=self.candidate)
        self.refs.update({'heads/main': live, 'heads/fix/main/example': self.head, 'pull/42/merge': self.candidate})
        self.merge = {'sha': self.candidate, 'parents': [{'sha': live}, {'sha': self.head}]}
        self.run['head_sha'] = self.head
        for job in self.jobs: job['head_sha'] = self.head
        self.analyses[0]['commit_sha'] = self.candidate
        original = self.api
        self.ancestry_valid = True
        owner = self
        class CurrentApi:
            def json(self, endpoint):
                prefix = RESULTS.PREFIX + '/'
                path = endpoint.removeprefix(prefix)
                if path == 'branches/main':
                    return {'name': 'main', 'protected': True, 'commit': {'sha': owner.refs['heads/main']}}
                if path.startswith('compare/'):
                    return {'status': 'ahead' if owner.ancestry_valid else 'diverged',
                            'base_commit': {'sha': snapshot}, 'merge_base_commit': {'sha': snapshot},
                            'ahead_by': 1, 'behind_by': 0, 'total_commits': 1,
                            'commits': [{'sha': live}], 'files': []}
                if path == 'git/ref/heads/fix%2Fmain%2Fexample':
                    return {'ref': 'refs/heads/fix/main/example', 'object': {'type': 'commit', 'sha': owner.head}}
                return original.json(endpoint)
        self.api = CurrentApi()

    def test_native_cli_selects_live_parent_delta_without_reexecuting_integrated_javascript(self):
        event_file = Path(self.temporary.name) / 'native-event.json'
        event_file.write_text(json.dumps(self.event))
        with patch.dict('os.environ', {**self.env, 'GITHUB_EVENT_PATH': str(event_file)}, clear=True):
            actual = CODEQL.cli_repository_plan(self.root, self.snapshot, self.candidate, event='pull_request')
        self.assertEqual(actual['languages'], ['python'])
        self.assertEqual(actual['commits']['base'], self.live_base)
        self.assertEqual(CODEQL.select_repository(self.root, self.snapshot, self.candidate)['languages'],
                         ['javascript-typescript', 'python'])
        # The hosted depth-two checkout genuinely lacks the older event object.
        # Provisional planning still uses M.parent0; final API ancestry remains
        # mandatory in the independent verifier below.
        shallow = Path(self.temporary.name) / 'depth-two'
        subprocess.run(['git', 'clone', '--quiet', '--no-local', '--depth=2', str(self.root), str(shallow)],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        absent = subprocess.run(['git', 'cat-file', '-e', self.snapshot], cwd=shallow,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertNotEqual(absent.returncode, 0)
        self.assertFalse((shallow / '.git/objects/info/alternates').exists())
        with patch.dict('os.environ', {**self.env, 'GITHUB_EVENT_PATH': str(event_file)}, clear=True):
            self.assertEqual(CODEQL.cli_repository_plan(shallow, self.snapshot, self.candidate, event='pull_request'), actual)
        with patch.dict('os.environ', {}, clear=True):
            self.assertEqual(CODEQL.cli_repository_plan(self.root, self.snapshot, self.candidate, event='pull_request'),
                             CODEQL.select_repository(self.root, self.snapshot, self.candidate))

    def test_final_native_verifier_rederives_live_base_and_rejects_nonancestor_snapshot(self):
        self.assertEqual(self.verify()['languages'], ['python'])
        self.pr['base']['sha'] = self.live_base
        self.assertEqual(self.verify()['languages'], ['python'])
        self.ancestry_valid = False
        with self.assertRaises(RESULTS.ResultError): self.verify()

    def test_native_provisional_context_and_final_language_claim_cannot_be_forged(self):
        event_file = Path(self.temporary.name) / 'native-event.json'
        event_file.write_text(json.dumps(self.event))
        for key, value in (('GITHUB_SHA', self.head), ('GITHUB_WORKFLOW_SHA', self.head),
                           ('GITHUB_REPOSITORY', 'elsewhere/overte'), ('GITHUB_EVENT_NAME', 'workflow_dispatch')):
            env = {**self.env, 'GITHUB_EVENT_PATH': str(event_file), key: value}
            with self.subTest(key=key), patch.dict('os.environ', env, clear=True):
                with self.assertRaises(ValueError):
                    CODEQL.cli_repository_plan(self.root, self.snapshot, self.candidate, event='pull_request')
        self.env['CODEQL_EXPECTED_LANGUAGES'] = '["javascript-typescript","python"]'
        with self.assertRaises(RESULTS.ResultError): self.verify()


class ResultFailureDiagnosticsTests(unittest.TestCase):
    def test_only_fixed_public_categories_and_phases_escape(self):
        class PrivateError(RESULTS.ResultError):
            def __str__(self):raise AssertionError('exception text must never be read')
        cases=[(PrivateError('private'), 'verification-rejected'),
            (subprocess.CalledProcessError(1,['private-command'],output='private-output'), 'process-error'),
            (OSError(13,'private-message','/private/path'), 'os-error'),
            (KeyError('private-key'),'key-error'), (IndexError('private'),'index-error'),
            (AttributeError('private'),'attribute-error'), (TypeError('private'),'type-error'),
            (ValueError('private'),'value-error'), (RuntimeError('private'),'runtime-error')]
        for error,code in cases:
            with self.subTest(code=code):
                value=RESULTS.failure_diagnostic(error,'selected-jobs')
                self.assertIn('phase=selected-jobs code='+code+';',value)
                self.assertNotIn('private',value)
        for phase in ('/private/path',None,[],{'private':'value'}):
            self.assertIn('phase=unavailable code=verification-rejected;',
                          RESULTS.failure_diagnostic(PrivateError('private'),phase))


class FakeMetadataCodeQLApi:
    """Complete immutable/API fixture; never queries a host or executes source."""
    def __init__(self, case):
        self.case, self.calls = case, []
        self.mutate = lambda endpoint, value: value

    def immutable_blob(self, oid):
        self.calls.append('immutable-blob/' + oid)
        return self.case.blobs[oid]

    def immutable_tree(self, oid):
        self.calls.append('immutable-tree/' + oid)
        c = self.case
        value = {'sha': oid, 'truncated': False,
                 'tree': [{'path': path, **value} for path, value in
                          (c.base_tree if oid == c.base_tree_sha else c.candidate_tree).items()]}
        return self.mutate('immutable-tree/' + oid, deepcopy(value))

    def json(self, endpoint):
        from urllib.parse import parse_qs, urlsplit
        self.calls.append(endpoint)
        assert endpoint == RESULTS.PREFIX or endpoint.startswith(RESULTS.PREFIX + '/')
        parsed = urlsplit(endpoint[len(RESULTS.PREFIX):])
        path, query, c = parsed.path.lstrip('/'), parse_qs(parsed.query), self.case
        b = c.binding
        def page(values, field):
            assert query.get('per_page') == ['100']
            start = (int(query['page'][0]) - 1) * 100
            values = deepcopy(values[start:start + 100])
            return {'total_count': c.inventory_total if field == 'workflow_runs' and
                    c.inventory_total is not None else len(c.runs) if field == 'workflow_runs'
                    else len(c.jobs[int(path.split('/')[2])]) if field == 'jobs'
                    else len(c.artifacts[int(path.split('/')[2])]), field: values}
        if not path:
            value = c.repository
        elif path == 'actions/workflows/codeql.yml':
            value = {'id': 7, 'path': RESULTS.WORKFLOW, 'state': 'active'}
        elif path == 'branches/main':
            value = {'name': 'main', 'protected': True, 'commit': {'sha': c.default}}
        elif path == 'compare/' + '9' * 40 + '...' + b['base_sha']:
            assert query == {'per_page': ['1']}
            value = {'status': 'ahead', 'base_commit': {'sha': '9' * 40},
                     'merge_base_commit': {'sha': '9' * 40}, 'ahead_by': 1, 'behind_by': 0,
                     'total_commits': 1, 'commits': [{'sha': b['base_sha']}], 'files': []}
        elif path == 'pulls/42':
            value = {'number': 42, 'state': 'open', **{side: {'ref': b[side + '_ref'],
                'sha': b[side + '_sha'], 'repo': c.repository} for side in ('base', 'head')}}
        elif path == 'commits/refs/pull/42/merge':
            value = {'sha': b['merge_sha'], 'commit': {'tree': {'sha': b['merge_tree']}},
                     'parents': [{'sha': oid} for oid in b['merge_parents']]}
        elif path.startswith('git/ref/'):
            ref = path[len('git/ref/'):]
            references = {'heads/main': ('refs/heads/main', c.default),
                'heads/fix/main/example': ('refs/heads/fix/main/example', b['head_sha']),
                'heads/fix%2Fmain%2Fexample': ('refs/heads/fix/main/example', b['head_sha'])}
            assert ref in references, 'unexpected fixed native branch reference'
            native_ref, oid = references[ref]
            value = {'ref': native_ref, 'object': {'type': 'commit', 'sha': oid}}
        elif path.startswith('git/commits/'):
            oid = path.rsplit('/', 1)[1]
            assert oid in {b['base_sha'], b['merge_sha'], '8' * 40}
            value = {'sha': oid, 'tree': {'sha': c.base_tree_sha if oid == b['base_sha'] else b['merge_tree']},
                     'parents': [{'sha': p} for p in ([] if oid == b['base_sha'] else b['merge_parents'])]}
        elif path.startswith('git/trees/'):
            oid = path.rsplit('/', 1)[1]
            if oid == b['merge_tree']:
                tree = [{'path': '.github', 'mode': '040000', 'type': 'tree', 'sha': '1' * 40}]
            elif oid == '1' * 40:
                tree = [{'path': 'workflows', 'mode': '040000', 'type': 'tree', 'sha': '2' * 40}]
            elif oid == '2' * 40:
                tree = [{'path': p.rsplit('/', 1)[1], **v} for p, v in c.workflows.items()]
            elif oid == c.base_tree_sha:
                tree = [{'path': 'tools', 'mode': '040000', 'type': 'tree', 'sha': '3' * 40}]
            elif oid == '3' * 40:
                tree = [{'path': 'repository-checks', 'mode': '040000', 'type': 'tree', 'sha': '4' * 40}]
            else:
                assert oid == '4' * 40
                tree = [{'path': 'metadata_context.py', **c.source[c.marker.SOURCE]}]
            value = {'sha': oid, 'truncated': False, 'tree': tree}
        elif path == 'actions/workflows/7/runs':
            assert query.get('head_sha') == [b['head_sha']] and set(query) == {'head_sha', 'per_page', 'page'}
            value = page(list(c.runs.values()), 'workflow_runs')
        elif path.startswith('actions/runs/'):
            parts = path.split('/')
            run_id = int(parts[2])
            if parts[-1] == 'jobs':
                value = page(c.jobs[run_id], 'jobs')
            elif parts[-1] == 'artifacts':
                value = page(c.artifacts[run_id], 'artifacts')
            else:
                value = c.runs[run_id]
        elif path.startswith('check-suites/'):
            run = next(x for x in c.runs.values() if x['check_suite_id'] == int(path.rsplit('/', 1)[1]))
            value = {'id': run['check_suite_id'], 'head_sha': b['head_sha'],
                     'repository': c.repository, 'app': {'id': 15368}}
        elif path.startswith('check-runs/'):
            job = next(j for jobs in c.jobs.values() for j in jobs if j['id'] == int(path.rsplit('/', 1)[1]))
            value = {'id': job['id'], 'head_sha': b['head_sha'], 'app': {'id': 15368},
                     'check_suite': {'id': c.runs[job['run_id']]['check_suite_id']},
                     **{key: job[key] for key in ('name', 'status', 'conclusion', 'started_at', 'completed_at')}}
        elif path == 'code-scanning/analyses':
            assert query['ref'] == ['refs/pull/42/merge'] and query['tool_name'] == ['CodeQL']
            start = (int(query['page'][0]) - 1) * 100
            value = c.analyses[start:start + 100]
        elif path.startswith('code-scanning/analyses/'):
            value = next(x for x in c.analyses if x['id'] == int(path.rsplit('/', 1)[1]))
        elif path == 'code-scanning/alerts':
            value = c.alerts
        elif path.endswith('/instances'):
            value = c.instances[int(path.split('/')[2])]
        else:
            raise AssertionError('unexpected fixed CodeQL metadata endpoint: ' + path)
        return self.mutate(endpoint, deepcopy(value))


class MetadataResultTests(unittest.TestCase):
    """Sealed source boundary plus real native adapter/result validation."""
    def setUp(self):
        from types import SimpleNamespace
        self.A, self.postmerge, _ = RESULTS._metadata_modules()
        self.repository = {'id': RESULTS.REPOSITORY_ID, 'full_name': RESULTS.REPOSITORY, 'default_branch': 'main'}
        self.binding = {'repository': RESULTS.REPOSITORY, 'repository_id': RESULTS.REPOSITORY_ID,
            'head_repository_id': RESULTS.REPOSITORY_ID, 'pull_request': 42, 'base_ref': 'main',
            'head_ref': 'fix/main/example', 'base_sha': 'a' * 40, 'head_sha': 'b' * 40,
            'merge_sha': 'c' * 40, 'merge_tree': 'd' * 40, 'merge_parents': ['a' * 40, 'b' * 40]}
        self.default, self.base_tree_sha = self.binding['base_sha'], 'e' * 40
        ordinary = lambda oid: {'mode': '100644', 'type': 'blob', 'sha': oid}
        self.workflows = {RESULTS.WORKFLOW: ordinary(CODEQL._METADATA_RESULTS_WORKFLOW),
                         self.A.METADATA_WORKFLOW: ordinary(CODEQL._METADATA_SOURCE_WORKFLOW)}
        self.source = {self.A.METADATA_SOURCE: ordinary('f' * 40)}
        self.base_tree = {**reviewed_tree(), **deepcopy(self.workflows), **deepcopy(self.source)}
        self.base_tree.update({'tools/repository-checks/workflows/metadata-edits/' + name: deepcopy(value)
            for name, value in [('codeql-metadata.yml', self.workflows[RESULTS.WORKFLOW]),
                                ('pr-metadata-context.yml', self.workflows[self.A.METADATA_WORKFLOW])]})
        self.candidate_tree = deepcopy(self.base_tree)
        self.candidate_tree['tools/check.py'] = entry('b')
        self.native = {'number': 42, 'base_snapshot': 'a' * 40, 'head': 'b' * 40, 'merge': 'c' * 40,
                       'run_id': 13, 'helper_blob': 'f' * 40}
        self.marker = SimpleNamespace(SOURCE_READY=True, SOURCE=self.A.METADATA_SOURCE,
                                      native=lambda *a, **k: deepcopy(self.native))
        self.env = {'GITHUB_JOB': 'select'}
        edge = {'path': RESULTS.REPOSITORY + '/' + self.A.METADATA_WORKFLOW + '@' + 'c' * 40,
                'sha': 'c' * 40, 'ref': 'refs/pull/42/merge'}
        run = {'id': 12, 'run_number': 12, 'workflow_id': 7, 'check_suite_id': 112, 'path': RESULTS.WORKFLOW,
            'event': 'pull_request', 'head_sha': 'b' * 40, 'head_branch': 'fix/main/example', 'run_attempt': 1,
            'status': 'completed', 'conclusion': 'success', 'run_started_at': '2026-10-15T21:00:00Z',
            'updated_at': '2026-10-15T21:01:00Z', 'repository': self.repository,
            'head_repository': self.repository, 'pull_requests': [{'number': 42}], 'referenced_workflows': [edge]}
        self.runs = {12: run, 13: {**deepcopy(run), 'id': 13, 'run_number': 13, 'check_suite_id': 113,
            'status': 'in_progress', 'conclusion': None, 'run_started_at': '2026-10-15T21:04:00Z',
            'updated_at': '2026-10-15T21:04:21Z'}}
        def job(identity, run_id, name, start, end, steps):
            return {'id': identity, 'run_id': run_id, 'run_attempt': 1, 'name': name, 'head_sha': 'b' * 40,
                'status': 'completed', 'conclusion': 'success', 'started_at': start, 'completed_at': end,
                'check_run_url': f'https://api.github.com/{RESULTS.PREFIX}/check-runs/{identity}', 'steps': steps}
        def step(name, start, end):
            return {'name': name, 'status': 'completed', 'conclusion': 'success',
                    'started_at': start, 'completed_at': end}
        self.jobs = {12: [job(80, 12, 'Select affected CodeQL languages', '2026-10-15T21:00:00Z',
                             '2026-10-15T21:00:01Z', []),
            job(81, 12, 'CodeQL (python)', '2026-10-15T21:00:01Z', '2026-10-15T21:00:21Z',
                [step('Require reviewed CodeQL extractor version', '2026-10-15T21:00:02Z', '2026-10-15T21:00:03Z'),
                 step('Analyze', '2026-10-15T21:00:10Z', '2026-10-15T21:00:20Z')])],
            13: [job(140, 13, self.A.METADATA_JOB, '2026-10-15T21:04:01Z', '2026-10-15T21:04:20Z',
                [step(self.A.METADATA_STEP, '2026-10-15T21:04:02Z', '2026-10-15T21:04:19Z')])]}
        self.analyses = [{'id': 91, 'ref': 'refs/pull/42/merge', 'commit_sha': 'c' * 40,
            'analysis_key': RESULTS.ANALYSIS_KEY, 'environment': '{"language":"python"}',
            'category': '/language:python', 'error': '', 'rules_count': 43,
            'created_at': '2026-10-15T21:00:15Z', 'tool': {'name': 'CodeQL', 'version': '2.27.2'}}]
        self.artifacts, self.alerts, self.instances = {12: [], 13: []}, [], {}
        self.inventory_total, self.blobs = None, {}
        self.api = FakeMetadataCodeQLApi(self)

    def verify(self):
        with patch.object(RESULTS, '_metadata_modules', return_value=(self.A, self.postmerge, self.marker)), \
                patch.object(self.postmerge, '_source_qualified', return_value=True), \
                patch.object(RESULTS.codeql.inputs, 'full_tree', return_value=deepcopy(self.base_tree)):
            return RESULTS.MetadataVerifier(ROOT, {}, self.env, api=self.api).verify(processing_seconds=0)

    def test_native_snapshot_is_separate_from_live_B_and_nonancestor_or_legacy_field_refuses(self):
        self.native['base_snapshot'] = '9' * 40
        self.assertEqual(self.verify()['languages'], ['python'])
        self.assertEqual(self.native['base_snapshot'], '9' * 40)
        self.api.mutate = lambda endpoint, value: ({**value, 'status': 'diverged'}
            if '/compare/' in endpoint else value)
        with self.assertRaisesRegex(RESULTS.ResultError, 'base snapshot'): self.verify()
        self.api.mutate = lambda endpoint, value: value
        self.native['base'] = self.native.pop('base_snapshot')
        with self.assertRaisesRegex(RESULTS.ResultError, 'base snapshot'): self.verify()

    def test_current_protected_branch_and_exact_native_head_ref_remain_required(self):
        for change in ('protection', 'base', 'head-ref', 'head-sha'):
            def mutate(endpoint, value):
                if endpoint.endswith('/branches/main'):
                    if change == 'protection': value['protected'] = False
                    elif change == 'base': value['commit']['sha'] = '8' * 40
                if endpoint.endswith('/git/ref/heads/fix%2Fmain%2Fexample'):
                    if change == 'head-ref': value['ref'] = 'refs/heads/fix/main/foreign'
                    elif change == 'head-sha': value['object']['sha'] = '8' * 40
                return value
            self.api.mutate = mutate
            with self.subTest(change=change), self.assertRaises(ValueError): self.verify()
        self.api.mutate = lambda endpoint, value: value
        with self.assertRaisesRegex(AssertionError, 'unexpected fixed native branch reference'):
            self.api.json(RESULTS.PREFIX + '/git/ref/heads/foreign')

    def test_future_recipe_is_exact_and_keeps_existing_pinned_language_selection(self):
        for name, oid in [('codeql-metadata.yml', CODEQL._REQUIRED_CONTEXT_RESULTS_WORKFLOW),
                          ('pr-metadata-context.yml', CODEQL._SCHEDULING_SOURCE_WORKFLOW)]:
            raw = (ROOT / 'tools/repository-checks/workflows/metadata-edits' / name).read_bytes()
            self.assertEqual(hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest(), oid)
        for path, expected in [('.github/branch-cleanup.json', []),
                               ('.github/test-suites.json', ['python']),
                               ('browser/main.ts', ['javascript-typescript'])]:
            before = deepcopy(self.base_tree)
            before[path] = entry('a')
            after = deepcopy(before)
            after[path] = entry('b')
            with self.subTest(path=path):
                self.assertEqual(CODEQL.select_languages(before, after)['languages'], expected)
        previous = deepcopy(self.base_tree)
        previous[RESULTS.WORKFLOW]['sha'] = CODEQL._PINNED_RESULTS_WORKFLOW
        self.assertTrue(CODEQL.select_languages(previous, self.base_tree)['full_scan'])

    def test_fifth_pair_retains_actual_analysis_verification_without_floating_old_helper(self):
        self.runs[12]['display_title'] = self.A.ORDINARY_RUN_NAME
        self.runs[13]['display_title'] = self.A.NONPRODUCER_RUN_NAME
        self.workflows[RESULTS.WORKFLOW]['sha'] = CODEQL._SCHEDULING_RESULTS_WORKFLOW
        self.workflows[self.A.METADATA_WORKFLOW]['sha'] = CODEQL._SCHEDULING_SOURCE_WORKFLOW
        for tree in (self.base_tree, self.candidate_tree):
            tree.update(deepcopy(self.workflows))
            tree['tools/repository-checks/workflows/metadata-edits/codeql-metadata.yml'] = deepcopy(self.workflows[RESULTS.WORKFLOW])
            tree['tools/repository-checks/workflows/metadata-edits/pr-metadata-context.yml'] = deepcopy(self.workflows[self.A.METADATA_WORKFLOW])
        result = self.verify()
        self.assertFalse(result['qualification']); self.assertEqual(result['analyses'][0]['id'], 91)
        self.base_tree['tools/repository-checks/workflows/metadata-edits/pr-metadata-context.yml']['sha'] = CODEQL._METADATA_SOURCE_WORKFLOW
        with self.assertRaises(RESULTS.ResultError): self.verify()
        self.assertEqual(CODEQL.result_workflow_sources()[3],
            ('3a273057a38255ca368d3028594fb94227ba7c3b', 'd04a6dc70213d8b549bac30c11cc15eaf0182dea'))
        self.assertEqual(len(CODEQL.result_workflow_sources()[:5]), 5)
        self.assertEqual(len(CODEQL.result_workflow_sources()[:6]), 6)
        self.assertEqual(len(CODEQL.result_workflow_sources()[:7]), 7)
        self.assertEqual(CODEQL.result_workflow_sources()[7],(CODEQL._UPLOAD_RESULTS_WORKFLOW,CODEQL._SCHEDULING_SOURCE_WORKFLOW))

    def test_staged_boolean_template_preserves_old_and_new_exact_native_analysis_pairs(self):
        ordinary=lambda oid:{'mode':'100644','type':'blob','sha':oid}
        for base,active in ((CODEQL._SCHEDULING_RESULTS_WORKFLOW,CODEQL._SCHEDULING_RESULTS_WORKFLOW),
                (CODEQL._SCHEDULING_RESULTS_WORKFLOW,CODEQL._BOOLEAN_RESULTS_WORKFLOW),
                (CODEQL._BOOLEAN_RESULTS_WORKFLOW,CODEQL._BOOLEAN_RESULTS_WORKFLOW)):
            self.setUp()
            self.runs[12]['display_title']=self.A.ORDINARY_RUN_NAME
            self.runs[13]['display_title']=self.A.NONPRODUCER_RUN_NAME
            self.workflows[RESULTS.WORKFLOW]=ordinary(active)
            self.workflows[self.A.METADATA_WORKFLOW]=ordinary(CODEQL._SCHEDULING_SOURCE_WORKFLOW)
            for tree in (self.base_tree,self.candidate_tree):
                tree.update(deepcopy(self.workflows))
                tree['tools/repository-checks/workflows/metadata-edits/codeql-metadata.yml']=ordinary(CODEQL._BOOLEAN_RESULTS_WORKFLOW)
                tree['tools/repository-checks/workflows/metadata-edits/pr-metadata-context.yml']=ordinary(CODEQL._SCHEDULING_SOURCE_WORKFLOW)
            self.base_tree[RESULTS.WORKFLOW]=ordinary(base)
            if CODEQL.select_languages(self.base_tree,self.candidate_tree)['full_scan']:
                # A transition selected for both languages must supply both
                # original native analyses rather than hiding that selection.
                js=deepcopy(self.jobs[12][1]);js.update(id=82,name='CodeQL (javascript-typescript)',
                    check_run_url='https://api.github.com/'+RESULTS.PREFIX+'/check-runs/82')
                self.jobs[12].append(js)
                analysis=deepcopy(self.analyses[0]);analysis.update(id=92,
                    environment='{"language":"javascript-typescript"}',category='/language:javascript-typescript')
                self.analyses.append(analysis)
            with self.subTest(base=base,active=active):
                value=self.verify()
                self.assertFalse(value['qualification']);self.assertEqual(value['original_run_id'],12)
                self.assertIn(91,[analysis['id'] for analysis in value['analyses']])
        self.base_tree[RESULTS.WORKFLOW]=ordinary(CODEQL._BOOLEAN_RESULTS_WORKFLOW)
        self.workflows[RESULTS.WORKFLOW]=ordinary(CODEQL._SCHEDULING_RESULTS_WORKFLOW)
        self.candidate_tree[RESULTS.WORKFLOW]=ordinary(CODEQL._SCHEDULING_RESULTS_WORKFLOW)
        with self.assertRaisesRegex(RESULTS.ResultError,'rolls back'):self.verify()
        self.candidate_tree[RESULTS.WORKFLOW]=ordinary('f'*40)
        with self.assertRaises(RESULTS.ResultError):self.verify()

    def test_staged_required_context_template_preserves_each_real_installed_pair(self):
        ordinary=lambda oid:{'mode':'100644','type':'blob','sha':oid}
        for base,active in ((CODEQL._SCHEDULING_RESULTS_WORKFLOW,CODEQL._SCHEDULING_RESULTS_WORKFLOW),
                (CODEQL._SCHEDULING_RESULTS_WORKFLOW,CODEQL._BOOLEAN_RESULTS_WORKFLOW),
                (CODEQL._BOOLEAN_RESULTS_WORKFLOW,CODEQL._BOOLEAN_RESULTS_WORKFLOW),
                (CODEQL._BOOLEAN_RESULTS_WORKFLOW,CODEQL._REQUIRED_CONTEXT_RESULTS_WORKFLOW),
                (CODEQL._REQUIRED_CONTEXT_RESULTS_WORKFLOW,CODEQL._REQUIRED_CONTEXT_RESULTS_WORKFLOW)):
            self.setUp()
            self.runs[12]['display_title']=self.A.ORDINARY_RUN_NAME
            self.runs[13]['display_title']=self.A.NONPRODUCER_RUN_NAME
            self.workflows[RESULTS.WORKFLOW]=ordinary(active)
            self.workflows[self.A.METADATA_WORKFLOW]=ordinary(CODEQL._SCHEDULING_SOURCE_WORKFLOW)
            for tree in (self.base_tree,self.candidate_tree):
                tree.update(deepcopy(self.workflows))
                tree['tools/repository-checks/workflows/metadata-edits/codeql-metadata.yml']=ordinary(CODEQL._REQUIRED_CONTEXT_RESULTS_WORKFLOW)
                tree['tools/repository-checks/workflows/metadata-edits/pr-metadata-context.yml']=ordinary(CODEQL._SCHEDULING_SOURCE_WORKFLOW)
            self.base_tree[RESULTS.WORKFLOW]=ordinary(base)
            if CODEQL.select_languages(self.base_tree,self.candidate_tree)['full_scan']:
                # A transition selected for both languages must supply both
                # original native analyses rather than hiding that selection.
                js=deepcopy(self.jobs[12][1]);js.update(id=82,name='CodeQL (javascript-typescript)',
                    check_run_url='https://api.github.com/'+RESULTS.PREFIX+'/check-runs/82')
                self.jobs[12].append(js)
                analysis=deepcopy(self.analyses[0]);analysis.update(id=92,
                    environment='{"language":"javascript-typescript"}',category='/language:javascript-typescript')
                self.analyses.append(analysis)
            with self.subTest(base=base,active=active):
                value=self.verify()
                self.assertFalse(value['qualification']);self.assertEqual(value['original_run_id'],12)
                self.assertIn(91,[analysis['id'] for analysis in value['analyses']])
        self.base_tree[RESULTS.WORKFLOW]=ordinary(CODEQL._REQUIRED_CONTEXT_RESULTS_WORKFLOW)
        self.workflows[RESULTS.WORKFLOW]=ordinary(CODEQL._SCHEDULING_RESULTS_WORKFLOW)
        self.candidate_tree[RESULTS.WORKFLOW]=ordinary(CODEQL._SCHEDULING_RESULTS_WORKFLOW)
        with self.assertRaisesRegex(RESULTS.ResultError,'rolls back'):self.verify()
        self.candidate_tree[RESULTS.WORKFLOW]=ordinary('f'*40)
        with self.assertRaises(RESULTS.ResultError):self.verify()

    def test_same_merge_original_native_analysis_is_freshly_revalidated_without_qualification(self):
        result = self.verify()
        self.assertEqual(result['metadata_only'], 'true')
        self.assertFalse(result['qualification'])
        self.assertEqual(result['merge_sha'], self.binding['merge_sha'])
        self.assertEqual(result['original_run_id'], 12)
        self.assertEqual(result['languages'], ['python'])
        self.assertEqual(result['analyses'], [{'id': 91, 'category': '/language:python', 'rules_count': 43, 'job_id': 81}])
        self.assertEqual(self.api.calls.count(RESULTS.PREFIX + '/pulls/42'), 2)
        self.assertEqual(sum('/actions/workflows/7/runs?' in x for x in self.api.calls), 2)
        self.assertEqual(sum('/actions/runs/13/artifacts?' in x for x in self.api.calls), 2)

    def test_disabled_source_and_unprotected_workflow_decline_before_security_lookup(self):
        self.marker.SOURCE_READY = False
        with self.assertRaisesRegex(RESULTS.ResultError, 'not qualified'): self.verify()
        self.assertFalse(self.api.calls)
        self.marker.SOURCE_READY = True
        for path in ('tools/repository-checks/workflows/metadata-edits/codeql-metadata.yml',
                     'tools/repository-checks/workflows/metadata-edits/pr-metadata-context.yml'):
            old = self.base_tree[path]
            self.base_tree[path] = entry('9')
            with self.subTest(path=path), self.assertRaisesRegex(RESULTS.ResultError, 'protected metadata workflow'):
                self.verify()
            self.base_tree[path] = old

    def test_first_workflow_activation_requires_both_real_original_languages_and_protected_templates(self):
        self.base_tree[RESULTS.WORKFLOW]['sha'] = CODEQL._PINNED_RESULTS_WORKFLOW
        del self.base_tree[self.A.METADATA_WORKFLOW]
        self.jobs[12].append({**deepcopy(self.jobs[12][1]), 'id': 82, 'name': 'CodeQL (javascript-typescript)',
                             'check_run_url': f'https://api.github.com/{RESULTS.PREFIX}/check-runs/82'})
        self.analyses.append({**deepcopy(self.analyses[0]), 'id': 92, 'category': '/language:javascript-typescript',
                              'environment': '{"language":"javascript-typescript"}'})
        result = self.verify()
        self.assertEqual(result['languages'], list(CODEQL.LANGUAGES))
        self.assertEqual({x['id'] for x in result['analyses']}, {91, 92})
        self.base_tree['tools/repository-checks/workflows/metadata-edits/codeql-metadata.yml'] = entry('9')
        with self.assertRaisesRegex(RESULTS.ResultError, 'protected metadata workflow'): self.verify()

    def test_query_configuration_cannot_be_authorized_by_conservative_full_language_selection(self):
        path = '.github/codeql/codeql-config.yml'
        for side in ('base', 'candidate'):
            tree = self.base_tree if side == 'base' else self.candidate_tree
            previous = tree[path]
            tree[path] = entry('9')
            with self.subTest(side=side), self.assertRaisesRegex(RESULTS.ResultError, 'analysis configuration'):
                self.verify()
            tree[path] = previous

    def test_empty_language_set_still_needs_original_native_merge_pointer(self):
        self.candidate_tree = deepcopy(self.base_tree)
        self.jobs[12] = [self.jobs[12][0]]
        self.analyses = []
        self.assertEqual(self.verify()['languages'], [])
        self.runs[12]['referenced_workflows'] = []
        with self.assertRaisesRegex(RESULTS.ResultError, 'native merge source'): self.verify()

    def test_native_leaf_bytes_are_authenticated_and_large_or_excessive_reads_stay_conservative(self):
        for change in ('valid', 'forged', 'oversize', 'too-many'):
            self.setUp()
            self.candidate_tree = deepcopy(self.base_tree)
            self.jobs[12], self.analyses = [self.jobs[12][0]], []
            for index in range(33 if change == 'too-many' else 1):
                path = f'native/Fixture{index}.cpp'
                for tree, value in ((self.base_tree, index * 2), (self.candidate_tree, index * 2 + 1)):
                    raw = f'int value = {value};\n'.encode()
                    if change == 'oversize': raw += b' ' * 64_000
                    oid = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
                    tree[path] = {'mode': '100644', 'type': 'blob', 'sha': oid}
                    self.blobs[oid] = raw if change != 'forged' else b'int forged = 1;\n'
            if change == 'valid': self.assertEqual(self.verify()['languages'], [])
            else:
                with self.subTest(change=change), self.assertRaises(ValueError): self.verify()
            self.assertLessEqual(sum(call.startswith('immutable-blob/') for call in self.api.calls),
                                 CODEQL._NATIVE_BLOB_COUNT)

    def test_newer_ordinary_failure_pending_unknown_and_rerun_never_fall_back_to_green(self):
        for status, conclusion, attempt in [('completed', 'failure', 1), ('queued', None, 1),
                ('completed', 'success', 2), ('mystery', None, 1)]:
            self.runs[14] = {**deepcopy(self.runs[12]), 'id': 14, 'run_started_at': '2026-10-15T21:02:00Z',
                             'status': status, 'conclusion': conclusion, 'run_attempt': attempt}
            self.jobs[14], self.artifacts[14] = [], []
            with self.subTest(status=status, attempt=attempt), self.assertRaises(ValueError): self.verify()

    def test_newest_ordinary_timestamp_ties_are_not_resolved_by_run_identity(self):
        for status, conclusion in [('completed', 'success'), ('completed', 'failure'), ('in_progress', None)]:
            self.runs[14] = {**deepcopy(self.runs[12]), 'id': 14, 'status': status, 'conclusion': conclusion}
            self.jobs[14], self.artifacts[14] = [], []
            with self.subTest(status=status, conclusion=conclusion), \
                    self.assertRaisesRegex(RESULTS.ResultError, 'ordering is ambiguous'): self.verify()

    def test_original_and_current_native_source_must_be_same_merge_not_just_same_head(self):
        for run_id in (12, 13):
            for change in ('missing', 'other-M', 'mixed', 'foreign'):
                old = deepcopy(self.runs[run_id]['referenced_workflows'])
                refs = self.runs[run_id]['referenced_workflows']
                if change == 'missing': refs.clear()
                elif change == 'other-M': refs[0]['sha'] = '8' * 40
                elif change == 'mixed': refs.append(dict(refs[0], sha='8' * 40))
                else: refs[0]['path'] = 'foreign/repo/.github/workflows/foreign.yml@' + 'c' * 40
                with self.subTest(run_id=run_id, change=change), self.assertRaises(ValueError): self.verify()
                self.runs[run_id]['referenced_workflows'] = old

    def test_original_version_analysis_window_native_check_and_open_findings_remain_required(self):
        for change in ('version', 'version-step', 'window', 'analysis-M', 'check', 'finding', 'extra-language'):
            self.setUp()
            if change == 'version': self.analyses[0]['tool']['version'] = '2.27.3'
            elif change == 'version-step': self.jobs[12][1]['steps'].pop(0)
            elif change == 'window': self.analyses[0]['created_at'] = '2026-10-15T21:03:00Z'
            elif change == 'analysis-M': self.analyses[0]['commit_sha'] = '8' * 40
            elif change == 'check':
                self.api.mutate = lambda e, v: {**v, 'app': {'id': 42}} if e.endswith('/check-runs/81') else v
            elif change == 'extra-language':
                self.jobs[12].append({**deepcopy(self.jobs[12][1]), 'id': 82, 'name': 'CodeQL (javascript-typescript)'})
            else:
                self.alerts = [{'number': 9, 'state': 'open', 'tool': {'name': 'CodeQL'}}]
                self.instances[9] = [{'ref': 'refs/pull/42/merge', 'commit_sha': 'c' * 40,
                                     'category': '/language:python', 'state': 'open'}]
            with self.subTest(change=change), self.assertRaises(ValueError): self.verify()

    def test_incomplete_inventory_and_metadata_producer_or_artifact_never_qualify(self):
        for change in ('truncated', 'producer', 'artifact', 'marker-skipped'):
            self.setUp()
            if change == 'truncated': self.inventory_total = 3
            elif change == 'producer':
                self.jobs[13].append({**deepcopy(self.jobs[13][0]), 'id': 141, 'name': 'CodeQL (python)'})
            elif change == 'artifact': self.artifacts[13] = [{'id': 900, 'name': 'unrelated'}]
            else: self.jobs[13][0]['steps'][0]['conclusion'] = 'skipped'
            with self.subTest(change=change), self.assertRaises(ValueError): self.verify()

    def test_final_bookends_reject_candidate_default_inventory_jobs_and_metadata_mutations(self):
        for change in ('default', 'merge', 'run-inventory', 'metadata-job', 'analysis'):
            self.setUp()
            reads = 0
            def mutate(endpoint, value):
                nonlocal reads
                suffix = {'default': '/git/ref/heads/main', 'merge': '/commits/refs/pull/42/merge',
                          'run-inventory': '/actions/workflows/7/runs?',
                          'metadata-job': '/actions/runs/13/attempts/1/jobs?',
                          'analysis': '/code-scanning/analyses?'}[change]
                if suffix in endpoint:
                    reads += 1
                    if reads == 2:
                        if change == 'default': value['object']['sha'] = '8' * 40
                        elif change == 'merge': value['sha'] = '8' * 40
                        elif change == 'run-inventory': value['workflow_runs'][0]['updated_at'] = '2026-10-15T21:05:00Z'
                        elif change == 'metadata-job': value['jobs'][0]['steps'][0]['number'] = 2
                        else: value[0]['rules_count'] = 1
                return value
            self.api.mutate = mutate
            with self.subTest(change=change), self.assertRaises(ValueError): self.verify()


class NativeUploadApi(FakeCodeScanningApi):
    """Real immutable Git plus entirely fake native API/artifact responses."""
    def json(self, endpoint):
        from urllib.parse import parse_qs, urlsplit
        parsed = urlsplit(endpoint[len(RESULTS.PREFIX):])
        path, query, o = parsed.path.lstrip('/'), parse_qs(parsed.query), self.owner
        if self.error: raise self.error
        if self.change: self.change(endpoint)
        self.calls.append(endpoint)
        if path == 'commits/refs/pull/42/merge': return deepcopy(o.merge)
        if path == 'actions/workflows/7/runs':
            return {'total_count':2,'workflow_runs':[deepcopy(o.runs[o.attempt]),deepcopy(o.metadata_run)]}
        if path.startswith('actions/runs/13'):
            if path.endswith('/jobs'): return {'total_count':len(o.metadata_jobs),'jobs':deepcopy(o.metadata_jobs)}
            if path.endswith('/artifacts'): return {'total_count':0,'artifacts':[]}
            return deepcopy(o.metadata_run)
        if path.startswith('git/ref/'):
            from urllib.parse import unquote
            ref=unquote(path[len('git/ref/'):]); return {'ref':'refs/'+ref,'object':{'type':'commit','sha':o.refs[ref]}}
        if path == 'actions/runs/12': return deepcopy(o.runs[o.attempt])
        if path.startswith('actions/runs/12/attempts/'):
            parts = path.split('/'); attempt = int(parts[4])
            if len(parts) == 5: return deepcopy(o.runs[attempt])
            if parts[5] == 'jobs': return {'total_count':len(o.attempt_jobs[attempt]),'jobs':deepcopy(o.attempt_jobs[attempt])}
        if path.startswith('git/trees/'):
            tree = path.rsplit('/',1)[1]
            rows = []
            for line in o.git('ls-tree',tree).splitlines():
                metadata,name = line.split('\t'); mode,kind,oid = metadata.split()
                rows.append({'path':name,'mode':mode,'type':kind,'sha':oid})
            return {'sha':tree,'truncated':False,'tree':rows}
        if path.startswith('check-suites/'):
            identity = int(path.rsplit('/',1)[1])
            return {'id':identity,'head_sha':o.head,'app':{'id':o.app},'repository':deepcopy(o.repo)}
        if path.startswith('check-runs/'):
            identity = int(path.rsplit('/',1)[1])
            job = next(job for jobs in [*o.attempt_jobs.values(),getattr(o,'metadata_jobs',[])] for job in jobs if job['id'] == identity)
            return {key:deepcopy(job.get(key)) for key in ('id','name','status','conclusion','started_at','completed_at')} | {
                'head_sha':o.head,'app':{'id':o.app},'check_suite':{'id':o.metadata_run['check_suite_id'] if job['run_id']==13 else o.runs[job['run_attempt']]['check_suite_id']}}
        if path == 'actions/runs/12/artifacts': return {'total_count':len(o.artifacts),'artifacts':deepcopy(o.artifacts)}
        if path.startswith('actions/artifacts/'):
            return deepcopy(next(row for row in o.artifacts if row['id'] == int(path.split('/')[2])))
        if path.startswith('code-scanning/sarifs/'):
            upload = path.rsplit('/',1)[1]
            return deepcopy(o.statuses[upload])
        if path == 'code-scanning/analyses' and 'sarif_id' in query:
            return deepcopy([row for row in o.analyses if row['sarif_id'] == query['sarif_id'][0]])
        # The base fake retains all existing PR/ref/commit/security guards.
        callback = self.change; self.change = None
        try: return super().json(endpoint)
        finally: self.change = callback

    def immutable_tree(self, tree):
        rows=[]
        for line in self.owner.git('ls-tree','-r',tree).splitlines():
            metadata,name=line.split('\t'); mode,kind,oid=metadata.split()
            rows.append({'path':name,'mode':mode,'type':kind,'sha':oid})
        return {'sha':tree,'truncated':False,'tree':rows}

    def bytes(self, endpoint):
        self.calls.append(endpoint)
        return self.owner.archives[int(endpoint.split('/')[-2])]



# Actual public PR1505 retry API rows, including the FAILED result2 gate.
# This is an input fixture, never successful retry evidence.
_CODEQL_CARRIED_RETRY_NATIVE = (
    'c-rk<X>;2~(*7$be%h@FA^_slR%+unPIkRXY&ljgZ*8##z<`1U5(o~-3`_t0?KuE~v<?y=MOtoukV%l!>>12-KTppzdNCknNvBz<'
    '56%_?5|nAqUtE)t<l`z&24{oIvdoIJ;ZR&GPA74BS@~5#^B|p-bXJ}Q>2z2Pb<J~4%QpXc{k1tb8PIF^s92Yg#j?F<1VW18EG3s}'
    'qDDEHT@6LE#W2g`YZA<FK~j_^NqPg{+*(-EvXK(cCLN_f%f&D)FDZ-*e1|DEiHi<B<gFI`zi}LLIk_D0I0Q*>;j)}2YjRsM+tT36'
    'tWiDoCxaxN#4~8O_N7@GQX&4Qmv8M~e}A0>AHKVJb1~6gU;LrL7t(w}X7OL7jMLfneS+3(jB^^$_?m{}jyHd;J(rlJUF1M3XkEl5'
    '9g}d%MkFFhLE#dNa}K|-tw`Aprohb%?*4-R2D^Dh<rhI7XWa&Fr8P(^=NSb7zrZ))-Imf=3%EGGj_J)<O3ErfiG#uI$$;c#9KjNQ'
    'L`gn&Yj^jW<|Q3MTc+hOui($fvrNy{wUId*Hj+VsfXo7#?EEK$SSJ6H23O;vVs}=|d`EX|+i^8(wEF3C%76QAe0B5k%|+%WZ(R2U'
    '{QJXunZ3*2uF31DG#8<A5yh~r4-=oxf}|>-Qy@7aaZ=@!UCt>fVHT1SE*qL*tGcEd`h{kl8TOgwy@&6FagiltJ}%=jVR!Nk|21U>'
    'OZ1v5X&%NilFyYtE0V-f9PpK^TpP9N<@Y{G#yS17qD9H93MJv#2hD>^_z>0_=oTk*7(>4bn$Um=R)bj0a^2E2m4*{qH-izF#wGU+'
    'Re34A1f4>EKvHddzT$)9({K39Je{R5WXZfWhRhC;DeKE?_$Hf^LTpKQC6C{3cN9{~h{#CO{fH1^XqKnhfgOex(F4l}gOIvJ3!wRw'
    '76q9w3Fmp5kqO+CdO&HYG=rji`${QOg=ASm)tH->GKRJ#nPzw0K*M1-u*|8PfcA)LrXJXSL_=MVG)<?5Ke9F7q@fX*VMx6&v>lCg'
    'fe$yIY%zG_IUn*oxCAY_&d){NK1%Z`DY@;6nCT)#5l?26cDD$%fW@%(iGGs$o#nxohFrj6SX>e=j!)O_8rJO>^3^S0lSxASG$$~='
    'odvH5S**MjzcHOY?gAeYFWN7Lvuf(oMrPbkWLz$X7T#whr#-~6=EH?g3VM5bdb(gUR|w{?u!o|e{c!PBM#{@tWFGrfzdN>+!OSZd'
    'lXTweCbdLxfsH3;9(<NYV3lK%C@)^AY@rlj@D=(oqj}7lzz5Qz!?L_$f0Xk$NEP!$c`*y~G!B*QGM&-lM2XMYixY*+LU>KWe<-uG'
    'gm+5w6H-zR1`F=SDbogUN|KVWd*^Ba8)EtUB{g7<b#!o6<`osMJ4@t^nLy^?qzky?dmN&d<DTn=8Kw2L!^DCS?In}7UlCZ6NiTt{'
    'eIxKPO}mdTZ@d)`S&lddWh33wEW_3SlEp<)(Xq5=T@~U&iaV{Mkl$~HO7S)KToc|?Y+K$Hop+YT+Ai2%$r{1m(4@08(HeAv)gz?M'
    'CKW)T9s;ER4y*DWl0<7J2GD6yG8@=gR3o8%7o^2#rtFd_{5-yzNTP7VKPVe$-C2hfA&Y+&F)*1Ek|ZY?<4r*fJ`Q3FOfOC?G5&(_'
    '7mU9=!}tqdQDATCkznk+vr*xV+cr%?zs>^d_KTrd6KuRE<S*JCZ!aYXab?v*y}JEyA@Pm8aef~Kmm=2YQBR421HfeJ0q9s;CW4Y_'
    'cNwg)3`F!pmO1D6a_GAWYGNB8WxF8F)+qGeFru{9tt%&k4?W@)_eVs<t_p+$hfMx}`-Q#!43ocvHk-!^myYST?*aYX{MZhY{^#|t'
    'LH3>@Ax6aEJ5t}_4G^#hoHB#tA^kHsoljYCHp}UCoL0qHDkeHS16y^n5{xVcXa8LcSm1!69Uwv=x*c3&L%}{-=Mw9{t@}(Alh6xI'
    'n18xu=|qc+$aJaUX`$(Ox?vfC<C?DFIic>?b9brj#?jNK>dMCJNk&Oc&$M039oY`(!o3LSXK7YfO@v1pG7*E@|FM2YG^YS{!*MfN'
    '_+6JX=`InU&aNz1r?ey?pfi=D-H#=kYTwu+LvzANC(y?z@?AU7ZNu`MDDZtV3LUt0b`*?8{04~o6%|}XuA!h9gL>>XmL@uep;-*g'
    'VrUjavlyDi&@6^#F*J*zSq#l$Xcj}W7@Eb<EQV$=H2YbGW^)SB#hnKzxm30UK(>qtf<+eZ>!_3KYT^Q$m5&{Y6q5};XB;=7@O3_j'
    '@nizr4ICIAVMjlWe)_rk=_(8FJ2pMi&Mf<VXA}6)mQfv!=96z^db)0pn9XXg_x#CaxVsU~&+7|&X<%j!nl&_Qn3;o_IS0<nG2JuG'
    '!OR@Y%)#wn-2TPwU)=u1?O)vf#qD3*{>ANI-2TP*3&vkC{({@Txc!UUznGcx8D!=dPm`Hr9CK#QUQ&?;nCpYNKA7u+!CnmZVz3v3'
    'y%_ApU@r!HG1!a2UJUkPuor{980^JhF9v%t*!yMV`WV~i`mke`Hs<=EpGH58xjy$<2*Z6=xjy`$dcka&&M3QO*_LBF+_q&I`!7gh'
    '#@qRlcy+CxYF6NQ)FYuD*?t(2PfxDvuBtieNW0KHmK>#vlj|$Nu@?}8o3ew|^R&v9S~Vrg)2R}Nl(3W4S)PVfAU&y^=V$+w0pT%x'
    'T2lV$IIj}goZ1(jpml=3(T^*^jQL9JZ{^Kc8h(DzKB$U9{P^-s9mc3*SzwaD=2g=sQZQJHchoe!=EUPko>p0#+VYJw_`t8?B;-3-'
    'd>)>xpVV)^9kV?(dUN;H)=y_uamj51v!VHXoRQ#)$PFWo_693E4ed8$mTExC;Bx5>VJ^xG&75p~skz4P0PJAECJN1GWZgVp(j;q7'
    'Tso^~=%eNwCS)PstIIars#_!5ZD{?!;_}~>ue@l!(zfY8*>8XUznh;fe);S5hsoEyIk)HO-qwCxZb0?*;8ILy-@VelkJpxhdi!hf'
    'Qr=TGvP&=BeAK>|-_74#dGq(i_Z9g)yA1!8T>Brcte-BfzV70uWiPsWXepqFZ*C;)!YfN*yYt7jz`H&1o7Q-5=8>Cw`VeQP`84LH'
    'w~*PW;^p8b7q*=b53_DWx|W>npf5Aq#`Vr_yA5yzX4BS0)vj=Pfz363KBAnjTo&6?E0?l3Nz2yBgXW|59#QLR<5E_xf+e8s3(~19'
    'F9;_BKeB$g>7?xc6m(CD<$G!R+l{jI_p4_on(Hm6Aod0B{0JQK2O6w2END={%Xz&LTAxTZ-@0^NB``mUAG6UOlLWv^qdq%-kW`b#'
    '4z$ewr(jJ3yyjl$HUJO6YwsJ7BjG@ON}`pMCz8$t(Yx~*5YCx4dcU5zS5!d&sbc&Vmyo4a?B+ZYI~+7z!D206$_=06_=cthwi*UT'
    's9H3%R4>%1N=?_%T{oa^WDO2~u<EXk@R4s_YJ4^T!b_MVEJ{w5^Pd%V21B7?Tq;B5XE+5j0n<X2csi|0;wQBAxjeA3;u^mFc|Ez)'
    'uf98f`H>-}v?{YoWG&7hGB5o@kX9@`67Y8WYOmx^J|6AP4qKwR{hdw;JKrImQp`J1zZU78?9DBnY5Ky>G(Ge%8Zboqy#cD-&Q{i4'
    '`QEiPV}z6tDIroqq=ZNbkrE;$L`wL@Q$pQ11SJ$$Y@HHXp=A>n*r4s2Bh?xOy6TUB5?Y}PWHB@&5{{0H64o7QQ9^#H@!9V<HBd+t'
    '!GCaa_FI^~Z+}$U$IKpKd~e@b2V;D^FUa_i@%3kX*8UlvSd0zhvkhltA>%{Fhl~#yA2L2<e8~8a@qOux&pWf+128^`#nu^LWRoD!'
    'O-HpID^M*za#i9uhDr(X!a%3gwCHg$zNRBf#wRW{K3g)pzkL9QA*_qaY=L<B_s99(JMFi(2jY98C&>4Z@Ac+;y1940CzoQI@0pf{'
    'd=L2^@;&5x$oG)%A>Tv3_hs`v05PV07{14_*gD@c_0Y5e(^f5AgF~ML@D>RpM|Esn*GFOGd3Jbod{1;_h3~<oPxxLohw>4#jR+ph'
    'hl3G3P#p;#61>lZ;IXw=6Fl2?A@LOn9uhnxcu4S&;32_7f`<eT37%!WzrP;eo(Nuz#nuTPTn$H&O;z32P1SN}p!#rpQzauObRsu!'
    'eDAmj-m)VN!IPI7pDi8)uGTX~&1q33<>MzezrT1jd6eksdm(zV3rO^k==CFdEPmwfo9NYRP!c^`cWuiwO(c3q^pNNw(L<t#L=TA`'
    '61^{*=&^_PIZsaX8Z5R>^lW`(z$5q^)zy6icJfSJbxmDY4bU16Zd%&N^^S??wK`H0z4}sbqW8o32kXT_h+f?VBzj2n`Vl=aFS@p8'
    'qSvg!Hqmo*9f=+iJtTTa^pNNw(L<t#L=PXz^7Id7X|UKQM>Z`p2z}d7iRoMLP!>N@eHyaEn}JE3$hY7C=g|>8(UBFR2bXsDP?jIg'
    'ubjg?l%?(qGCpK{$Nx~4W-+!HA5;*=hq55!L&k@U4;ddaK4g5z`0$}D2Y4t;gT>Yv9|@_Z!Ff$USp>HB0>f2(*LGA>H^|7>oiOx*'
    'V`F@>BW=dVF74`}EI*vjemNZ9V?9B>hkWn&bM~60xWe}=+~GsMhkOtD9`Zfpd&u{Y?_ti~0UpZIV6k<+r-j4}2}{y*G|1W098GoM'
    'IV`HDMgE97j_y0o@$o%N|Ag;Zdgq6-0KxMQN$@P(&_jav*$_OdwV?<16ss&C!9#+F1P=)w5<Db$Nbqn&?;xet8!Wa?@O&%Mf!je('
    'BNL8r>Smw<tPNG)Ha#nZy}rn@kBi_n9a$1Qap?(5t^e@OfA#i2lu&dQDIrqA<1e+|tkzrTFD&7L@Ak15eCjnUYrNyi?mcbr8V6lz'
    'YM)u&``RK3{<zIVJf;Gr^;oqEl=4fGW^#rMJY`l^s$rgLCSzhxW@5iPfBBJ-QZ_pn#+qg#QJTGHjaq#Y7duX&`vyw<G@uB<viWan'
    'YuE1Mi1JGU8o)opwOA^-ynJUXW%<QHk7ZkwG?Q!Vu?6r@9!Zl6Q7ToYz?2!Z%+sUl8TY7nd(us<t2oPe@9F?9TlEU~-qr+@Ask59'
    '$i?(yqpB1T5ejHadE?;9FIPu8OXdnJBc&Fr%m_0Y%f-@Cd~|Td+e<zK<*9l@=1NT#lvz4cMU)NHUFvN<x!&uOcuns-jAww9lv-D%'
    '04EYw3B)YqbW#2m#$+-}3usd)#4n)r-&<X>4&J42>j|^EGVSh){jamfuk9yu>g$fB3FAq<-|!~&G;eMNXT=e_L2S)l8)BSxj}7XA'
    '+`Url9>NAN!sau<2KN^)e-s<+tgQKSasAGwuHPB-$jaKn_1k-M{dOPA=WSs58rNUuRl#N#fl$W0hzli4A<Q@5%Gd8(+cjU`_<2sr'
    '!Tu?J8qNhQZsNO}JAAK)_TqUik7-Xrj!)=ESSd<CW?{_YV@f<@%8E^%&Heno)s<$a8RW+P)P_e+6<TcL%kO>g&92lw2b`g7HPqgI'
    'b=Ei3d7GuEYX{f)9?YaaYSVQ6X+Tr$agPf$H8pK}WvM(2ngrhZ{6W(L^?x4)O*^U#{7fK|rELhAc=@f)=Uz64OuDl#$fR3644<iQ'
    '1DPbfy@4Ce-ol~`88L><;B8Qo7>bSxTjt{mzhc1~Fm3>w#H!c^6`A^;wfh<NPU4&@;(W}K-ayPIht&a~4pxdh>$5R9vdqp}gXJA<'
    '5Cmba`7gQ+^4Ysi3?1hJ_DJU@hq8iAZooq^pPl7=^9V=%yIqyu;P#)h(*(ukR$4oU*O~#gPv?McJgQl*NnmZL*+VN{A03B|Tbfbb'
    'd{k{~&uZU?c&+Z5?G*7gaOvm}uc+$T>zw`<gLv<&fVwf_-L^LBbAh<}rVv+uB8Y1rCBz+>2Y|SJ0)wWrXNWs8_pIGsAg<Y&HZW6b'
    '>;>ZPU8kKx+~#+?Dm^*`#C;O2J3-t=cvsEL{X^U*({Z;DxB2Bgs@)CZKB(EQA+EqjM+I@0bq#x!k9+{)Ht6`Xhqw>bfP56<_N@;2'
    'OrWm4X*Ab<B%1qh#la1sE)(MI1?oPe-bNPB+Z>w_MSc`j3G5O=VhEiv8?A^{mF64c-R6g%Kx^3L1}i62Y;72BjDGv-YUy2$7}Wa8'
    '_511erupPbuOH6)Db91i<qWb#pyef;HXv)~-eO38BZ)GFy=B67loipNjq!4$N!M-|J&qheg6zsHmv=(CkQF9k@3$AD2R!21YzM2K'
    'FP9|DpXMY&?GcogN7xieTgGnH-||Gl7I)%tTx*S<qAwj*^yAoe@2Ypkw)bncOKiIYMxC)Os8d1?Q&J~PSu#n)*lUtVtJ+(yqIwU&'
    'Uudei&jJ2ESQ&3`@VBm+w*r5S&ldiAo2GtvkEDJ)T!(E#_{)Uodx5`=<Ss^WL$!7ff1gt8zVNrVuA>9M-+d^30QlQz(zP4bF~Hxx'
    'y)dkU!rx{bcc=cr;BTW&*S^>XgTGIqdN=sn2;VdOZ2_ZW3hlNET<t5#>3Lz>`-*|>Kgp>s6Lw4>S3EER^PDix3G<vV&k6IKFwbc('
    'xJfwOW5Z3dOw7LWoEUEMo(pcex1`R#^PK8pJI@C-VX70RI$^34raED&6Q(+0s?)Pfb!s7|;{&~xzQ<IjX9jxjsVlPcRHwS)$TLE@'
    'nC*nwPMGb4*-n`4gxOA*?erY8omvp-xKM6WFkoNL1ZSsGp2?Q@1H~1N;F;ic*@b7cXO52r$H#)>W5MyU;LrZC;4R;>(}WRLAy5?a'
    'O1oFygG?6Jv}|+h>U%3)?^}a!MOf!be0NCcQ;%;&T<@xUZD}>ikYm5B&$srac9p)j_OHLcPJ$2L-MqP&Xs<8+(7IITTb;0-YxJ#%'
    '=~1a~P0lXr^{t59UDdu-v3J+*`=#KPeoJW&SMI9|@D;m8bi+n6v#tQ#X|nU55Moyg$&S~{#;tzZg2C_BVelW`%j{kDc1>O{vcyGz'
    'nQrORDetW*j>Jm2CS*RAwZ}HL@Y3}1d%se!whyynC2V6+qz!z&@Dg+i{Q*g}@%f4mj!(bgGxKzo!jL8N))+3m>}&YuKvekyu_fJ='
    'Jbt^k;D1x_{jB~jgfsFK$}ck3B?q)Q;?JX5uUG-(c3rnJp0bja)9kJrC~_XloXQDkkEmwqf$c{$)b&WybZYn`Tk}mC8i5&x)C)t~'
    '(dy!C<5mq|HspD530icWpNqOZ<Xu3GXKuS9X1WN}yPV7@?QRij0gGYn6a56hN>_RCr6Cuv7y^~&;`ns!u3_DNAz$6{HJJbpPji;S'
    ')V-u&TgYPNt@sUI^0|k2(S9)$2(*?N_Y)bH%b{fumE^RCIM#f)V6_i#Pft%5Z06p!%CUBrEZPqjUqLPF%UWa}`&GX?wv@422DYoj'
    'b|u;Mg6hA_(g>_F1VEJ+uT-{B__0^|5en$WtO<M|EjlY)&U2#9;~-Vc6NpKNc^ZdG1{<BUI8owr_TmK2%t9pnoP_@XMhIyWGo|?n'
    'DM=O)KV{kgPGO<<?wzXzY>4IWm(+kcUZMRAP5@K!y0b*ym<ePKPP%}*N=h<_UXFXN8)lT&*A5d4Mzohq)_z4`NhZAnvi6NYUKqHm'
    'G*MN!LwK~NBdzM7ykhcL+Ow_-iL%RgT16qh-wc)FYwo!wyr<Z<yem5IERD5Yu)mTuidb@2X`(gg2CGL%lSx<I1unC;cv0-ml0<7J'
    '2GD6yG8@=gR3o8%7uE~bE|~(v%O{d3-0%;|23mL4VMWN|pG6Ez=7d1NJ7c^lh{4A}Y=P;;sU^l=F#dw^muDD%;VX*OyO$%ut4xpk'
    'l&EgoGztAW3#{8OhGI>y@t%;sXm`B5l+XmmX&+&{{cs`ijl6Mw9|e~p*5*-9iJ5$eK_5WJ+A<N8OuNfqjb$LBAF|9j$CpFjy}tXQ'
    'H|eFdUfJUQ&?8>)&|v^J@Zbz~FPjNnf|$*tf=d_l+xP5Tz>n>K=zm`S8f5Po=3$f@z9W?!*85Bhe6uG}ozAB$44bi&erZ+IM+kNw'
    'Qx<X|pgK5N31o^bcouYENC`+3{A@cg$9{`_vd%-+L0|V-EGDoQnlN{DIBZL_$cRjr8lD!K4(!lbM&P)nYj{qm`}MqEYP)gd^{KkD'
    '@miD-R?{<W*K$X!%Kh>Hm1cF`=;YpP$VBk{Nf;&yPrV5MCN$HJ-*q`R?-KFpe9dyT-a%L8;TSe~zkw_Q%?Tr&Kp&&XckMv84a;+)'
    '!1v84bl}$6Q83~MRpkAO3a%p8P|%Y>J$4&Q6CJ~_E{1h6tczh?4C`W87sI+3*2S<chIKKli(y?1>ta|J!@3yO{Vc<}Io(5^(2z^L'
    'CsC=6I=QZR^3(X?$JyTd@J2R>@nizr4ICIAe@8!!e)_rk=_(5!$UQZ9?&<DR9h)>AzVBpux^9n{&1$aq{K;jwyAeLPz5RdF42Cf'
)

class NativeUploadResultsTests(unittest.TestCase):
    git = ImmutableRepositoryTests.git
    write = ImmutableRepositoryTests.write
    commit = ImmutableRepositoryTests.commit

    def setUp(self):
        import sys
        SelectedResultTests.setUp(self)
        self.write(RESULTS.WORKFLOW,(ROOT / CODEQL._UPLOAD_RESULTS_TEMPLATE).read_text())
        self.write('.github/workflows/project-tests.yml',(ROOT /
            'tools/repository-checks/workflows/producers/protected-project-tests-optional-leaf.yml').read_text())
        self.write('tools/repository-checks/workflows/metadata-edits/pr-metadata-context.yml',
            (ROOT / 'tools/repository-checks/workflows/metadata-edits/pr-metadata-context.yml').read_text())
        self.write('.github/workflows/pr-metadata-context.yml',
            (ROOT / 'tools/repository-checks/workflows/metadata-edits/pr-metadata-context.yml').read_text())
        for relative in ('tools/repository-checks/codeql.py','tools/repository-checks/codeql_results.py',
                         'tools/repository-checks/metadata_context.py',CODEQL._UPLOAD_RESULTS_TEMPLATE,
                         'tools/repository-checks/workflows/metadata-edits/codeql-metadata.yml',
                         'tools/test-evidence/producer_api.py'):
            self.write(relative,(ROOT / relative).read_text())
        self.base = self.commit()
        self.write('tools/check.py','# independently changed Python input\n')
        self.head = self.commit()
        self.candidate = self.git('commit-tree',self.git('rev-parse','HEAD^{tree}'),
            '-p',self.base,'-p',self.head,'-m','Native upload exact merge')
        self.git('checkout','-q','--detach',self.candidate)
        self.pr['base']['sha'] = self.base; self.pr['head']['sha'] = self.head
        self.pr['merge_commit_sha'] = self.candidate
        self.pr['labels']=[]
        self.event['pull_request'] = deepcopy(self.pr)
        self.env.update(GITHUB_SHA=self.candidate,GITHUB_WORKFLOW_SHA=self.candidate)
        self.merge = {'sha':self.candidate,'parents':[{'sha':self.base},{'sha':self.head}],
            'commit':{'tree':{'sha':self.git('rev-parse',self.candidate+'^{tree}')}}}
        self.refs = {'heads/main':self.base,'heads/fix/main/example':self.head,'pull/42/merge':self.candidate}
        self.run.update(head_sha=self.head,check_suite_id=501,run_number=10,
            display_title='Ordinary PR checks',updated_at='2026-10-15T21:30:00Z',
            pull_requests=[{'number':42}],referenced_workflows=[{'path':RESULTS.REPOSITORY +
                '/.github/workflows/pr-metadata-context.yml@' + self.candidate,
                'sha':self.candidate,'ref':'refs/pull/42/merge'}])
        # Use the exact protected module constant, never a caller title claim.
        sys.path.insert(0,str(ROOT / 'tools/test-evidence'))
        import producer_api
        self.A = producer_api
        self.run['display_title'] = self.A.ORDINARY_RUN_NAME
        self.attempt = 1; self.app = 15368
        self.runs = {1:deepcopy(self.run)}
        def step(name,start,end,conclusion='success'):
            return {'name':name,'status':'completed','conclusion':conclusion,
                'started_at':'2026-10-15T21:00:' + start + 'Z',
                'completed_at':'2026-10-15T21:00:' + end + 'Z'}
        def job(identity,name,start='00',end='30',steps=None):
            return {'id':identity,'name':name,'run_id':12,'run_attempt':1,'head_sha':self.head,
                'status':'completed','conclusion':'success','started_at':'2026-10-15T21:00:' + start + 'Z',
                'completed_at':'2026-10-15T21:00:' + end + 'Z',
                'check_run_url':f'https://api.github.com/{RESULTS.PREFIX}/check-runs/{identity}','steps':steps or []}
        self.jobs = [job(80,'Select affected CodeQL languages',end='01'),
            job(81,'CodeQL (python)',start='01',steps=[
                step('Require reviewed CodeQL extractor version','02','03'),step('Analyze','10','20'),
                step('Record the native CodeQL upload identity','21','22'),
                step('Publish the native CodeQL upload identity','23','29')]),
            job(82,self.A.METADATA_JOB,end='01',steps=[step(self.A.ORDINARY_SOURCE_STEP + ' (diagnostics absent)','00','01')]),
            job(83,'codeql-security-results',start='30',end='40',steps=[
                step('Require current selected-language security results','31','39')])]
        self.jobs[-1].update(status='in_progress',conclusion=None,completed_at=None)
        self.attempt_jobs = {1:self.jobs}
        self.upload = '3771cd18-cc98-11f1-9b96-0ef876cdb593'
        self.analyses[0].update(commit_sha=self.candidate,created_at='2026-10-15T21:24:22Z',sarif_id=self.upload)
        self.statuses = {self.upload:{'processing_status':'complete','errors':None,
            'analyses_url':'https://api.github.com/' + RESULTS.PREFIX + '/code-scanning/analyses?sarif_id=' + self.upload}}
        self.artifacts=[]; self.archives={}
        self.add_artifact(1)
        protected = tempfile.TemporaryDirectory(prefix='codeql-native-default-'); self.addCleanup(protected.cleanup)
        self.protected = Path(protected.name)
        subprocess.run(['git','clone','-q','--no-hardlinks',str(self.root),str(self.protected)],check=True,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        subprocess.run(['git','checkout','-q','--detach',self.base],cwd=self.protected,check=True)
        self.api = NativeUploadApi(self)

    def add_artifact(self, attempt, *, extra=None, language='python', upload=None):
        import io,zipfile
        payload = {'schema':1,'kind':'native-codeql-upload-id','repository':RESULTS.REPOSITORY,
            'repository_id':RESULTS.REPOSITORY_ID,'run_id':12,'run_attempt':attempt,'language':language,
            'source_commit':self.candidate,'ref':self.env['GITHUB_REF'],'workflow':RESULTS.WORKFLOW,
            'workflow_sha':self.candidate,'sarif_id':self.upload if upload is None else upload}
        if extra: payload.update(extra)
        raw = io.BytesIO()
        with zipfile.ZipFile(raw,'w') as archive: archive.writestr('upload.json',json.dumps(payload))
        value = raw.getvalue(); identity = (100 if language == 'python' else 200) + attempt
        self.archives[identity] = value
        self.artifacts.append({'id':identity,'name':f'codeql-upload-12-{attempt}-{language}',
            'digest':'sha256:' + hashlib.sha256(value).hexdigest(),'size_in_bytes':len(value),'expired':False,
            'created_at':'2026-10-15T21:00:25Z' if attempt == 1 else '2026-10-15T21:31:25Z',
            'expires_at':'2026-10-29T21:00:25Z','workflow_run':{'id':12,'repository_id':RESULTS.REPOSITORY_ID,
                'head_repository_id':RESULTS.REPOSITORY_ID,'head_sha':self.head}})

    def retry(self, *, fresh=False, complete=False):
        self.attempt = 2; self.env['GITHUB_RUN_ATTEMPT'] = '2'
        self.runs[1].update(status='completed',conclusion='failure')
        self.jobs[-1].update(status='completed',conclusion='failure',completed_at='2026-10-15T21:30:00Z')
        self.jobs[-1]['steps'][0]['conclusion']='failure'
        second = deepcopy(self.runs[1]); second.update(run_attempt=2,check_suite_id=502,
            run_started_at='2026-10-15T21:31:00Z',updated_at='2026-10-15T21:40:00Z',
            status='completed' if complete else 'in_progress',conclusion='success' if complete else None)
        self.runs[2] = second
        rows = deepcopy(self.jobs if fresh else self.jobs[-1:])
        for row in rows:
            row.update(id=row['id']+100,run_attempt=2,conclusion='success',status='completed')
            row['check_run_url']=f"https://api.github.com/{RESULTS.PREFIX}/check-runs/{row['id']}"
            for key in ('started_at','completed_at'):
                if row[key]: row[key]=row[key].replace('21:00:','21:31:').replace('21:30:','21:32:')
            for step in row['steps']:
                step['conclusion']='success'
                for key in ('started_at','completed_at'): step[key]=step[key].replace('21:00:','21:31:')
            if row['name']=='codeql-security-results' and not complete: row.update(status='in_progress',conclusion=None,completed_at=None)
        self.attempt_jobs[2]=rows
        if fresh:
            old=self.upload; self.upload='4771cd18-cc98-11f1-9b96-0ef876cdb593'
            self.statuses[self.upload]=deepcopy(self.statuses[old])
            self.statuses[self.upload]['analyses_url']=self.statuses[self.upload]['analyses_url'].replace(old,self.upload)
            self.analyses[0].update(sarif_id=self.upload,created_at='2026-10-15T21:54:22Z')
            self.add_artifact(2)

    def verify(self, **options):
        with patch.object(RESULTS,'ROOT',self.protected):
            return RESULTS.Verifier(self.root,self.event,self.env,api=self.api,**options).verify(processing_seconds=0)

    def test_late_processed_native_upload_passes_without_relaxing_legacy_window(self):
        result=self.verify()
        self.assertEqual((result['analysis_attempt'],result['result_attempt']),(1,1))
        self.assertEqual(result['native_uploads'][0]['sarif_id'],self.upload)
        reader=RESULTS.Verifier(self.root,self.event,self.env,api=self.api)
        reader.pinned=True
        windows=reader.jobs(reader.context(),['python'])
        self.assertEqual(reader.analyses(['python'],windows),{})

    def branch_upload_context(self, event, target='main'):
        self.head = self.candidate
        ref = 'refs/heads/'+target
        self.env.update(GITHUB_EVENT_NAME=event, GITHUB_REF=ref,
            GITHUB_REF_TYPE='branch', GITHUB_WORKFLOW_REF=RESULTS.REPOSITORY+'/'+RESULTS.WORKFLOW+'@'+ref)
        self.event = {'repository':deepcopy(self.repo), 'before':self.base,
            'after':self.candidate, 'deleted':False, 'ref':ref}
        self.refs['heads/'+target] = self.candidate
        if target == 'main':
            subprocess.run(['git','checkout','-q','--detach',self.candidate],cwd=self.protected,check=True)
        self.runs[1].update(event=event, head_sha=self.candidate, head_branch=target,
            pull_requests=[], referenced_workflows=[])
        for row in self.jobs:
            row['head_sha'] = self.candidate
            if row['name'] == self.A.METADATA_JOB:
                row.update(name='Authenticate PR text edit', conclusion='skipped', steps=[])
        self.analyses[0]['ref'] = ref
        self.artifacts.clear()
        self.add_artifact(1)

    def test_native_push_upload_verifies_skipped_call_on_all_seven_targets(self):
        for target in sorted(RESULTS.TARGETS):
            with self.subTest(target=target):
                self.setUp()
                self.branch_upload_context('push', target)
                result = self.verify()
                self.assertEqual(result['languages'], ['python'])
                self.assertEqual(result['native_uploads'][0]['artifact_id'], 101)

    def test_native_schedule_upload_verifies_both_languages_and_skipped_call(self):
        self.branch_upload_context('schedule')
        self.env['CODEQL_EXPECTED_LANGUAGES'] = json.dumps(list(CODEQL.LANGUAGES))
        javascript = deepcopy(next(row for row in self.jobs if row['name']=='CodeQL (python)'))
        javascript.update(id=84, name='CodeQL (javascript-typescript)',
            check_run_url=f'https://api.github.com/{RESULTS.PREFIX}/check-runs/84')
        self.jobs.append(javascript)
        upload = '5771cd18-cc98-11f1-9b96-0ef876cdb593'
        self.statuses[upload] = deepcopy(self.statuses[self.upload])
        self.statuses[upload]['analyses_url'] = self.statuses[upload]['analyses_url'].replace(self.upload,upload)
        analysis = deepcopy(self.analyses[0])
        analysis.update(id=92, sarif_id=upload, category='/language:javascript-typescript',
            environment='{"language":"javascript-typescript"}')
        self.analyses.append(analysis)
        self.add_artifact(1, language='javascript-typescript', upload=upload)
        self.assertEqual(self.verify()['languages'], list(CODEQL.LANGUAGES))

    def test_branch_attempt_requires_exact_skipped_parent_job(self):
        for event in ('push', 'schedule'):
            with self.subTest(event=event):
                self.setUp()
                self.branch_upload_context(event)
                adapter = self.A.Adapter(self.api)
                result = adapter.codeql_result_attempts(12, self.candidate, self.head, attempt=1)
                self.assertEqual(result['languages'], ['python'])
                metadata = next(row for row in self.jobs if row['name']=='Authenticate PR text edit')
                for name, conclusion in ((self.A.METADATA_JOB, 'skipped'),
                        ('Authenticate PR text edit', 'success')):
                    metadata.update(name=name, conclusion=conclusion)
                    with self.subTest(name=name, conclusion=conclusion), self.assertRaises(ValueError):
                        adapter.codeql_result_attempts(12, self.candidate, self.head, attempt=1)
                metadata.update(name='Authenticate PR text edit', conclusion='skipped')

    def test_pr_attempt_rejects_branch_skipped_parent_job(self):
        metadata = next(row for row in self.jobs if row['name']==self.A.METADATA_JOB)
        metadata.update(name='Authenticate PR text edit', conclusion='skipped', steps=[])
        with self.assertRaises(ValueError):
            self.A.Adapter(self.api).codeql_result_attempts(12,self.candidate,self.head,attempt=1)

    def test_document_only_native_result_and_retry_need_no_analysis_or_alert_inventory(self):
        self.git('checkout','-q','--detach',self.base)
        self.write('docs/native-upload.md','# Documentation-only native result fixture\n')
        self.head=self.commit()
        self.candidate=self.git('commit-tree',self.git('rev-parse','HEAD^{tree}'),
            '-p',self.base,'-p',self.head,'-m','Document-only merge')
        self.git('checkout','-q','--detach',self.candidate)
        self.pr['head']['sha']=self.head; self.pr['merge_commit_sha']=self.candidate
        self.event['pull_request']=deepcopy(self.pr)
        self.env.update(GITHUB_SHA=self.candidate,GITHUB_WORKFLOW_SHA=self.candidate,CODEQL_EXPECTED_LANGUAGES='[]')
        self.refs.update({'heads/fix/main/example':self.head,'pull/42/merge':self.candidate})
        self.merge={'sha':self.candidate,'parents':[{'sha':self.base},{'sha':self.head}],
            'commit':{'tree':{'sha':self.git('rev-parse',self.candidate+'^{tree}')}}}
        self.runs[1]['head_sha']=self.head
        self.runs[1]['referenced_workflows'][0].update(sha=self.candidate,
            path=RESULTS.REPOSITORY+'/'+self.A.METADATA_WORKFLOW+'@'+self.candidate)
        self.jobs[:]=[row for row in self.jobs if row['name']!='CodeQL (python)']
        for row in self.jobs: row['head_sha']=self.head
        self.artifacts=[]; self.analyses=[]
        for retry in (False,True):
            with self.subTest(retry=retry):
                if retry: self.retry()
                self.api.calls=[]; result=self.verify()
                self.assertEqual(result['languages'],[])
                self.assertEqual((result['analysis_attempt'],result['result_attempt']),(1,2 if retry else 1))
                self.assertFalse(any('/code-scanning/' in endpoint for endpoint in self.api.calls))

    def carried_retry(self, *, complete=False):
        """Mirror GitHub's real new-ID/old-clock retry inventory shape."""
        self.retry(complete=complete)
        carried=deepcopy(self.jobs[:-1])
        for row in carried:
            row.update(id=row['id']+200,run_attempt=2)
            row['check_run_url']=f"https://api.github.com/{RESULTS.PREFIX}/check-runs/{row['id']}"
        self.attempt_jobs[2].extend(carried)

    def test_carried_result_retry_uses_only_original_analysis_and_upload(self):
        self.carried_retry()
        try:
            result=self.verify()
        except ValueError as error:
            self.fail('genuine carried original analysis must remain usable: '+str(error))
        self.assertEqual((result['analysis_attempt'],result['result_attempt']),(1,2))
        self.assertEqual(result['analyses'][0]['job_id'],81)
        self.assertEqual(result['native_uploads'][0]['artifact_id'],101)
        split=self.A.Adapter(self.api).codeql_result_attempts(12,self.candidate,self.head,attempt=2)
        self.assertEqual([job['id'] for job in split['analysis_jobs']],[80,81,82,83])
        self.assertEqual({job['id'] for job in split['carried_forward_jobs']},{280,281,282})
        self.assertEqual(set(split['native_checks']),{80,81,82,83,183})
        self.assertEqual(set(split['carried_forward_checks']),{280,281,282})
        self.assertFalse(any(item['name'].startswith('codeql-upload-12-2-') for item in self.artifacts))

    def test_carried_retry_queued_result_remains_pending_never_completed_success(self):
        self.carried_retry()
        gate=self.attempt_jobs[2][0]
        gate.update(status='queued',conclusion=None,started_at=None,completed_at=None)
        adapter=self.A.Adapter(self.api)
        split=adapter.codeql_result_attempts(12,self.candidate,self.head,attempt=2)
        self.assertEqual(split['analysis_attempt'],1)
        self.assertEqual(split['result_jobs'][0]['status'],'queued')
        with self.assertRaises(ValueError):
            adapter.codeql_result_attempts(12,self.candidate,self.head,attempt=2,completed=True)

    def test_carried_execution_mutations_cannot_borrow_original_analysis(self):
        for change in ('step','time','runner','unknown','mixed','same-id','wrong-app','failed','gate-old-clock'):
            with self.subTest(change=change):
                self.setUp(); self.carried_retry()
                row=next(job for job in self.attempt_jobs[2] if job['name']=='CodeQL (python)')
                if change=='step': row['steps'][1]['name']='Different Analyze'
                elif change=='time': row['completed_at']='2026-10-15T21:00:29Z'
                elif change=='runner': row['runner_name']='unreviewed new execution'
                elif change=='unknown': row['new_execution_field']='unknown'
                elif change=='mixed':
                    row.update(started_at='2026-10-15T21:31:01Z',completed_at='2026-10-15T21:31:30Z')
                elif change=='same-id':
                    row['id']=81; row['check_run_url']=f'https://api.github.com/{RESULTS.PREFIX}/check-runs/81'
                elif change=='wrong-app': self.app=123
                elif change=='failed': row['conclusion']='failure'
                else: self.attempt_jobs[2][0]['started_at']='2026-10-15T21:00:30Z'
                with self.assertRaises(ValueError): self.verify()

    def test_carried_result_metadata_fast_path_uses_factory_analysis_attempt(self):
        ordinary_retry=self.retry
        def actual_shape_retry(*args,**options):
            ordinary_retry(*args,**options)
            if not options.get('fresh',False):
                rows=deepcopy(self.jobs[:-1])
                for row in rows:
                    row.update(id=row['id']+200,run_attempt=2)
                    row['check_run_url']=f"https://api.github.com/{RESULTS.PREFIX}/check-runs/{row['id']}"
                self.attempt_jobs[2].extend(rows)
        with patch.object(self,'retry',side_effect=actual_shape_retry):
            self.test_metadata_end_to_end_revalidates_gate_only_and_whole_fresh_second_attempts()

    def test_actual_failed_retry_API_rows_are_mirrors_not_new_analysis_or_pass(self):
        import base64,zlib
        raw=zlib.decompress(base64.b85decode(_CODEQL_CARRIED_RETRY_NATIVE))
        self.assertEqual(hashlib.sha256(raw).hexdigest(),'f1b6efa2ad3f4c0da524b909ebce55e1be798daed059fe6ef80f512d6cdadccb')
        fixture=json.loads(raw)
        class ActualRows:
            def json(self,endpoint):
                prefix=RESULTS.PREFIX+'/check-runs/'
                if not endpoint.startswith(prefix): raise AssertionError('unexpected fixture API')
                return deepcopy(fixture['checks'][endpoint[len(prefix):]])
        adapter=self.A.Adapter(ActualRows())
        originals=fixture['jobs1']['jobs']; current=fixture['jobs2']['jobs']; before=deepcopy(fixture)
        carried,checks=adapter._codeql_carried_jobs(current,originals,fixture['attempt2'],
            RESULTS.timestamp('2026-10-21T06:00:00Z'))
        self.assertEqual(len(carried),4)
        self.assertEqual({job['id'] for job in carried},{119061865711,119061866323,119061866351,119061912353})
        self.assertEqual(set(checks),{job['id'] for job in carried})
        self.assertEqual(fixture,before)
        self.assertEqual(fixture['attempt2']['conclusion'],'failure')
        self.assertEqual(next(job for job in current if job['name']=='codeql-security-results')['conclusion'],'failure')
        # The mirrored row has the new check ID/App2, but its original1 steps,
        # source, runner and execution times must remain exactly unchanged.
        for change in ('step','time','runner','origin','extra','group','check-App','check-source'):
            mutated=deepcopy(current); row=next(job for job in mutated if job['name']=='CodeQL (python)')
            with self.subTest(change=change):
                saved=deepcopy(fixture['checks'])
                if change=='step':row['steps'][0]['name']='forged step'
                elif change=='time':row['started_at']='2026-10-21T05:28:14Z'
                elif change=='runner':row['runner_id']=123
                elif change=='origin':row['head_sha']='a'*40
                elif change=='extra':row['unknown_execution']='forged'
                elif change=='group':row['runner_group_id']=123
                elif change=='check-App':fixture['checks'][str(row['id'])]['app']['id']=123
                else:fixture['checks'][str(row['id'])]['head_sha']='a'*40
                with self.assertRaises(ValueError):
                    adapter._codeql_carried_jobs(mutated,originals,fixture['attempt2'],
                        RESULTS.timestamp('2026-10-21T06:00:00Z'))
                fixture['checks']=saved

    def test_result_only_second_attempt_uses_original_native_analysis_and_artifact(self):
        self.retry(); result=self.verify()
        self.assertEqual((result['analysis_attempt'],result['result_attempt']),(1,2))
        self.assertEqual(result['analyses'][0]['job_id'],81)
        self.assertEqual(result['native_uploads'][0]['artifact_id'],101)

    def test_whole_fresh_second_attempt_uses_only_its_actual_analysis_artifact(self):
        self.retry(fresh=True); result=self.verify()
        self.assertEqual((result['analysis_attempt'],result['result_attempt']),(2,2))
        self.assertEqual(result['analyses'][0]['job_id'],181)
        self.assertEqual(result['native_uploads'][0]['artifact_id'],102)
        # A failed fresh analyzer cannot borrow the earlier successful analysis.
        self.attempt_jobs[2][1]['conclusion']='failure'
        with self.assertRaises(ValueError): self.verify()

    def test_native_attempt_mixing_extra_analyzer_failed_gate_and_app_are_blocked(self):
        for change in ('mixed','extra','failed','app','old-selector','original-gate','future-attempt','source-edge','PR-edge'):
            with self.subTest(change=change):
                self.setUp(); self.retry()
                if change=='mixed': self.attempt_jobs[2][0]['run_attempt']=1
                elif change=='extra': self.attempt_jobs[2].append(deepcopy(self.jobs[1]))
                elif change=='failed': self.runs[2].update(status='completed',conclusion='failure')
                elif change=='app': self.app=123
                elif change=='old-selector': self.jobs[0]['conclusion']='failure'
                elif change=='original-gate': self.jobs[-1]['steps'][0]['name']='Checkout'
                elif change=='source-edge': self.runs[2]['referenced_workflows'][0]['sha']=self.head
                elif change=='PR-edge': self.runs[2]['pull_requests']=[{'number':99}]
                else: self.runs[2]['run_attempt']=3
                with self.assertRaises(ValueError): self.verify()

    def test_wrong_upload_payload_hash_extra_member_and_expiry_never_authorize_analysis(self):
        import io,zipfile
        for change in ('M','attempt','language','ID','hash','extra','symlink','expired','foreign','duplicate'):
            with self.subTest(change=change):
                self.setUp()
                if change in ('M','attempt','language','ID'):
                    self.artifacts.clear(); self.add_artifact(1,extra={
                        'M':{'source_commit':self.head},'attempt':{'run_attempt':2},
                        'language':{'language':'javascript-typescript'},'ID':{'sarif_id':'not-an-upload'}}[change])
                elif change in ('extra','symlink'):
                    value=io.BytesIO()
                    with zipfile.ZipFile(value,'w') as archive:
                        archive.writestr('upload.json',json.dumps({}))
                        if change=='extra': archive.writestr('extra','unapproved')
                        else:
                            entry=zipfile.ZipInfo('alias'); entry.external_attr=0o120777 <<16; archive.writestr(entry,'upload.json')
                    self.archives[101]=value.getvalue(); self.artifacts[0].update(
                        digest='sha256:'+hashlib.sha256(value.getvalue()).hexdigest(),size_in_bytes=len(value.getvalue()))
                elif change=='hash': self.artifacts[0]['digest']='sha256:'+'0'*64
                elif change=='expired': self.artifacts[0]['expired']=True
                elif change=='foreign': self.artifacts[0]['workflow_run']['head_sha']=self.base
                else: self.artifacts.append(deepcopy(self.artifacts[0]))
                with self.assertRaises(ValueError): self.verify()

    def test_processing_pending_errors_wrong_id_source_or_category_fail_closed(self):
        for change in ('pending','error','unknown','wrong-ID','wrong-M','category','rules','URL','version'):
            with self.subTest(change=change):
                self.setUp()
                if change=='pending': self.statuses[self.upload]['processing_status']='pending'
                elif change=='error': self.statuses[self.upload]['errors']=['SARIF invalid']
                elif change=='unknown': self.statuses[self.upload]['processing_status']='failed'
                elif change=='wrong-ID': self.analyses[0]['sarif_id']='4771cd18-cc98-11f1-9b96-0ef876cdb593'
                elif change=='wrong-M': self.analyses[0]['commit_sha']=self.head
                elif change=='category': self.analyses[0]['category']='/language:javascript-typescript'
                elif change=='rules': self.analyses[0]['rules_count']=0
                elif change=='version': self.analyses[0]['tool']['version']='2.28.0'
                else: self.statuses[self.upload]['analyses_url']='https://example.com/analysis'
                with self.assertRaises(ValueError): self.verify()

    def test_default_native_artifact_and_current_pr_closing_drift_reject(self):
        for change in ('default','PR','artifact','job'):
            with self.subTest(change=change):
                self.setUp(); reads=[0]
                target={'default':'/git/ref/heads/main','PR':'/pulls/42','artifact':'/actions/runs/12/artifacts',
                    'job':'/actions/runs/12/attempts/1/jobs'}[change]
                def mutate(endpoint):
                    if target in endpoint:
                        reads[0]+=1
                        if reads[0]==2:
                            if change=='default': self.refs['heads/main']=self.head
                            elif change=='PR': self.pr['head']['sha']=self.base
                            elif change=='artifact': self.artifacts[0]['digest']='sha256:'+'0'*64
                            else: self.jobs[1]['steps'][0]['conclusion']='failure'
                self.api.change=mutate
                with self.assertRaises(ValueError): self.verify()

    def test_completed_retry_native_metadata_result_is_real_attempt_two_not_an_alias(self):
        self.retry(complete=True)
        adapter=self.A.Adapter(self.api)
        split=adapter.codeql_result_attempts(12,self.candidate,self.head,attempt=2,completed=True)
        self.assertEqual(split['analysis_run']['run_attempt'],1)
        self.assertEqual(split['result_run']['run_attempt'],2)
        self.assertEqual(split['analysis_run']['conclusion'],'failure')
        observed={'kind':'native-nonproducer-scheduling','qualification':False,'metadata_only':'true',
            'original_identity':{key:self.runs[2].get(key) for key in self.A._SCHEDULING_RUN_FIELDS},
            'original_run_id':12,'original_merge_sha':self.candidate,'binding':adapter.current(42)[0],
            'references':adapter.current(42)[1],'diagnostics':False}
        self.assertEqual(adapter.metadata_result_status(observed)['run_attempt'],2)
        result=adapter.metadata_result_success(observed)
        self.assertEqual((result['analysis_attempt'],result['result_attempt'],result['job_id']),(1,2,183))
        self.assertFalse(result['qualification'])
        self.runs[2]['conclusion']='failure'
        with self.assertRaises(ValueError): adapter.metadata_result_status(observed)

    def test_metadata_end_to_end_revalidates_gate_only_and_whole_fresh_second_attempts(self):
        from types import SimpleNamespace
        for fresh in (False,True):
            with self.subTest(fresh=fresh):
                self.setUp(); self.retry(fresh=fresh,complete=True)
                if fresh: self.jobs[2]['conclusion']='failure'
                self.metadata_run={**deepcopy(self.runs[2]),'id':13,'run_number':11,'run_attempt':1,'check_suite_id':513,
                    'status':'in_progress','conclusion':None,'display_title':self.A.NONPRODUCER_RUN_NAME,
                    'run_started_at':'2026-10-15T21:59:00Z','updated_at':'2026-10-15T21:59:21Z'}
                row=deepcopy(self.jobs[2]); row.update(id=240,run_id=13,run_attempt=1,
                    check_run_url=f'https://api.github.com/{RESULTS.PREFIX}/check-runs/240',
                    started_at='2026-10-15T21:59:01Z',completed_at='2026-10-15T21:59:20Z',
                    steps=[{'name':self.A.METADATA_STEP,'status':'completed','conclusion':'success',
                        'started_at':'2026-10-15T21:59:02Z','completed_at':'2026-10-15T21:59:19Z'}])
                self.metadata_jobs=[row]
                native={'number':42,'base_snapshot':self.base,'head':self.head,'merge':self.candidate,
                    'run_id':13,'helper_blob':self.git('rev-parse',self.base+':'+self.A.METADATA_SOURCE)}
                marker=SimpleNamespace(SOURCE_READY=True,SOURCE=self.A.METADATA_SOURCE,native=lambda *a,**k:deepcopy(native))
                _,post,_=RESULTS._metadata_modules()
                with patch.object(RESULTS,'_metadata_modules',return_value=(self.A,post,marker)), \
                        patch.object(post,'_source_qualified',return_value=True):
                    result=RESULTS.MetadataVerifier(self.protected,{}, {'GITHUB_JOB':'select'},api=self.api).verify(processing_seconds=0)
                self.assertEqual(result['analysis_attempt'],2 if fresh else 1)
                self.assertEqual(result['result_attempt'],2)
                self.assertFalse(result['qualification'])
                self.assertEqual(result['analyses'][0]['job_id'],181 if fresh else 81)
                adapter=self.A.Adapter(self.api)
                _,_,workflows=adapter._workflow_tuple(self.candidate,paths=self.A.METADATA_CALLERS[RESULTS.WORKFLOW])
                policy=self.A.MetadataPolicy(7,RESULTS.WORKFLOW,{'native-upload':workflows},
                    {'native-upload':adapter._metadata_source(self.base)})
                observed=adapter.metadata_schedule(42,13,policy)
                native_result=adapter.metadata_result_success(observed)
                self.assertEqual(native_result['analysis_attempt'],2 if fresh else 1)
                self.assertEqual(native_result['result_attempt'],2)
                self.assertFalse(native_result['qualification'])

    def test_upload_recipe_composes_with_exact_installed_project28_tuple(self):
        spec=importlib.util.spec_from_file_location('upload_project28_packages',ROOT / 'tools/repository-checks/package_checks.py')
        packages=importlib.util.module_from_spec(spec);spec.loader.exec_module(packages)
        rows=packages.workflow_generations()
        self.assertEqual(len(rows),28)
        tree=CODEQL.inputs.full_tree(ROOT,'HEAD')
        tree.update(deepcopy(rows[27]['workflows']))
        tree[RESULTS.WORKFLOW]={'mode':'100644','type':'blob','sha':CODEQL._UPLOAD_RESULTS_WORKFLOW}
        self.assertEqual(packages.validate_tree_wiring(tree),rows[27]['name'])
        self.assertEqual(self.git('rev-parse',self.base+':.github/workflows/project-tests.yml'),
            rows[27]['workflows']['.github/workflows/project-tests.yml']['sha'])
        self.assertEqual(self.verify()['languages'],['python'])
        tree['.github/workflows/project-tests.yml']['sha']='f'*40
        with self.assertRaises(ValueError): packages.validate_tree_wiring(tree)

    def test_passive_recipe_exposes_only_small_native_upload_identity_and_exact_generation(self):
        import yaml
        path=ROOT / CODEQL._UPLOAD_RESULTS_TEMPLATE; raw=path.read_bytes()
        self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),CODEQL._UPLOAD_RESULTS_WORKFLOW)
        value=yaml.safe_load(raw); analyze=value['jobs']['analyze']['steps']
        step=next(row for row in analyze if row.get('name')=='Analyze')
        self.assertEqual(step['id'],'analyze'); self.assertIs(step['with']['wait-for-processing'],False)
        record=next(row for row in analyze if row.get('name')=='Record the native CodeQL upload identity')
        self.assertIn("steps.analyze.outputs['sarif-id']",record['env']['CODEQL_SARIF_ID'])
        self.assertIn('attempt>0',record['run']); self.assertNotIn('GITHUB_TOKEN',record['run'])
        publish=next(row for row in analyze if row.get('name')=='Publish the native CodeQL upload identity')
        self.assertEqual(publish['with']['overwrite'],False)
        self.assertEqual(publish['with']['if-no-files-found'],'error')
        self.assertEqual(CODEQL.result_workflow_sources()[-1],(CODEQL._UPLOAD_RESULTS_WORKFLOW,CODEQL._SCHEDULING_SOURCE_WORKFLOW))
        self.assertFalse(path.is_symlink())
        self.assertIn(path.stat().st_mode & 0o777,(0o444,0o644))
        active=ROOT/RESULTS.WORKFLOW
        self.assertFalse(active.is_symlink())
        self.assertIn(active.stat().st_mode & 0o777,(0o444,0o644))
        active_raw=active.read_bytes()
        active_blob=hashlib.sha1(b'blob '+str(len(active_raw)).encode()+b'\0'+active_raw).hexdigest()
        self.assertIn(active_blob,(CODEQL._REQUIRED_CONTEXT_RESULTS_WORKFLOW,CODEQL._UPLOAD_RESULTS_WORKFLOW))
        if active_blob==CODEQL._UPLOAD_RESULTS_WORKFLOW:
            self.assertEqual(active_raw,raw)
        else:
            self.assertEqual(active_blob,CODEQL._REQUIRED_CONTEXT_RESULTS_WORKFLOW)
            self.assertNotEqual(active_raw,raw)


if __name__ == "__main__":
    unittest.main()
