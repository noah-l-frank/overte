#!/usr/bin/env python3
"""Pure protected affected-suite selection; no suite/build/runtime execution."""
from copy import deepcopy
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zlib
from unittest.mock import patch, Mock
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inputs


def blob(raw=b'fixed', *, mode='100644'):
    return {'mode':mode,'type':'blob','sha':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()}


def definition(scope='content'):
    return {'command':['python','contracts/test.py'],'layer':'host','scope':scope,'environment':'host-qt5-qt6',
        'closure':{'kind':'patterns','inputs':['contracts/**','source/**'],'required':['contracts/test.py']},
        'python_imports':{'roots':['contracts'],'reviewed':'sha256:'+'0'*64}}


class AffectedPlannerTests(unittest.TestCase):
    def setUp(self):
        self.tree={p:blob(p.encode(),mode='100755' if p=='tests/run-project-tests.py' else '100644')
                   for p in inputs.AFFECTED_AUTHORITY}
        self.tree['tests/platform-profile.json']=deepcopy(inputs._AFFECTED_SHARED_PROFILE)
        self.tree.update({'contracts/test.py':blob(b'fixed test'),'source/input.qml':blob(b'fixed data'),
            'tools/test-evidence/sandbox_host.py':blob(b'old controller'),'unrelated/readme.md':blob(b'data')})
        finite=definition();finite['python_imports']['reviewed']=inputs.python_import_digest(self.tree,['contracts'])
        self.registry={'schema':1,'control_inputs':['tests/run-project-tests.py','tools/test-evidence/**','*.py'],
            'suites':{'finite':finite,'unproved':{'command':['python','unknown.py'],'layer':'quick','scope':'content',
                'environment':'host-qt5-qt6','closure':{'kind':'repository','inputs':[],'required':[]}},
                'candidate':definition('candidate')}}
        self.dependencies={'schema':1,'lookup_digest':inputs.affected_lookup_digest(self.tree),'registry_digest':inputs._suite_definition_digest(self.registry),'suites':{
            n:{'kind':'repository' if n=='unproved' else 'reviewed-patterns',
               'definition_digest':inputs._suite_definition_digest(s),'setup':['host-full'] if n=='unproved' else ['python']}
            for n,s in self.registry['suites'].items()}}
        self.seal()
        self.candidate=deepcopy(self.tree)
        self.candidate['tools/test-evidence/sandbox_host.py']=blob(b'changed candidate controller')

    def seal(self):
        self.raw=json.dumps(self.dependencies,indent=2).encode()
        self.tree[inputs.AFFECTED_POLICY]=blob(self.raw)

    def plan(self,base=None,candidate=None,trusted=None,raw=None,registry=None):
        return inputs.plan_affected(registry or self.registry,self.raw if raw is None else raw,
            self.tree if base is None else base,self.candidate if candidate is None else candidate,
            self.tree if trusted is None else trusted)

    def test_changed_controller_selects_unproved_and_candidate_owners_individually(self):
        plan=self.plan()
        self.assertEqual(plan['required'],['unproved','candidate'])
        self.assertEqual(plan['omitted'],['finite'])
        self.assertFalse(plan['reusable'])
        self.assertEqual(plan['required_setup'],['host-full'])
        self.assertEqual(plan['paths'],['tools/test-evidence/sandbox_host.py'])

    def test_own_data_and_discovery_changes_select_their_suite(self):
        for path in ('source/input.qml','source/new.qml','contracts/data.json'):
            with self.subTest(path=path):
                candidate=deepcopy(self.candidate);candidate[path]=blob(b'changed')
                self.assertIn('finite',self.plan(candidate=candidate)['required'])

    def test_lookup_shadows_native_modules_pth_and_deletions_are_not_hidden(self):
        for path in ('contracts/json.py','contracts/sitecustomize.py','contracts/module.so','contracts/path.pth','contracts/test.py'):
            with self.subTest(path=path):
                candidate=deepcopy(self.candidate)
                if path in candidate:del candidate[path]
                else:candidate[path]=blob(b'new lookup candidate')
                with self.assertRaises(inputs.InputError):self.plan(candidate=candidate)

    def test_historical_unreviewed_module_on_both_sides_keeps_owner_required(self):
        base=deepcopy(self.tree);candidate=deepcopy(self.candidate)
        for tree in (base,candidate):tree['contracts/historical.py']=blob(b'child variant')
        with self.assertRaises(inputs.InputError):self.plan(base=base,candidate=candidate)

    def test_nonregular_inventory_anywhere_declines_even_if_unchanged(self):
        for mode,kind in (('120000','blob'),('160000','commit')):
            with self.subTest(mode=mode):
                base=deepcopy(self.tree);candidate=deepcopy(self.candidate)
                for tree in (base,candidate):tree['other/entry']={'mode':mode,'type':kind,'sha':'a'*40}
                with self.assertRaises(inputs.InputError):self.plan(base=base,candidate=candidate)

    def test_candidate_cannot_add_replace_remove_or_enable_its_graph(self):
        for which in ('candidate','base','trusted'):
            for operation in ('remove','change','mode'):
                trees={n:deepcopy(t) for n,t in (('base',self.tree),('candidate',self.candidate),('trusted',self.tree))}
                if operation=='remove':del trees[which][inputs.AFFECTED_POLICY]
                elif operation=='mode':trees[which][inputs.AFFECTED_POLICY]['mode']='100755'
                else:trees[which][inputs.AFFECTED_POLICY]=blob(b'candidate narrowed graph')
                with self.subTest(which=which,operation=operation),self.assertRaises(inputs.InputError):self.plan(**trees)

    def test_every_authority_change_declines_before_selection(self):
        for path in inputs.AFFECTED_AUTHORITY:
            candidate=deepcopy(self.candidate);candidate[path]=blob(b'new authority')
            with self.subTest(path=path),self.assertRaises(inputs.InputError):self.plan(candidate=candidate)

    def test_closed_policy_registry_definition_and_global_controls_are_bound(self):
        mutations=[]
        for change in ('schema','unknown','missing','definition','arbitrary-kind','setup','duplicate-setup'):
            value=deepcopy(self.dependencies)
            if change=='schema':value['schema']=True
            elif change=='unknown':value['force']=[]
            elif change=='missing':del value['suites']['unproved']
            elif change=='definition':value['suites']['finite']['definition_digest']='sha256:'+'f'*64
            elif change=='arbitrary-kind':value['suites']['finite']['kind']='caller-selected'
            elif change=='setup':value['suites']['unproved']['setup']=['python']
            else:value['suites']['finite']['setup']=['python','python']
            mutations.append((change,json.dumps(value).encode()))
        mutations += [('duplicate-key',self.raw.replace(b'"schema": 1',b'"schema":1,"schema":1')),
                      ('oversized',b' '*64001),('wrong-type','{}')]
        for change,raw in mutations:
            with self.subTest(change=change),self.assertRaises(inputs.InputError):self.plan(raw=raw)
        registry=deepcopy(self.registry);registry['control_inputs']=[]
        with self.assertRaises(inputs.InputError):self.plan(registry=registry)

    def test_missing_unknown_empty_and_wrong_policy_bytes_fail_closed(self):
        for tree in (None,{},[] ):
            with self.subTest(tree=tree),self.assertRaises(inputs.InputError):
                inputs.plan_affected(self.registry,self.raw,tree,self.candidate,self.tree)
        with self.assertRaises(inputs.InputError):self.plan(candidate=self.tree)
        with self.assertRaises(inputs.InputError):self.plan(raw=self.raw+b' ')


# Fixture-only projection of the REVIEWED PROPOSED SOURCE snapshot, not protected D.
# c33a233fbfd2af9268688b890608d6dcc783d187 / tree 4b840cafcaa88da82a412c7697b8c3f8667ad3ec.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = '722507c3fb7ed51ca20315393692ccc987eca61deb956821a032ddff193e445b'
_MAIN_PROJECTION_B85 = (
    (
    (
    (
    (
    (
    'c-qa~>vkMhk{#gxevJM-Xy*MgPvPa||5$k?O9W78pdg7eYu?>oWECi~8>q}GaBPq5QHzrMoXX4-Ct}CmJO1-;fB(EYe0k|Vbr0jy'
    'emCCi|9F_5ZVpe~!}B~n{r$J+{lnk>{XhS9zaOW+{rlh2B&mwxZ~ykU=P#YV&9Wr*KV_OVLpu0RNm|eIl=tIMR>{z$bCS<vn)?56'
    '`1Tn81^wN=|J#54+xKOA3k_dx9`|><;oHh;eV_a9s-~)~ld+qIrmE|qpOU0b=Dh01WUi~COPcprd+dg<-RJ4%kNwlv`ELKm&F9Il'
    '?GC&B!}HqWQ#F=tn-xV_j#X<9#WYNFHx6~0xBgMrC$%5_{^C#5<NkSf*gt){8NN)z*R>VPp{TRjbFI^69>;c?rgkoiIVr~04{e(+'
    '&x)xp-e2)BJs)nKUv`J-W}F_UhjDrscGK!FO|oi8%c`HoI&bTy>hol7n!M=Be(akf?K3aDuePkaw$@mceVfhknfPz)vaTzqy7dJW'
    'O<Rp!Ri#Crdav)V_4+EGz1*ki;c)Yhm+o#i?}p{A{{7qi-TSMz{XA52Q)hXf&ShI<)!e4Jr{331mQ+nqboJ~L-?aME{<mp3+{ABx'
    'KEJHPl4o7nb;U5uQ(g9HQKrS1)?L~TNm`BG`J7GdmSz9-qdL2EllH@$ws}5{Ly?zFR!!MB6=~Yl&eAZ9#W)T1@W%7*pDZUb40k(E'
    '`O~ob^xO3Cb@%Z6>2nwF`SIKPtNO1WihdZfz9@>i&x&TOhAgeiX)GJReJ-c8u9NJNRUiFwFZ}$v#a!o8(M@%e_sLLaW8+KidmmOm'
    'XZ4)aO)^cxaM`;1{`{(QH`mGFGfHQ_FH71k$?`hyi=myGVyNeC=*lKfFIn~J<>Bm_Lt0c-HO^hz7ftQwb!}cHt=FAT{gf4>;55zi'
    'MQg^Fd^>!3+TTyN&%^%l{I71xB1t^iF3qcIXvD_0EAy^S%B&H)%3*BBCcW%gFFSbX?x$ygd%As^y2sta=d;@w9a@KaDyu@&oYG>-'
    '(+Jw#&{s*7mPH|?xT-GS#^e3%uz#3$=ht_Jr>e=zs%p}1xfZKDOG>e=DaSEOY_7J){NnZFULJ4%{C)1vuHXC4lA;*PvUW+7i6>EZ'
    'Z8BtTNMB^`DJ1Ua?&9@*fv(E4Yfr<RH(i;HqS>6+y+D%oX`Xa$t)a`(X3UE!+3?#VqWsZ)`}8m!BGTPH?OzVl?YQecKkT0myWxDa'
    '$=jjt8bPfb%Bk@B+h&?NS7%aIrB86|vrfv=Uc8N$@$u}!SyNZ(lnSVBlzMFA>D!6RbRIJYVRqFOQ(bRf`1s+SR$mgc_yiBrpNI1S'
    'sC3xtsmt;*Z-n~TRM}2-Uye>=I}K?fK2+=B_O6o`9`^UU;YQf|efR7}bpStgFXQfTd%E%BmOXnS%W~?9G3)wi%4gAV9E-LsiY8)W'
    'T9xrKJem6H-7Kdv4#!>hB9}ZLrRpjl#!LcNcpoy1UfgV(tet1cPBN$Ilt{Lc>o@Zvoje~Y$DvD`A*-4>DgE}Y9J1Qg;Fw7F%4ROR'
    'vB<M2y?PH{r>BSM?sj=gXLr(Oy$3SZ)iBn5Ue866&Hb2FWm>n@Tup6V`+l?e>Ydzo57O=NR*vsee)@L%W%nGp%Gq5dadB01(e%kQ'
    '2qX1Wy3E|7a)mUv!=x@erR#UK@BK@^uLQGdh{|Osd(pD!v%2>6c6l=9LnC?0Msci)e|r5c9#54=cekACr*1f$4{Xg?G+A9_O_j|}'
    'C90QYUJql_RhiE^E0T7cvZimZ-jbYZzT18Na@ZVet2&=$R7qEqy{lz%&eJBX8}TO|(3mG`wz=*<u%)$h%L6Etnn~T}NnT}5nnl(n'
    '%koHCZ!c+b#Y;9`y#;B<DA?_Ocd&22Kce$lfNw=T*v{%V&meE=M%?c!!FTRe$#Xi0Kgsov<@w-To&Q)`pGF-^_if%t?bCT~eYb-L'
    'RVyd!y3E`11E=WFJ$;@w-vYCQH|d5^_Ayt!k;%bMi@NlY)bWJWercOb*T1D>w)%P%^!t~Gv0Di=K9kmmBR%(864*sojs8zr4Mmpr'
    'RgrY5I-!_;(VjM3Px+)cE8D(m^CF+13PaM*%E8o^+>Acsh&aQXd~iq09d)}Y3=XCIJxg7fF2*LCx^A5M#+R+i>GC`;OEq-)(f2kz'
    '{JwkIKivBlkFV~0S(gRQ6DUF6_kB53u86*?rlPK<uIV$+%#A+gAKTOBTeRtly317+HOQoa(Ts)aRsyEH?B%|d18+yguiMV;P7?U}'
    'czdj5f_>lkpvF2I5`nn)vii0f+Qwy(yVLq<&TRK%Tf6F(?`wdTgxEJew>5CB9->Zc+AJO9BE?+f-PjJlXluj%e!)rB9#}PZQ{GDC'
    'i#8P~<9#-gX5rgzt1<0o_iU4ozh+m@)9=&6N>#07ZHF>mpdwNLNIb75NnIaVJ~hzLTp;g0wx3OrKzdlTc|Z)~G`B-rb#B})sT}?R'
    'Ae&ZRXsXQp;8uRfitcw?zVQ}#*ag6lPq~__2FSt`)4l^4*d3&8O2@94Ken&SQzP%KlQY6W%03U6Yfj)0X_XZ|@hWdJJ1mm9|LDHt'
    'N4LY%1lv9Ay1VBUbU?{f6q$>*X?tngJbPG?6QsRlH_eA$>NK_=-qV(pAb0uuaQqLns7q64URDi;gxur}h&_W!j#>7x&0LYa$szkW'
    't<tJ;!j#QjIm`a*axT)TOI<mcdoaz0k8SLE|MCRX8uni%xb<*8o3q}SD2h5yCQ!C%%-af7-9`y84=pq|9Y9PU+)`wfw;M`W2$Osb'
    '*q3Q}wB6jhXELbEm}l_&bQYePq)Cfkv7Ncw-My>;y-m>!Q#X}eQk31GVWM$Sc5;>>^O%M_Z(0qM^n>5^;r?;n-A&)Cwe!cncIj7n'
    'r#b@%iI^2w#$)N_yGcN@Iy+feeeml(JiR<0+$3M8Z%=E`s539WbiRvzN`2F<cQmws(xgv)R8un-V>5lEBDi2Pk!2@&TEj%Mwwb*>'
    '9S<F^qEDQ#q1T*fVG-M|{}V`k`X}dai!p}=`YfQMb?LrP&?hq4GVM!=ER42nhNjt;VSj#E!rk<Azk7aOdWdI}vA%8fBcjnUH&Z{t'
    'G&D<<iM=*cF*QTdjbhHWpZsMXZ-2jE3;1zCt0$UHzj7$FWiz2oecrgi$0QxWagNEhHIHe_`Ov9@l{t91_Qx1m6ySSG0bF2{*_|_{'
    'xjl^A@}~!v|L@anH{S2g-y}L4k`M7uYqF|zKcEuhJan3Q{%;Q8DijPG3xd<CTfoF5afvI-qCl#LX{Z$Tg%b}23HWGGt_cI%zNH^e'
    '(&ijv$kQq775VDJs9JS^M*ZnVuHmpJ+1R&0_>J}AkNuu4N2%5fZi{>zb0~jV7g69(t?XGZck)@QrPXF*eZk_#!gSa_O}D?f9v`Oj'
    'HAI9~!Azf{s7BRaRYRHEBr5k-GpbUjcEh|8qx*3O_xs<cr5JSutz3mET(ZuxIq93c3m8{gBk7F05iZuM+G~x6w%fjk%c9CKc;ZR!'
    'SSMOvn)K>~bk5VRbJ8Xk(1a>5wEgz=H-?sUoYjs^7qvDVrEZ+KK-?Vh#z8C^;a%RHZ(sNrUp72*HIVnNnVY%3veYST<kEevxth6g'
    '0mPt_yh<)z`mYl9{2ii^ok)8+scT>%btbcKJa~Y9;&rER5((LS{qm=7-|+Zy{y8{z>42(`1Qd-HqRw!WRZwF0oPI)6YqYdiY-HQ|'
    '`CMvprm{ZGPRW-nb#@-|%pWuzbfL=nF}eH`kgzXY4o9JTI*$eQy_+<PE~{H*5c0~>o`xwaeT0+X*vK@-vA=o?+nz-2`CBj1^zM)i'
    'Mt{XN@bEkJ@#JQgT$S>SE4K0N@MZt74bY5_Uy%URaURr9C_+<NYoZi@6+I@^vFBA>@i3mI&oCW@%6R+7Q}_6|mSqinqWqnG6hc8@'
    'U@phL?DT|H<Ws6P5E;5FJ`BLp`6g^tsnaTpN$18QT8p5;S+_0gBSZ#6t<)wNwlBRsA!zHa?eZX(%$gC?n7EM&=vE;)7|ULlF(@$e'
    '1^3ZaS%LlnrkW0s<kG!_6{p)dbO8l+c7i)M3{}3N8an>+o880X%i)u^es^M3-N^87{+J}*U^Nxd+1=>XMV0EUFW+C#j+Ba^wE#rG'
    '-LuD%l^e38pLS#Qn`sQ<(~ldA(&M%}#G_jWjyhGMG))bX;UIOsioxksmehsXL!WqxuXY1C`rgLYNISC=5c!kGk_Fb_3LVD=)h?;E'
    'K1)n30j$|TnOQFDS90U|C8cV<&B#tQdqsrkfcI*#dTNl~98o-xx|=sH`3j9iti1Iex~Kd7)9s6YZzXFfGY7#PspA3<8>%77KTvDi'
    ')M+}SiKU8BVSMX8j+N)li7WBx`DyrnO&(d_*#9*;$@^P5a!R7WS~ATQJX3nxG^6fIn&O@oQm(FoX8_8bU(cpP`K_A|Z08j~ShjUO'
    '>n-{^LnRyrF;z%)e$^ZW{=_UDwhzhYjBs@2W)>3X@#{t=?VdM(K4ay)N&}}16qQYG;{nUWTT^>?W9g4%iPZ-B)#|?bm)+fX#DBH|'
    't|D852$Xd#29O?AG718CpMikD$h2GX;Af^E-`oka`{A*z@K7APcwR!nfUgOuOQIXB$$*hlWx;qzr?&X`#&+63Pp>caL^?l@Ea+2Z'
    '*mI3;d5V`arqS)lHH<TSI{ZR}^R#Jy!OkAsS$CQq-IG?|`LApep?g@guC-JTb}o8q^MjOn)EG6dwsBMT<;Qn*OnStKA3C(>FV((7'
    '@~VN0-d!S4jSl44`qX@J*tSpssDIOcd~27)u2G)h+xOw)&x_w#qv?;}6rofDIl3O|weA-j%Tv0(yI(5Vm;Uif_q@W6Mw+aIdD|P*'
    'v4JMYkUD@d0)P_Ng`@p2^uOR6J6?sG;OknSQ<Q-13>g5iZWhRNp86rFvLQ%nnFp6lAK%pT?(@Qq*pY&$d^a4*60qnpRP+I~3m|SY'
    '_f6w4Xk85wT@MVtI{i27ZOL>twB4I&OxtL$A-}f1J=L&^Xo7{7N<?g=X@oxif<y2s1USE)S^pRd6eKIP0Sz@^p(?A?1#OuIAgy2O'
    'M!0f2uY34(*;T3EZ&AI!eCz|RYTQgX%7_xETRqeQYMa(qzs2vnS}w{J)=fZH$l310PMj(nMTs{Y3$EK|c?cB{n?L+~P9gq0q?2cv'
    'V#$@`LPmvvu;R0b@gM|I9j&~Db{6GF_p;%b(S{U3>O;vO4Ury*;dw6~rfz_44xMaNKfC_$R!;T9&xdU#0whr`&9%-+*Mr#eJgG;d'
    '|JlEldtuR00f2vWYZq(@C<yQo74fwS2~{7YRry~^)1<F6^>x7G$(d?$+&zVW=(Mvbn_gQH3n1GKhjlEN9L=pe=!Pn7o1u+-s!bpe'
    'RSpw}lPhbwI=^HOYelRoO%akcWvx6=5K!dh!DZG~8c8t}lr=5c_TRm+(WKv-P%{*>UOc)`PIS_$;gKz*YzWk;E=1bC^>MoXx`%lU'
    'wU{yuek86giekNgXrdoRv@{^S^uGS2@}l2jaE|*yEiTLK?mpe3>i;0ox{ZIf(yz0u519Tfi~DTq;a4R^iLa}u@;;d2dEHItmkr9{'
    'c}%7qXS8#Dfo75jQB`8ls<`{muJ~qh0Z%V0KflZ|;aUFkO0T!g`!ZmbelF`OLm8xnsugXyE>%STiD+hg<3|PjH9Z6>{;7L9>?o%s'
    '$_vxwu)-miosXDz&|p^yIZl!edPQZV#X+mgX6+*Fva?GrUy8)s->=fy(x?SA^bvjs9H|7Kbxc5R)ueE5hLW0540!8~{g(xg#E|pf'
    'Nf*donI~9k0N+}hu|j|fWnZfrD35jVu=4w!`~Cgx?{4jJJ*5F-wrc9q(FTsd_)))LH8X)Ec(<1sj{Vra)x17tE93P0F5aU0?(q<-'
    'Z%Oo$5GSCK1YqgFPqA1-)uqgLN%r{f$*Aestt~oskB89CED`2kR`m4#daj;Y;x*z%HBj8X(`C}Xh9wB2b)Ak4<P^Jo+ltTMRn?D*'
    'g71HPKCorcQ5}-Tr>mzyw1d0?LQn0W#sE$<R`P!6uH3=n<L>4DcFRVFU~B6pP4&{o%_nl>Q7n(-EMh%cFbYFgUbvA>4*_4M(q8Mu'
    '+aidfH83DUj*x$JS=A3sN9{mrc<I{1{?7ffKc?^}+T;4SpBI7L_tb0z!wNLDzvcyaJ(zq1DSFI}EPuRoHw$2V`+3rEUu!ucdZ8FQ'
    '3%dEjS`qmeMnlm|B+Eq&Nru6x$~JFd`3^R{3zUKp-E0=nf@)S4$W}9rP8RKdn34AY)5<o#i~m2~fzHMK%92R7jkE$IF(I$@JI4rs'
    'wNR^_t}3pv3$$MItxJy6^H<%g+x_rzxBGL`vj?lj()w1QlS;~i#-kM1IcW>@a$F_^CfUiATloC=a{C28@@{%wfi?9MN5v!Ezjldc'
    'e_G@c6Oc|Gy|oO-&fA!hU$76PXxBTc`wGuUi$+vH9K#{4<~iDaW0Xw6MJUM0scZ5){WTj}0HzJi=m5jZ&~4=O`@^X7OD$1SA(JXh'
    '@d~HlUFFr4yK-?qVMaXfzWUqOzdM_Fse({b+CmQ0N=<-FwT>)B=Gf?VjUkKHLddS%&k=#>zTF9EQ6o*e_paEVA=L!&S9X-lRar)N'
    'zC<CJ*mx9?zcXJ@c~9lF$Liw!u(A+12HKIVY1I-~G*l9v*{B8=QU}R*{-&$Q+xxlS4_`MO?yiX*j-tBG!}Ec@MoT3PA%AG1=3p(z'
    '{O4io!l!Dn-#v_L>`RquD8mG^A*D<AjUs^}ER9uQXQ|*yggR84&-3GM*cYGX-Jgd*{TJ}_d|V67j)YDgq4yYNanJ>%lYx3bj@2Nt'
    'j=H&Q{l6$vo39mRdKYw4%_FR_=u@kgiyV~*mq>544t5`)?6QqKh1JT__Dzs6DTTsDM?njs>w4g7nB9=X5Xqzs0V?2S>n8lS22taJ'
    'JHCjNY77-J5UlM{h+L}DPv0k5#XR8>44snn${if@oz2f96dkJEfVqf(74iDuh$C`hK0m~8d4bf@6r1n*-}nCZcCj>yYIP+#Nvjgw'
    'yIch5gTj_X%5PC&37wPzCs>8+Yxf%$Y#n|d9l91P90#I>t${<!f-I{KgCV_oweh^RAi>PH|ClyOuk_rZ3~}IHS6=kohQ=v_IaF?V'
    'nO+LL)_+)Aa*?9F*5xZY;WiW$tsZeY>Gv1OgfYbvAk3T^4P1X2FqGB;&NiL2&J)}z1-Ro@WYMu!eG>u6S_b%gdDLzX#n#1^U%EfF'
    'gX2Hm9{&xQ!QF<oYk;Oc-BHEP2BSuN2?HSIx`&UO<YUVaKE~vl?d%?+@r!fOzwq69x_x}<U%4>n_ax-Ie1W*o3Gf|LpnTN1YnUNv'
    'rPl%D^|<*T+Eb|8=%uDR*U}nujcG|}5i0Nk=ngD3pmXyHqP_>y<Ylney0<KmF4)fx?HlRAJRNrT=dUSuAO<`Ah_aVDIBqKvK&L~;'
    '*8vKRnf!O`uG!U{r=#0Dt%YW9A&DkEN3KTAGkQ=dmXIPuD=q|g01J3Xdd(j0mv*3*#M&Nsa|QYW;c3I`Ebu%Rwr_@Mmi>suXuth<'
    '%^t$u#~z->4bNh7Gv%Rp;(F#w0k>nv;GD2TAY~XUat46JTkcis`_LMVYW(p<4}R0fq2_K?!juM%Hi{u;qm-YshaG7bHFMlrReROP'
    'v4AzV$9wB|vd_Pt#NAw}2W79=TYZ3Jpj@0KlmHCCA-<aFy3+%j-#-BWPP_TX{oM+wPBKGYf`I5gVF;w&341YB8q$)G?>1GmkH26m'
    '@n`2T0~RY)tzSJYoHBky9*Y=*7>hYxPi^4b%~)N(mtbW+cRrRC^d?YD=yw{L6rvE=mNx~ymCwj%8onmzCDU}xMxML-N1C+f;0GUD'
    '`)kB~e*;fcVevR<hpEqG`?HEi3#~7a0x_z6G}BeF{}9UbaYF@AM9l#<s`bQcpN9U5K12sdz|<|E91waKV1Lafj-SVHrw}{82mG;+'
    'iHxu#p9uk62>5HrFUUu;9Jr2mS8qQy!<X*xDx>KRt7j#6!jSCXDC;guwc#p&ZZ``us`DErf$VO!hqLb{k0<LW5bl>1ga9D{z%}Xj'
    ')c97>HqfrbULa{<)8ugkq|$5;Vn-6}@pjqwp_bH44We52xRNBHexhwlKegP;q0y<~c_B552CA5<CeO=$`&o?`K71SQrc>TF3{FVo'
    'Z-+078^GPPUYCUq86}}ggf5qzej*SQSs-p7Bo4hm$UxftqCIUe_Cgxrqep}v&W6G)>Hh%sD&kLD6*RyH!?5`!8ya_9_YNzJ_l$&n'
    '&`Z<k?Zf7)3Zm7(&vU{a@@ZjR%~8hvk{vxw|9Dx8`N+)i>4<RryqG*jQppj>fhwYX+mPH6#uW8OH*~lEynEP$wN%<<uD~fSXjYfL'
    'Y-n{M`wzA(drCKC5uBHg?g;wv92$*>VcPUDK{o=yUHXW+rQTSZRtgn8#D0`Sgn-$t^x-F^;rLxOy|yRs$J<epXgRT96^>Z5c0s&M'
    'BE!S)ouw4h_|ZK*PX{;EXV~sT_xSu}zp^W$U1q;fNzswX3(!5@;waZFf?+WRK^#T<m+k81@owLphnnX=;T7<#M6r4KfG9-}b7sV6'
    'o#;U75t@oB`{<qy`>)f(i8gya*@EE)D|S$?bfs*Z@K7{D$02`ebAtCQw%1?1p>cc)H2!It;@@~!<p{dAl#SFcC@;`FywfJ^?3jh%'
    'G&V)%ibY$wc02w-G%9Yt91f400+W!aZ<;N<3SJF@L4oy&kl=p7vE)Kk@or74k8bFBc-lQ~x%zdrde+XoNrqB=Nuw(H1H$qOReo~^'
    '2^Fc5^8*`Nr<v-Jq~SoIq8u}su}W5T-G?bLCEw(7A)+e#s}KCRzwgB9<@)%`>-&7XPJO2xWegT><U|WbPFRV1gZ?UEVlxrOP9NOT'
    '-7ciI8_+ssN>fZ!&AsqPAp^x4A;XN+noO$LgqlZ0Dt^U&R5jCX%?KzQ?D(B)nQ$V}Inf-}u;_yxp+5HtH3YRzlMikv<V^hKHbrRS'
    'K1>M&pTwDl*($fdoA^G6^5LE~%Bo=%`L$a*GLF8Vu^$v?=U-hJE@g#2AQOU48ch>gN8etN!+WDA^HQBAziM0YS5(FgmaI||uPvOc'
    'csOAuV=WFfB#<vy<LyEwDY^6J7wv0ax3>wW=n3K|I);|0z*P>jdzm*Pj#vqeWJEuFa6@scZm_au%o5>f#(IT@`k))_h&Fn0%2f0m'
    'q@-vMr61hQk>&X0&>b)!SCti5t_X)xje?SuPJr|(4PLiuk;7bACvmvIH2vVNPWQ*l!^VfDV+)s+-@4m7C9JstU4thQI1dOOLm!;L'
    'ru5ovecm7T!6}z;pZ2zrZ6mUW;C0HVuZv(gB2*$!^a=p2#Tro#WAy6i9mqoPaRatIf5v*=8!~>OS)(<ml^UxqH%Cp;1WeZ6)cBsS'
    '-N@a3T<oll=27PnpCX*dY4uP@+C>B4(m<<I6KQ+L+y#}j$o+x6L@{)FNvH6==_&y`q=9KGUQsp8@yG*_%QPaqs_-YP6-la-k8Nxb'
    'QIE?>8}_TMh)B?+hX@n=Y+DrIA&BJ|cSMDXxM+ng;Lx>uI>91;J*M?7RcWh&H6J1*aZnP53v*C+^<{m^Vq|>O>GcJORoU&G-rq)W'
    'q>#df=}5qKniHJuIW^ZowI#pDOhfezvia3%$-_PxM}g+izk6b9jNjCKhW9@NS8-Z|3c)Fu!mw}v*Q6n5;)Qc{{jpzi$YVK#GyAd<'
    '6)9>MF(8trVN51U<Btad5sk+wrZfz|$LZ=D7PJ_jwVGeZ-iFkGth%sD4*j=Cz#T`^KmLGXZ{Pt{_{i#M{>Y9_))2RcFX6g(eml&7'
    'lju`eR<al_X|45j{V+|V=Y<_Z(Rg)gbSlZzL82qV;X3Icw7JeY_C3t1m2guq_;kp<Gu?wsHd$+GTz!u%H|e<T?#SHi+5*hlIOfY='
    '<%&RREqUE+)>=AW%udK&uHVaY$CGw!J?%t^g&g0zQ56;g?1TR}(TB>K)>8*V{$bun^}!wee!s!sBfLYPE(SkkQwFDQ<j|PfRnJyB'
    '#;uGJ>u$I@5Bj}{#P#<;)7H}aJPGzt8<2G#V=pY-ggvA?E2?Y$(#oW^`@l}7KZ7qH4eQOeqZV)LHVhujYT}@mFV&%;J8oA0Dxt!_'
    '?Cv9*+AU9K+WMH<lze*#S7gK*)RyqT!?<D*SA;<f3?vL$^7dmp+Ha`GjQfeKESS3{k&O7WsX{uZA_$`*eDjEi_4SZv?Boy_!~SW7'
    'a#%#No`<VLjl9h}lk8D^o+f!~7M0-~62K4a<3t7=*7SyGc9_L{%3$~`gIM?unm_F0@-a+N9C=FGe)`B(zTZ<K;7Xn|sF)d3LO7tj'
    'WGq#}G>31cK<Fz`)w|6d@n5l-_3j`5EYw2u>P~eX2#j_m)hhTWCWe`)!V_fbKd_mQ7p`chgtCyogu5PFzcLTAy&)#SNtLl<Bw!s6'
    'f`0hOE)L<=c^f3IRV+$594%4JYUz}O)P8i0g*%8{5G6roDxQzT-tRfYgcCyJzhd^pUxU@2v0Aw3t%jjz;;m__6opJjfc8i8)oIpW'
    'x##WD*jy3vbHS!Z1id4d!A`xXnERw{q2%->1AW4s{+dhDg9*(9Eak|tT@k-&y>TBbVklxCUTm1g@F!QKvy7($ah73i&#fNsSn<3X'
    '94!BNwYM#k?82O4lsADcwFb-ZM(b5nt;8;gh8PRu?UV<6(xU|S=l;Yih_czB1;<+>3G)t`Qq)+N;7lwgbT}3*G`g8aLwNyQ@y@=M'
    '5@GYM$l!-~S*(G%N0Jij?6UG;4V#6LorZJk0oKLUyE-*bw(dtN45IAG7IX&UoNK;eCgA83R=T7#GYtAl)2sLMBa3qDrX+naZZxVV'
    '6lGn5@E8nfdK`M)FsMB{n+wvdH#ZgkZ2O*;);A6Sc{lpF#1wD{^GYH#lBkQ+Nl?p^Yxgufb<bbeLO$#d-Mao8tb{w$hK7P=2mBO?'
    'JnUab>@f8L0<MBDyMQ0}PrEr`7Tbpdd1EoC)ciNo{~`>?LNg+9-YdM!A)19^>*^TrGwif+Q(-GKVowm%;r+*?G?w^@SxRW#tVCtX'
    'B+1=4er!`w4R5yV<Fk^_N7F#baTtRe)5p>$Q6$%agNJS?uddzEcO+%=h8VkM{XlqHPI0fs7^lR5G`S!NA||1KE=#`py~V@no^`t~'
    'h>z;sOm?UiF2m2D#!z>qqQd5k6}y<o>t1QE-O;K1lux~Uj$r{SP&||gm)-2Ea4%s&gPc6aDBe68UzKW$#EMX|`tWv+?VSDg>rL-1'
    'TsM78aHl!0IkP51JE__M6~gR{)=m5AgF9P#16%hLvj)phc<Id%I>^YhR!|mHqeTGXGRdZXb6n3wdwTxza)^X+`+WjB6_C=fYentK'
    'xh!e+xOowWsGt-ZG#`rB&HFlSWcjq8UnA!5vKUDp@D`+SyYtD3+iL=|sDlhLvo_aIbQ8i`eP`fHF^6|t+kRw6`~EjclPXo%#4Uap'
    'SBx;iP>If!9*sFa?pyec3FYvxF*LBm$L^L(5~ery^wS@$rj{m(dQ(l9*mE*skO67ow1h9osAh5d^%PN9x9@0T`#s%6D_$=7&-vwf'
    'G)e`8LYV*+LdPQ?nIj}X#v0&vAJ-r2jyEk=-rLNn-+g*Ar@uSZ^XIn``nlO%W*(KPb3q|B0<>VtA_2j`(SJs*y@2lg&Q?}ae-{LV'
    '1+zMIKI-J5k0vT&ez3r^@L9vyFSehnL)U{SPXy!TKL@$@d4<^;<0E)2dKy(Y<Dua}#O5Fb#F%mA88-pbls>YHwI?B>m_rb5b3RSt'
    'x+%t`WihCPK_s(R)I>fx$@Vn*_-Q`u;sDdrLErAWZwu*qMPn8`;uyfqP_7J0uZp>XJ0T}1p#kru+Wi7D)NvoAeBIN@>h7o_S*wr9'
    'y$~=XiU2g`aD;(rBS6Kx^&AzPt$N+gmu-VJ_w7>`S>WyG`0H99Jxp&YYQ{*FnKcngAg;|x;I)PZ=+78aE&FLM--ZAFam9))yhZAm'
    '3xKl=xWEkQ1Ey%>s==Qn`_*aas_L@EkFOv;gH7)Ns{+o*gbrzuwFz%h?I<j8JVp-cq0Kdfu(&`Ucam9!e&$rut!sIZVhN3zVPn7c'
    're$J!Yl{yO7j>>b#ePR1Ec?qgae_TxKZF$rI)(NW$Zr@u8yzwSEl<JCS0?CIKxy28w7Kwm)OX_av`reA#&ncXD-Pw3XO=n^fjW;S'
    'FYg)esHR3YFl@SP2M8tIGI4S{KY-X68Bl0;BEwKo@7>)_q#{nnfC<L_Z<@}X-NqtGS(k$JY3L8QSP<$|aZMl~tEmNV7)Wl!2k*;q'
    'E-!oyrx5+aBiLl2#>*lJZD<pdbt60)(Y6T7U>+!&!H>p8>MwjFdRo0u87FjQc^Yt3e%4=6VFBp?9cF&%&<;VVaho!|;MR57@-I7?'
    '-r=zFG19X6bv)zaz668m7p3%|oGVaRg48<%V3&^<ul@YTZml~V6LNzDsw@a)EPIGx?8a0kl^(MZ(03YI=*??~JN=Q?bRX6wF}Gmq'
    'w|Gt!OqMdt*Fe`LFaYjCccu%@BVdT-b{aDj%It$XS=9!aq{alG$uMxkgPfCYOoT-lGB#@Q-l8O%i~jO$#Of!m*G6iEAwMmJ6m?@v'
    'cm~;UzH?uMQ9@XN<$*6lo-TMfAqlz(9{0DOQVBkJljyZT%&UAjet*tK6Pt?vC!-l-k{GJ4K<d=sIZ^6X#r3=TZNFP|6^q8>cE0OA'
    'uh=q2>sgCD*h6C|1;Q;UF8Y*8Snd^eFos}d*YD`43&r+O=6+tAlEYGOj={=Y{)8;Z5>K%?6fi;h)>Vs{4932<*KY@FaZf>fdV6Ls'
    '%ulEdD^QM(Uby7tdFV{|i0SUR?95?nVq8Y3SWDg{YX#F30Q)kksnfptb7f2v?}|JEXigqf^H}jlkU4xa=sD1&BxbB;Yq03_r#f-z'
    '#c#483}trUj7!Iv<spx00XC_-CEK>F01N%dH?QhgtYi~T;n)vpOh6h#!I*~yej2<ecd1jVWaityR;r&`O#fum#jW$}nxV}c)YwQR'
    'I3Gd@P%$&U5~CrSgaz0cW>}*=r5o2jqRlG?fiYcGV+#n^0!G5!UOmGbYK%^W$4+83CG*A=PYQuoHSLyOn`sC#0+$q>39~?2v%HGz'
    'k?t(IHbb`bn^tq_*B$Ji$TpyUt5e777%ZTmj(N#3dy{$+_q|+%3S5MYqcQ?_HDmj}>>tN;aW73;vn%I8r=w}~gh>H9ubk-mVA}_C'
    'Kxc81uo-!a`MPmwjtoxHUynYRn)~xFo%2BxM5q||J%kh@4--5}5m+at33N(PJzlnfMaZ)<><ZNhH-b+~7Xv{8NG-y3ZVZpY6g$9B'
    '^eox>$d`%BD@0T}M&(!xwgLkRQhYaK=$Jl=EtEtdroOI<8g~0YOe0YL`8eDjULMxG)k1aS&Vtq=mXmQ!F{G15+IHBM$A~HFpkY<^'
    '8tX2|T0GtLadI;Ja*;@cGGdOA6!KAM)eus3bRp)qF}*0+vg)^of#_fqx;EO=1fLE8aKMgIku@<<+j?48ahR1wHQVh>a=c;jlb`C*'
    'p5S)feB2G>M$qT!Vq$d`$QX*RBcy|u&S-#IF(K60vNTY4{&v|fw@Ml4X=37$%L6<$OY-=ho7+YGxxD_WShW}VZF>01-ux3*4IIX`'
    'vEq|wW`+?KF$W6$Xo^9!LuB}T2oPLGGc+CKRY}w9qQ^PmF*33bPTIWtyi)d;F;xc~h*}QwA@Yy|NIxRgj?hWYz;a{QxcaMo`Rj~n'
    'snF+X<*D=DUtArjU6)5p7Yq&Kn_Y&xBa}}3q!w&9ZebyE?#>$90%ZBxBiJJycR}b9$*40_75I0PFE5GWWL19ny5gzTx#?wdX4L2*'
    'Qj5{hFh0+F3RnX*hV2l`J=Uggx<9|a@`Z0arG1cb0=NhZ=4C7@R<E0)D<e~>X1qYoEzKoc*zn9LE4Ui?kf$ZbbY;*vDFA}K%A%?;'
    '!+Qw7zm;Y0jT7rOo2RK1y;|2|!Joi?;AEK5Q^|;Qy27ec4|UcwU0ZZNzJ#sF%j28M-yeTwD`rUXWLm7_^v=uxo`Z`O$socsj%Cc6'
    'UagpqD?Tq4(a)ReQpTE^QCZ++8V$xGq<B2F_l!$}Tx6tl^knOP>%xzr<TavUMd_?*5KMtK`WjWZ4k1a(1boObQG>XM(5FjRSr*@y'
    'T{_{bf^YscP<uTC<R#IPLM_lb$%qQ3?gE-1|DIMk;onzX$S#}wV%Wps=+{$dm?&cAI-HoXR}m!HJ7^=YVdWiGZd^IairqT5x(a^;'
    'f7Id>qO4>xy-0_c{Dv>4Bh2+TP1~)DE<Bo7u?=-w$bnX$x$H}=CbMG!hI45S2lgDrHZ`ZBy5`!ThD=w9bg!E@(Pz|-YYN*UfIqh+'
    '?3I9pSX1X*`@V`^zCp+F^A(fjW$P|@tYZ0bMcvzI$>4agU2GzDhc%E7j9F|QVyJM5k)Vwm*M3zMO3BVI>moFAC?=QcS^D+CI|;1{'
    'iKB6RbQvjO*w}1bcE0<z;+SRbAxs;_E+9kq<Tw>eW$k}SZ%>6voC_=1xZG}BESS2lX9ML7P}jzfq1j2`5qd05l&B40*VFF8ZdMAo'
    '^>aElTpp$u<>L8_9-a;j17m9cs+jrxg<mrDwlUebGfE06cH3=T__vq)^WRVzwuUkLno2zlEdswug5E0f+Av_`MHcg0s*UR%hmhSq'
    '-$NkIK44v(E~KBKcgz_&RptS=A#Rcqr=Ylq8&ZII>$<P>+x1tQBH0BHz{pat^bt|Uz*<x=B4p6kS+$#SF<iXz#z^JJ>YQL5On!7B'
    '#R#L)T>INdBTQRzZmPz4)ermo`uqLYl|JUutaZV&qHjZg(-Tee)nHSL85W#hqdkhPQ6lE8uPCA%ns7)a$ae7&tMS=$1AxOt3Ms7W'
    '9Phf=y57s(VYkdFJzo|Yy%Zj_LCXsPFIcUO7Jkg%1jaLN)~?Ame^0N2Kj+T!+mxRGZJ}ujU+938V-yr7fmteC_IPu_AXLp@pN%{C'
    '!6A9m^2QlSZ+P(_{BlzbKiWX>fO&4eDNq<aF_RcJE`Rbx=B$2q__BfqgxG^8Ek{K<8C^+MN$OMaSs#w;eu>CVs<Lt6=K;L50xH4m'
    '-L)eU<`7<}JTHrY9h3(cSSr*An{|H4f}Zi}!Nog>4j1+!Lw#pQtIhDHF1-DPEs{Doo9nRMylyb5V0jw=YOrCbb(O=Q=sFOHa2giD'
    'I8=~9QDa-WueL_%@9srE7*U=7>C_NIRmUt3N7<K5s1F?no%+Uo>YOpc33lrpe8g;l<lpcdzpiBPf+4@M;AVjyVqTS;(!BCnkg=WM'
    'P4a)(noFPhF-v|mt;k-BFcg$~RN?riVWsvCJJ*GvNkk}$Dj27&CCjnNeg3z4rtCpyu0tjwsW}6uHilCQ;NeET0RSqi@uC%Pac0im'
    'hY(o4iX6;iI<JuxE(^<J%4SjdGt;Xy?#Rn7TlJXn?4I`<^t^@yQGff1SxBeqVDv;^pjAP+Od>OJHFx>u-_5%0xc>Rfhx?rpkV_fq'
    'rvtT|szty--=}fw6E{6`*cwJ&9v3L_<uM2?D;)vEY>$;aaX9fwa!My#t)TxAJrYRj9I<8VO>y+l+*UF;rRI9&Xk<%vIU++d+8Be*'
    '5^hDg!FQZ2+pXow(J(TMM4!41?%Jj!1&i2s9J2%#qPV-cirFL~!blfd=D3y_Pz65x`E-24pKkq?wfXG|X{HVCo^~_6VpT&Mn7Oj?'
    's$(QeluK$D>cRAqg<mICokotF|J2H`>gG%5roun>b0GoYbx_10iz3E@i{n{#(fTK+{%zLvVUp#^hxiVYOoy{JqbI1ZX-pTDmkspU'
    '>8e}bPdhjv5_jQc{>1tPTCn2L$@iuqF4GWUeTOHFNEM$%8l!tKg&}TzwaQKSX%Cwg_L#Nz`vBW$YxJB@wH)kdvFZ_V3<{g$d?+qn'
    'IR5PwY6xQuc&3a6i&2TpgcPK!Jw+P90w@TE=Hjf~A;<YKn?AL$&N1zG29!EVzBoc6GF0`>)Q0DFh5a1V^_3MLcaMZ9Yl)cBDKM8l'
    'rbZSqpkOKg4abm|^r(u_Mqal$dTVUuj~7(%MyL`rO^YtigPk#k$)k?BYFLI1zywXNHUR<!zHl-jC^&f8m`>0_EQ~M%8sf;tT!|np'
    'qki?Phvw+ru$+~J7;x-2t>}87lB~GZin30>-Z*-*AH*=+M<E(WFH)wfe#6gN)c4)@fs8k=Kl{7w-{zr-wB21;B*bX1BF5T6K{&}|'
    'CPKytf^sBh>DSq?TQ;<1s3HY3hgJeQ)jTy(9YY(`ebQohGJld7Pk=9zeP}z|K9b(BC^MOf(Qrtjxesxp-AhB3lG{|=G5M;_`ut9o'
    '@sE$)Ze<=}I+`@5(I16q7Lh=0fWtkR*=asbP|<L|R()emTY;}f?YqS{*Wf{O54b?{s5Ru#WkS%D1j5jVwhC=o94fnE+ro#ae2MK1'
    'rHH4nTAFD4_TdxUh3H>Px(U%giJr+UKFv0y4P(7|?L~rnyxOOyr)3m{X5pHJDI08rp&p@zy-JWfLN(1?O%?2c1D+*a)UX$9;z9~j'
    '3uI<L5c4J#XMuLJ=1QV+DFcGWcVpVQK5ya29sKqZnbnq`pG}6Q7NKAb=PS$y{661(Apc|NA){k%n!qKCU-0#50=K~`S~#Fl!XzPs'
    'b_By~4_2yM7yxc_!RnWNf@G+IkivnOh-qZbpAib>p(to#-1PudG%9HAmd8V%Z+{pVzkM(fRzA2k4<R^OnKvF2di0zU8ud1W9Ebv7'
    'z~RyjoKnn9vrvH%<{l5BeH&0hB>JY6HIW(M{<Qi~D)(%4FxGop*glWS0jR^KMiH$6B0<1ugYL?{`k10nEMrL0OSiFo7V8|Ud-2Bq'
    'rdABoAqX#sjJj)#?hLn|GI})E?ckNAbH3a$a|<m3<4)2^I%O1X;AH4+R1)lL^5_6}t7y%?Y++mXlR|*iN!CwToW`HJ00F-sXbVH2'
    'wI+k0oUTgA|9SPFDUOQ)%1Y`DH3^3vlSTo-h$32Ka{p)`g^mY)=T0n!4{c)u(-IddZ3or1Tv)T++ecd>*5(bE#t;n?iovx_`k{Sn'
    '9?fdJit4Kk?1}{fho>wI(%VR(HSySlsf*{lxp*@%q4jp#$gj8@__UdsOuN;9#zk$hlGUcxZJ{~}PcC=%#d|>Pd6+)0i!b4|o`0y>'
    'vM`=8yu>s$c|0;Kg9uvnya5cYk|5sPz;k%nt=$*8@R1@>U2251;fEabmMKhPSy!6u!u79C#!ExQ>vYXcQv@y3EFy^{%zCGVezMGL'
    'g1FJMRH6PHF8(TCx3GCyEhgKHY+r<yM%`GK%Qdd<2}|f0qpR;5^LDP>$M?aon;gz@fsI0%vlyeDg&R*F>7<+j2}qY2=PibSX5FQm'
    'Irj9W7XwbxZA`0rTImqhQWwPx<Qvco`_vm8LIRM)IOncIp_N!&yN?*|@UUc9E~?e>qk8Ri%r+d;B#h3~p^G(bRYi(B*Gu<(SnUtL'
    'vzKFrZAT9q6nHpUv#Lg65f1oXjmit>f+7*|5e>ta1QV#!>$b9mLC(Q&h#`pl?s?(4=2W3W7?`8JnAbbTbZxNWrJ)N#&)I9O6N0#f'
    'JFW|YMJ=IM&qb)zdU4U|o}(J6y~^RzsPVIC;dT@7(-Y2PsKE=dj0skBM|fP5|CMoGQOgBzs8@O6R<;>txgAW2p-06?)uW*tZzH!2'
    '+h6K^XJ@R+{L)-|zT18N;#+t*U8wh%p(}z0_=~TwjJB%L2QWm+w-ho|2P50W2n~%O3}2dMeGahiA*@g%`MsT=9M|2dnnRG(Y1U{4'
    'tJh4$U@@XtCJhwDvZzN!f4y`oqBvqh_we%QGg)fE{eE7V<ED?Gn<ULbK0+Qv)^;$sQ(=1~$R+xu`7mDkP|T=(c<U<psgH%~SBCW}'
    'RMMlzZP3$VD#!C2&aF)x{Pb)U<^AWSe`szjFXR$4=p?4eg@ivwnlNJ3$)of^-z`b__0+_59-IB8M;3wnGUhl|r-Ua-6+SUEBuChb'
    '@oDaSx<#xeVI$};<@NhmC5@TS;eU*IXW|5f&VuwhhmVU1W@?e(M52vde2>HyE>cY7;qwf6XYicHAOoJXo=#9gDR=t`xQkJyI=W&X'
    '7bqw!0+Hc17Pwe}%Z~7DMo}ViHW5pT#r-E4uGqy!ErZ^ZezH86%1{f!uwDO4nc7Cl%5=bVBHkYtS7}Fy-|b2Aw^pLzK()mCYE-D5'
    'a5@^c72Ibub1e#z$h4dg7%$z!Wh88cFwYgy!pU^AqP~$@CS7oZs~Aay0`B9u_(6yci<{7?MY=v^ks}`FHOvHpC=;gg2ryeQZ8$?@'
    'H(hwcU3@?;nKVB{D+<#wyp#k795iq;r6T6GLOCW57iD*G`g_`eGa4au)6i>;V&XKkbS+B!649J{mq{L!a$$2es@k+&vg<bTxL-oL'
    'n{79IU2&ZNV4&5;R~oW8Z$N<x>Bj0(G{wyMIY=<gbsJfD3R_-GBB|v2Fv-L@D8=lzo+hD*FEcnf6VyGXE?ycf9%B8#7K5=tKEMz8'
    'c?CVtSxjPTAl9P0%LX*k`HvV^k%n$JXny_0N9EL4y{w^4eT5*RSRJ6N(ZUU?J=V2-RWX_r<55PGR@d$2($+SkM38eDWW$6F0m+><'
    '2$|XxmKe@-6~5kC-CwtxBbR2=MsUKAl3Z%I;4qD10fCpfYIXQ%>rJJ>hrjq0Euzy?e!fwB3SCer#&pscuZ(HhS7mS^F~>VMFApwH'
    'r|K_F1s`|A{`*eW!)ka%O2e!Z1Y2S@`f3j-4c>1aQUzYF=DKy)?Be)dK2LiVI&0)mgN*TB7@Qcq!8Zw$E0kmiH^DELe}s~5eaOU{'
    '+c<?2?j148VfV0xxtOctZq<;I3Jsx_aNqcFjs77+LJuM4(8f!zdL*xB`2uo`UIot%I*K`oL1p5p;;Bf(<0ze{3<o`donM@{FWdQn'
    'M7tRx#d%XqDyro`nr7N~gZt2M370SJrTq<IJ9O1{ULDPq*q^t^rs|*|1a(_IS7HGenIfPl_oD)b5$SMi?R8h3p%cS*>vKtCB1)Gq'
    '(4&OV&U77vfW{C+DuR79Ve6aBmtM+$-9I52*oM=w5>(IHOV|g3Vu(;;LL}{VSZ3hX0dg^`F3lUgoqk%d?5OjMg<dTt;_3kiVZrd?'
    '!37z(k`X?kVk15CjzIe|R;MX0-^j>I^!vl`sy^=)r-4=Wj}ueIw1Or?==hV~8p167Do{dia0mrjU0u2%|K*H4FX@5-9wd?&_|b<%'
    '+KG)B2J3NP3=c6)lOc|HbLmF56Nh6YcBk(f)O%r$V=w+2TFqjWgm76(u&EI)jdF0hlgs>IntNv|z{)Nnj5x&ss1te+UI1yrW}`rA'
    'CC7~5Pdk3$F3wPUe=0NGG;Q3nWdQn`9d*<gt=4=VR@X#<;pQ@5dQhUibv$Ac<=SKhn(+~NNyM1Kd^9Fy@Vk$(Z!9;ZBxZ<X<~5fh'
    'ASagX?MeC??msJ~4brx6u?c@H2xSojM4Xj026Mvzm?%f9xV>;2Cl&weZdM68dI%}rT3H0&F!&hm6ov^hl#aSuqY$tSPtPyk1_#~H'
    'cgqitb=LW?Mc9V57qcW$U&EUngQkiB_RcK!5`4~~tu8&BM;`Lyv=SP6W7u{3!W1hpUrXG?1!n(L$1UewfbaBW$KtBhx3Qp`08CAY'
    '&Ey^7q{uR(77O&up_96x_SZ<^FMSV-ZQ0SHWDArX<eb@u$oYrwjG1*Z_BJ-9*2`k*C;EBNHr94=Sw!l?0@x&l$s6ust}<0H6=i`l'
    'qdGuhQ`+LItgZUpJLCH$b($}<GV-Vkwmnfl+o(=gNiR!FI>k>3Nf`0{5O;UKdG!r0aSk^|5DsN+&@yN*UOWknr;ij~vC)uN&C@D7'
    '=P$F6?a|L%%?i~aVWlrgsvR$xf2q-p(aMh|3qE!|t=jya!pwX3?oZwkCj5bIM$|iVUotl=0oV`|;x(1&SSizWpQ~ouikkx)8$?dn'
    'nqvAeypCKpBOg4YG89}c`yt4)!tUx1UC!{f956@cHln2|3Nvt9L}z-SWeSJy7x~O^xG-^RH?0^kYnzgQz#Xs5Ez-l%Wt)<|%1R7k'
    'V?-1-L#F*wu8NU=SawUKFaTx>zsD*D`KV8L1RIhXpEU%C<Q=01>al7y`NOI>$<c>ip+CD6yCBb}VJT^7o6m{vNsLHhE(~iWvwK!+'
    ')*n{gctg;nqy<l*E_||dn8^Z4a4=;(n{^`&pczK2tm4A|vhao(PPn@4WjM(WO-x#?u!m4GI!HmOP;R^d+I|4SdrKc{@tYqL_M5}n'
    'ym@)CEGR~FGOB<aWigW*jy1$Jz=vC$E_IdPy%E)v^Zw~RdWK{n-QBnUSkWJW3CxjK$R#4bZe<L%H|ZMHA&sE1IKNfzTiO1&-ib9C'
    '2*{d=KiAMuneg#%fZ06vL<PC8G(?ijTR7_NnJe1`%bxK5^|hlTX)fawM~9A3`z37qOS73dl+6>Y*)Duom#+N^Zg1EEoC8lB4Nn!M'
    '?-drQCTWIS0zvi^!i*^<RloaHt9lNxha2VLY%J~He|z3PocYD@PkdZVqZm#?(AS2~JP~8i&H!I@gfpJ#yE%?kenZN*S=yXXwzogy'
    'AMc)I4mA~am4Q|urDC}gOx`fC4#kSvEf0wFeNKMN0X<FEe!hv}n}0w2c{n#?C~F~RTD+qtNQ|K5mQGh;X2>6mu1Ms_-j}iofj6%|'
    '@@+xJPlgZ@HPe{Ax)`W1#=ss?sRYh&wG*RA4g!uy&aD=F>iD~x1#4gFO3{iVd9a&SFX&X7frz%Ja?mC$aou4IT;kuYo1W!WH~1XU'
    'TR0W2{^a)bC%4~C3(lu6WehMzX<>iKOT>6K90xNP<u1W>0Kwqn_-F5J;`{G?ioWdAdLX2(RuMFS^E3oLk`=yrg!_e|7Hak`%%}|5'
    'd+Q5|mg}d!`|3OW{vTI@ZaB&t9;*US4Ru7AB>Oc+6Bmp@<WED0+ZG$vIu6%7{O|q$n(mf(@ISl5mlX`w#fqOV;Z_I*7Td?E9J^&8'
    'UI66YcKvoidR$$TWcYG(VrLK|?jP6Xmn;bJL?~(_C}ao;LrlNo7cJhK#zBZk`T8dL^Q|>ce_dhJiS04a&g3S8<^$-aLNksrqP;1W'
    'G`7H)H}k?Dmpo?qpB4t)%JgkhQ*q{8a9Q{q5jS>{7F01>rSLZ)NWnQBx2-oyg3o`j`Eoi`ioDv;)3on-0@85Pd6JFs?N5UG@g^nh'
    'jrBgin4`GzJoC1Tt|+|Gbtw}hL&G}L{Ufnpav?V0&bHguV~}=O8#-FWs3eAeevr}TILn@IjOkE7$^^r@HU`2D?;govcXKp4c>eTd'
    'H#0Yf+a2e&J?>Yc0Vg<;RKALAW2uy3-r)x)B*EliikQlR60~B&(y`V$C&FlZGvOF_hd(H*4i1Yz8PZ(MtGo*Z6SLIvP5sorEcmnl'
    '$!o^gAub${kCX5%VWv!ti-t=K%N$nWh83HTwj|Sr6<;1#nfXe?9048Z*#^}`TTWarqP1@mJQUcHsid0jz17Ak47Smmze#YN{^xM('
    'T0N6RxPOsBNPWyi1*}x=PWK9`cNtQ13Se(Gy=YZq6Lu>#Qy;GEIuazKmUL?<!Sk@uh}led9VW?@X);~3?CJ$Jgp6O`3aNSu?n)84'
    '0#Xet0YGaV%($4^kzTUsu@*mnn@}4C>>qBvhC?{8I4mkgNE+d>#20T>pEG%HS-hc}<#^ou;|0ty?~VhSH@sZwJQ^mqZa{B%p@cIk'
    'z6Q06iZPrkL+3EO|CHZbc?(U1aDl6hh#=0g+`|oF{2~nupOjF%uwCX}m0kR+zpMo&c2#nRP;>Mlt*kV&rAkCMRQ_10g+E7==*vqN'
    '-Y~b;9gW+7IEY}2Qpi3c1j0zCdJ3NZnCNnA%)J|qHA7#f8w42H%VOX7c<9#T3MIm`FUXzhS0ia<;UM7C_Q2iXB^R_LypP*WYp&mM'
    '+6Cy;Md#PB2MhOP#bL~#R8p7%XO_JSNG`l-xh+>5$Q2*c1Q*lRXLh>cm9s?upl<>R==F(eu0qYm1rKYPCu$#cERTO`oN)Cw3)Qpa'
    'xE80_)6_={F!tS~=!7vGbL<T{k-fWBTrlqNIc&(8n*ceK`QpEi1wTZkQEXc7(e<quTp6yAEqXsREi!qddc)x&@%QFNF#?b9n}%_2'
    'vuVY*+yQ=y^X9xXegPV`@qj>lMEo>hz#_Pmp+uYmQ|>n{b{qw?LV_ZdYGYV4)8`740-6oOSKDGv(3BD4;;2>co`zFgfBoy0xqd;K'
    'rm+YtwGGa!OI(M7^#YVtQ5JZwy>!j{OUi$C5l?TH&*k~mJY>ZxCT*g%?agUR_)I)RKivPrKp2Z8jAMMd^~I~MkHeT_9$(PKNjT9C'
    'B%Y>n_ks3;<HCSBnzu<kT)woX{<xp#H5t7i%L`YgApMJWm_C0O)b>Uzxg+Nb<Nk5`>STg{JO}0Q@nwYrYRH&Ki`d6oy5M&;stUbc'
    '#6JmIpbr3#{DR-T9v%q8V-f+?CNC|8aQt2Zdf~z70Nh3|SrXA)vZi(Zv0?>-gJx=`QX&WxMF>QL;>ouFh+{0Xytft^vr88}$;MX('
    'H(^0QlZiE=T9PpI(GQ}?3-S{SRd<YJrfs(`9vQ>NF=ATIl3#99W&HS5QzQm?5$WbU^F}f+!zr~*rtOQv9(9He-BH-}=SqSq8EY11'
    'cU<F(2h{`vC0AD!2+fNgwdpVT?GKOlvGTLosVlSW82)rgjBX1eo?%_VLhHjO(Y=5M=j{U@WKi4JKHWw~Y2Av@kWGvaojRSpCmWNX'
    'bs0no!}9P%6KDZ-+0buaJpTOld&0h3<Ia|W1xTgPU>xrtVV3L}I8$a(@Yxo5U0Po7-ou}Az7tqpgWJu*()@G^aj$>+=_t<qbV?U?'
    'C$Z{oTbs>*Ki&BWxeLuHi}c<B6$W!eTi$RJw*zmqtpEGB{a3?z<JK!^GmR@W561%ks1GO+Mx*0_ugtAO$>b8tH*Edrg85D`{mDjN'
    '#;Bj0LcHVk@?bLYgtmj^JoLRW@QUwMv*i;Hl@Xoh(s9^OhfU$M?fj@PVHRd{c3Lf+!hm?zITPJ8$85{F-VC<sSGbE3V{|26VRo&Y'
    'h;eK(vG5CIJw1iR?YludW^hghFq{vVe0iz;ijZvcJOUVmU<g6A#!*3N8-mIUOnkS(Jh}<p^g#^ip0@lhUZpyXkV<%e7xZ?yW%S1C'
    'nD7jF3NpS9%Degb^V8@4cI{_XF(f@$A4bz~#TNx6=!vF{ThaZa#mvBA%HKU$A-K9Zg6k7=+)v|fUWO+gb}JoDiK{LX7c?55aF~?P'
    'gfSR9)qoHTca`9Qp|h<EuO@Rt3~vaZ@Nh{%qpg+gT19ZfuxIge6<6VoyLG{zYUcBG$Pi<v8$YdOR*w52lbmAo(h#z|I))(mREKKo'
    '%B%2?@W}d%5mFkEy51&cm0KkYpZQv{@&wza)BBhEvev8R%%^T?o~*c(;%%v|3}_23eHM}o+42<Vu&AR&MX|wu>HUxO=Ox9~*Y4tZ'
    'n4KsdQ7XD$Or~hGV)`Si4Hh&({ZJQ06RzI2=ywJ3`BO>KnZy)xcsFO6AYq4TC9EG9&Vwv8m3*GMZEJ3TS_WBu6JCwnL#nVSq+4Z<'
    'ii8~wY&w3Rcq-d@+k$~W-$%4NpB;unG{sf0yt!6EBACxgRq<6hzNx6A^Jf~)#x)ln@s`G$-k|x`J{~4+v<Pj8>b0SKJ%Ap2VtR|m'
    'G?$mHyD~Vz0g3rdzTk<19pJ%{q@gCK5uv7$nz!os>arzqly~Q!aEzZ*U+|4XoFCyH#)7Fubc_>_@Q7=V=8<2z>}yuDG8cqK%2U?S'
    'fTAJM<Foi*Y7Mf}A&pX(dE?ffyb6qveVbFn{wj}NMyM%acysvaYQU8-4-Ew^?KiKsN*DqV(6FYV>xD!+BGn*!6cX`0g8vo6Zp;lX'
    'E?V)e$vr<q?(D^5P>=Ttb<J`5lHhKdE^1UVs$JYZ_4|<f&x<}wKl}ap8I=lCLj#+jm&FIXv=MNtgW8M|7WYgRfq%Ye#oJZXnPA9h'
    'B;_&q!FVVw9O0K!iZqvn4k!;S+rB-da%I^~Y*pnUSerkJbj)|F(^_|t!B7pEMinEc6|lwo9qYH3Uo;mhEHw27h!2qH%tnt|$sA6j'
    'TIPaP9YM;UR+p`NR5YAVlmL1>-O>Qp4N2l8fON;uFO}v--?xnCk>wjNxnmlN!+Fvpt$9Z2$Jb$U8IHMT>J&j#n$4F6icPrN7!q&m'
    '_1{=}HTuWo4T4{IFqd(avBruH3K>lonTwRSUbKY&@<IRC|M)-d1R$~'
)
)
)
)
)
)


class ShippingPolicyTests(unittest.TestCase):
    def trusted_main_projection(self, root, raw, source):
        """Authenticate fixture fields; never call this native D evidence."""
        payload=zlib.decompress(base64.b85decode(_MAIN_PROJECTION_B85))
        self.assertEqual(hashlib.sha256(payload).hexdigest(),_MAIN_PROJECTION_SHA256)
        tree=json.loads(payload)
        self.assertEqual(len(tree),502)
        self.assertEqual(tree[inputs.AFFECTED_POLICY],blob(raw))
        policy=json.loads(raw)
        self.assertEqual(inputs.affected_lookup_digest(tree),policy['targets']['main']['lookup_digest'])
        self.assertEqual(tree['tests/platform-profile.json'],policy['targets']['main']['profile'])
        self.assertTrue(inputs.AFFECTED_AUTHORITY <= tree.keys())
        for subjects in inputs._AFFECTED_SUBJECTS.values():self.assertTrue(set(subjects) <= tree.keys())
        # Installed workflow authority changes only through a complete enrolled
        # tuple, exactly as shipping_context overlays the reviewed templates.
        generations=json.loads((root/'.github/package-workflow-generations.json').read_bytes())['generations']
        accepted={'npm-consumers-sync-ci-v1','npm-consumers-sync-ci-budget-v1','npm-consumers-sync-ci-budget-cleanup-v1','android-owned-npm5-sync-ci-v1',
                  'protected-producer-original-default-v1'}
        matches=[row['workflows'] for row in generations if row['name'] in accepted
                 and all(source.get(path)==entry for path,entry in row['workflows'].items())]
        self.assertEqual(len(matches),1)
        for path,entry in matches[0].items():
            if path in inputs.AFFECTED_AUTHORITY:tree[path]=dict(entry)
        return tree

    def target_context(self, root, raw, source):
        policy=json.loads(raw)
        lookup=inputs.affected_lookup_digest(source)
        matches=[name for name,row in policy['targets'].items()
                 if row['lookup_digest']==lookup and row['profile']==source['tests/platform-profile.json']]
        self.assertTrue(matches,'actual source namespace must match an unchanged protected target row')
        target='main' if 'main' in matches else matches[0]
        # Equal namespace aliases (Android main/VR) must also share the complete
        # native reader proof, rather than choosing among incompatible variants.
        self.assertTrue(all(policy['targets'][name]==policy['targets'][target] for name in matches))
        return target,self.trusted_main_projection(root,raw,source)

    def test_shipping_manifest_is_complete_and_backward_compatible_registry_is_unchanged(self):
        root=Path(__file__).resolve().parents[2]
        registry=inputs.load_registry(root/'.github/test-suites.json')
        raw=inputs.load_dependencies(root/inputs.AFFECTED_POLICY,registry)
        manifest=json.loads(raw)
        self.assertEqual(len(manifest['suites']),60)
        finite=[n for n,r in manifest['suites'].items() if r['kind']=='reviewed-patterns']
        self.assertEqual(finite,['documentation-contracts','release-bundle','embedded-web-qml',
            'places-native-qml','recorded-voice-qml','snapshot-qml'])
        self.assertEqual(registry['schema'],1)

    def source_context(self):
        root=Path(__file__).resolve().parents[2]
        registry=inputs.load_registry(root/'.github/test-suites.json')
        raw=inputs.load_dependencies(root/inputs.AFFECTED_POLICY,registry)
        tree=inputs.full_tree(root,'HEAD')
        for path in ('tools/test-evidence/affected-test.py','tools/test-evidence/AFFECTED_SELECTION.md'):
            tree[path]=blob((root/path).read_bytes())
        tree[inputs.AFFECTED_POLICY]=blob(raw)
        # Both the source PR and its exact installed successor run this test.
        # Authenticate the actual complete deployed tuple before constructing
        # the distinct approved preinstallation B; do not bind R to B instead S.
        generations=json.loads((root/'.github/package-workflow-generations.json').read_bytes())['generations']
        previous_rows=[row['workflows'] for row in generations if row['name'] in {
            'npm-consumers-sync-ci-v1','npm-consumers-sync-ci-budget-v1','npm-consumers-sync-ci-budget-cleanup-v1','android-owned-npm5-sync-ci-v1'}]
        previous=next(row['workflows'] for row in generations if row['name']=='npm-consumers-sync-ci-v1')
        future=next((row['workflows'] for row in generations
            if row['name']=='protected-producer-original-default-v1'),None)
        if future is None:
            future=next(row['workflows'] for row in generations if row['name']=='protected-producer-seven-target-ci-v1')
        endpoint='.github/workflows/pr-metadata-context.yml'
        approved=[future] if endpoint in tree else previous_rows
        matches=[row for row in approved if row is not None and all(tree.get(path)==entry for path,entry in row.items())]
        self.assertEqual(len(matches),1,'source must match one complete reviewed current or installed tuple')
        if endpoint not in tree:previous=matches[0]
        enrolled22=any(row['name']=='protected-producer-original-default-v1' for row in generations)
        codeql=blob((root/'tools/repository-checks/workflows/metadata-edits/codeql-metadata.yml').read_bytes())['sha'] \
            if endpoint in tree and enrolled22 else '3a273057a38255ca368d3028594fb94227ba7c3b' if endpoint in tree \
            else '6d55d0fe4e9edc86204c66e1fa3967681793a2cd'
        self.assertEqual(tree['.github/workflows/codeql.yml']['sha'],codeql)
        tree.update(deepcopy(previous));tree.pop(endpoint,None)
        tree['.github/workflows/codeql.yml']=dict(mode='100644',type='blob',
            sha='6d55d0fe4e9edc86204c66e1fa3967681793a2cd')
        return root,registry,raw,tree

    def shipping_context(self):
        """Use the actual complete prospective installed S, not source-only B.

        The native inventory includes the new reusable workflow's membership.
        Its protected certificate must already name S; this fixture never
        rewrites that certificate to make the shipping positive pass.
        """
        root,registry,raw,tree=self.source_context()
        generations=json.loads((root/'.github/package-workflow-generations.json').read_bytes())['generations']
        historical=next(row['workflows'] for row in generations if row['name']=='protected-producer-seven-target-ci-v1')
        self.assertEqual(historical['.github/workflows/repository-checks.yml']['sha'],
            'd9fefd275d9e3c6977cf9350a1945a6bbe5051b4')
        future=next((row['workflows'] for row in generations
            if row['name']=='protected-producer-original-default-v1'),None)
        templates={
            '.github/workflows/project-tests.yml':'tools/repository-checks/workflows/producers/protected-project-tests-android-platform.yml',
            '.github/workflows/parent-qualification.yml':'tools/repository-checks/workflows/producers/parent-qualification-android-platform.yml',
            '.github/workflows/repository-checks.yml':'tools/repository-checks/workflows/producers/repository-checks.yml',
            '.github/workflows/pr-metadata-context.yml':'tools/repository-checks/workflows/metadata-edits/pr-metadata-context.yml',
            '.github/workflows/sync-validation.yml':'tools/repository-checks/workflows/sync-ci-selection.yml',
            '.github/workflows/browser-client.yml':'.github/workflows/browser-client.yml',
        }
        self.assertEqual(set(historical),set(templates))
        if future is not None:self.assertEqual(set(future),set(templates))
        for path,template in templates.items():
            expected=blob((root/template).read_bytes())
            if future is not None:self.assertEqual(future[path],expected,path)
            tree[path]=dict(expected)
        tree['.github/workflows/codeql.yml']=blob(
            (root/'tools/repository-checks/workflows/metadata-edits/codeql-metadata.yml').read_bytes())
        if future is not None and tree['tests/platform-profile.json']!=inputs._AFFECTED_SHARED_PROFILE:
            # Source13 keeps all original owners. Only the installed Android S
            # fixture applies the separately reviewed exact seven-file handoff.
            owner=json.loads((root/'.github/android-owner-transfer.json').read_bytes())
            targets={path for group in ('legacy_workflows','source_contracts') for path in owner[group]}
            self.assertEqual(targets,{'.github/workflows/android-tests.yml','.github/workflows/android-vr-tests.yml',
                'android/common/tests/android-workflow-contract-test.py',
                'android/common/tests/ci/validate_ci_contract.py','android/common/tests/ci/test_ci_contract.py',
                'android/common/tests/robolectric/build.gradle',
                'android/phone/tests/phone-release-metadata-test.py'})
            for group in ('legacy_workflows','source_contracts'):
                for path,item in owner[group].items():
                    self.assertEqual(item['source'],'tools/repository-checks/workflows/android-owned/handoff/'+path)
                    data=(root/item['source']).read_bytes()
                    self.assertEqual(tree[item['source']],blob(data))
                    expected=blob(data,mode=item['mode'])
                    previous={'mode':item['mode'],'type':'blob','sha':item['reviewed_blob']}
                    self.assertIn(tree.get(path),(previous,expected))
                    tree[path]=expected
        return root,registry,raw,tree

    def bounded_context(self):
        """Seal a small synthetic repository while preserving real definitions.

        Real whole-inventory shipping/legacy routing and protected iOS proofs
        remain separate. Repeated mutation cases need every actual authority,
        required subject, CI exception and currently reviewed import root, not
        thousands of unrelated application assets in every negative plan.
        """
        root,registry,raw,source=self.shipping_context()
        policy=json.loads(raw)
        required=set(inputs.AFFECTED_AUTHORITY)
        required.update(policy['suites']['device-control-plane-full']['native_independent_paths'])
        # These existing importable mutation subjects must remain edits, rather
        # than becoming new import names in the smaller synthetic inventory.
        required.update({'tests/device/self_tests/test_voice_roundtrip.py',
                         'provenance/artifact_identity.py'})
        for suite in registry['suites'].values():
            required.update(suite['closure']['required'])
            imports=suite.get('python_imports')
            if imports and inputs.python_import_digest(source,imports['roots'])==imports['reviewed']:
                required.update(entry['path'] for entry in inputs.selected_entries(
                    source,inputs._import_patterns(imports['roots'])))
        tree={path:dict(entry) for path,entry in source.items() if path in required}
        # This deliberately synthetic fixture exercises main's bounded parser.
        # Full source/shipping contexts above retain real Android13/19 profiles.
        self.assertEqual(inputs._AFFECTED_SHARED_PROFILE['sha'],'d63537504c20204de9d35d9be61da72a56df59c3')
        tree['tests/platform-profile.json']=dict(inputs._AFFECTED_SHARED_PROFILE)
        policy['lookup_digest']=inputs.affected_lookup_digest(tree)
        native=policy['suites']['device-control-plane-full']
        native['reviewed_reader_digest']=inputs.device_reader_digest(tree,native['native_independent_paths'])
        if policy['schema']==2:
            # Keep the versioned main aliases coherent in this smaller fixture;
            # shipping/all-seven source certificates above remain unmodified.
            policy['targets']['main']['lookup_digest']=policy['lookup_digest']
            policy['targets']['main']['reader_digest']=native['reviewed_reader_digest']
        sealed=(json.dumps(policy,indent=2)+'\n').encode()
        tree[inputs.AFFECTED_POLICY]=blob(sealed)
        return root,registry,sealed,tree

    def test_shipping_five_controller_case_omits_device_without_running_any_suite(self):
        root,registry,raw,base=self.shipping_context()
        _,_,_,source=self.source_context()
        self.assertEqual(inputs.affected_lookup_digest(source),inputs.affected_lookup_digest(base))
        self.assertNotIn('.github/workflows/pr-metadata-context.yml',source)
        self.assertIn('.github/workflows/pr-metadata-context.yml',base)
        candidate=deepcopy(base)
        for name in ('attested.py','postmerge.py','producer_workflow.py','sandbox.py','sandbox_host.py'):
            candidate['tools/test-evidence/'+name]=blob(('changed '+name).encode())
        target,trusted=self.target_context(root,raw,base)
        native=json.loads(raw)['suites']['device-control-plane-full']
        self.assertEqual(inputs.device_reader_digest(base,native['native_independent_paths']),
                         json.loads(raw)['targets'][target]['reader_digest'])
        plan=inputs.plan_affected(registry,raw,base,candidate,trusted,target=target)
        self.assertIn('device-control-plane-full',plan['omitted'])
        self.assertLess(len(plan['required']),60)
        self.assertIn('attested-runtime',plan['required'])
        self.assertIn('test-evidence',plan['required'])
        self.assertEqual(plan['required_setup'],['host-full'])
        spec=importlib.util.spec_from_file_location('affected_host_policy',root/'tools/repository-checks/host_selection.py')
        host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
        selected=host.select(candidate,plan['paths'],True,trusted_tree=trusted,base_tree=base,target=target)
        self.assertEqual(selected['reason'],'protected-affected-dependencies')
        self.assertEqual(selected['suites'],plan['required'])
        self.assertTrue(selected['full_host'])
        self.assertEqual(selected['include_platform'],base['tests/platform-profile.json']!=inputs._AFFECTED_SHARED_PROFILE)
        self.assertFalse(selected['affected']['reusable'])

    def test_preinstallation_source_cannot_inherit_the_prospective_native_omissions(self):
        root,registry,raw,base=self.source_context()
        self.assertNotIn('.github/workflows/pr-metadata-context.yml',base)
        candidate=deepcopy(base)
        candidate['tools/test-evidence/sandbox_host.py']=blob(b'changed preinstallation controller')
        target,trusted=self.target_context(root,raw,base)
        plan=inputs.plan_affected(registry,raw,base,candidate,trusted,target=target)
        owners={'device-control-plane-full',*inputs._AFFECTED_PRODUCT_SUITES,*inputs._AFFECTED_SUBJECTS}
        self.assertEqual(len(owners),23)
        self.assertTrue(owners.issubset(plan['required']))
        self.assertFalse(owners.intersection(plan['omitted']))
        for name in owners:
            self.assertEqual(plan['reasons'][name],
                'fixed-subject-or-reader-not-reviewed' if name in inputs._AFFECTED_SUBJECTS
                else 'product-component-or-reader-not-reviewed')
        if target.startswith('android-'):
            original=inputs.full_tree(root,'HEAD')
            owner=json.loads((root/'.github/android-owner-transfer.json').read_bytes())
            for group in ('legacy_workflows','source_contracts'):
                for path in owner[group]:
                    self.assertEqual(base[path],original[path],'preinstallation fixture must retain every actual legacy owner')

    def test_actual_child_namespace_cannot_be_claimed_as_main_or_trusted_default(self):
        root,registry,raw,base=self.shipping_context()
        target,trusted=self.target_context(root,raw,base)
        candidate=deepcopy(base);candidate['tools/test-evidence/sandbox_host.py']=blob(b'changed CI')
        # A real child keeps its extra import membership and native readers.
        # On main, a synthetic neighboring import proves the same refusal.
        foreign=deepcopy(base)
        if target=='main':foreign['ios/fixture_namespace.py']=blob(b'new child import')
        self.assertNotEqual(inputs.affected_lookup_digest(foreign),json.loads(raw)['targets']['main']['lookup_digest'])
        for old,new,default,claimed in ((foreign,candidate,trusted,'main'),
                                        (base,candidate,foreign,target),
                                        (base,candidate,trusted,'unknown-child')):
            with self.subTest(claimed=claimed),self.assertRaises(inputs.InputError):
                inputs.plan_affected(registry,raw,old,new,default,target=claimed)

    def test_exact_metadata_and_source_reader_bytes_are_independent_but_membership_and_modes_are_bound(self):
        _,registry,raw,base=self.bounded_context()
        paths={
            'tools/repository-checks/metadata_context.py',
            'tools/repository-checks/workflows/metadata-edits/pr-metadata-context.yml',
            'tools/repository-checks/workflows/metadata-edits/codeql-metadata.yml',
            '.github/workflows/pr-metadata-context.yml',
            'tools/repository-checks/workflows/producers/legacy/repository-checks-protected-ci-v1.yml',
            'tools/repository-checks/workflows/producers/legacy/parent-qualification-postmerge-v1.yml',
            'tools/repository-checks/workflows/producers/legacy/protected-project-tests-ci37-v1.yml',
            '.github/workflows/documentation-push-owner.yml',
            '.github/workflows/documentation-checks.yml',
            '.github/workflows/workflow-security.yml',
            'tools/test-evidence/source_admission.py',
            'tools/test-evidence/source-admission-test.py',
            'tools/repository-checks/workflows/producers/legacy/parent-qualification-metadata-v1.yml',
            'tools/repository-checks/workflows/producers/legacy/protected-project-tests-metadata-v1.yml',
            'tools/repository-checks/workflows/producers/legacy/repository-checks-metadata-v1.yml',
            'tools/repository-checks/workflows/producers/protected-project-tests-android-platform.yml',
            'tools/repository-checks/workflows/producers/parent-qualification-android-platform.yml',
        }
        self.assertTrue(paths <= set(json.loads(raw)['suites']['device-control-plane-full']['native_independent_paths']))
        candidate=deepcopy(base)
        for path in paths:
            self.assertEqual(base[path]['mode'],'100644')
            candidate[path]=blob(('changed reviewed bytes '+path).encode())
        plan=inputs.plan_affected(registry,raw,base,candidate,base)
        owners={'device-control-plane-full',*inputs._AFFECTED_PRODUCT_SUITES,*inputs._AFFECTED_SUBJECTS}
        self.assertTrue(owners <= set(plan['omitted']))
        for path in paths:
            for mode,kind in (('100755','blob'),('120000','blob'),('160000','commit')):
                changed=deepcopy(candidate);changed[path]={'mode':mode,'type':kind,'sha':'f'*40}
                with self.subTest(path=path,mode=mode):
                    try: result=inputs.plan_affected(registry,raw,base,changed,base)
                    except inputs.InputError: continue
                    self.assertTrue(owners <= set(result['required']))
        candidate['.github/workflows/pr-metadata-context-extra.yml']=blob(b'unreviewed neighbor')
        self.assertTrue(owners <= set(inputs.plan_affected(registry,raw,base,candidate,base)['required']))

    def test_unavailable_graph_retains_the_independently_selected_legacy_gate(self):
        root,registry,raw,base=self.shipping_context()
        spec=importlib.util.spec_from_file_location('affected_host_rollout',root/'tools/repository-checks/host_selection.py')
        host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
        candidate=deepcopy(base);candidate['tools/test-evidence/sandbox_host.py']=blob(b'new')
        paths=['tools/test-evidence/sandbox_host.py']
        without=deepcopy(base);del without[inputs.AFFECTED_POLICY]
        for old,trusted,claimed in ((without,without,paths),(None,base,paths),(base,base,paths+['README.md'])):
            with self.subTest(old_missing=old is None,claimed=claimed):
                selected=host.select(candidate,claimed,True,trusted_tree=trusted,base_tree=old)
                legacy=host._select_legacy(candidate,claimed,True,trusted_tree=trusted,base_tree=old)
                self.assertEqual(selected,legacy)

    def test_changed_graph_cannot_expand_an_independently_reviewed_ci37_plan(self):
        root,registry,raw,base=self.shipping_context()
        spec=importlib.util.spec_from_file_location('affected_graph_preserves_legacy',root/'tools/repository-checks/host_selection.py')
        host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
        candidate=deepcopy(base);candidate[inputs.AFFECTED_POLICY]=blob(b'changed policy bytes')
        options={'base_tree':base,'trusted_tree':base}
        with patch.object(host,'REVIEWED_PROGRAMS',host.program_digest(base)):
            legacy=host._select_legacy(candidate,[inputs.AFFECTED_POLICY],True,**options)
            self.assertEqual(len(legacy['suites']),37)
            self.assertFalse(legacy['full_host'])
            self.assertEqual(host.select(candidate,[inputs.AFFECTED_POLICY],True,**options),legacy)
        with self.assertRaises(inputs.InputError):
            inputs.plan_affected(registry,raw,base,candidate,base)

    def test_each_device_component_reader_data_discovery_native_and_variant_keeps_device(self):
        _,registry,raw,base=self.bounded_context()
        paths=('tests/device/catalog.json','tests/device/self_tests/test_voice_roundtrip.py',
            'tests/device/fixture/new-resource.json','provenance/artifact_identity.py',
            'tools/sbom/verify-artifact-identity.py','libraries/audio-client/src/AudioClient.cpp',
            'libraries/shared/src/new-header.h','interface/resources/qml/new-component.qml',
            'scripts/system/settings/qml/new-data.json','android/phone/new-native-input.cpp')
        for path in paths:
            candidate=deepcopy(base);candidate[path]=blob(b'changed component')
            with self.subTest(path=path):
                plan=inputs.plan_affected(registry,raw,base,candidate,base)
                self.assertIn('device-control-plane-full',plan['required'])
        historical=deepcopy(base);historical['libraries/audio-client/src/AudioClient.cpp']=blob(b'child reader')
        candidate=deepcopy(historical);candidate['tools/test-evidence/sandbox_host.py']=blob(b'unrelated')
        self.assertIn('device-control-plane-full',inputs.plan_affected(registry,raw,historical,candidate,base)['required'])

    def test_optional_ios_adapter_and_historical_native_root_headers_remain_bound(self):
        _,registry,raw,base=self.bounded_context()
        for path in ('ios/audio/IOSAudioAdapter.cpp','ios/audio/IOSAudioAdapter.h',
                     'ios/audio/new-private-header.h','cassert','QtCore/QCoreApplication'):
            for shape in ('candidate-only','historical-both'):
                old=deepcopy(base);candidate=deepcopy(base)
                if shape=='historical-both':old[path]=blob(b'historical native lookup')
                candidate[path]=old[path] if shape=='historical-both' else blob(b'changed native lookup')
                candidate['tools/test-evidence/sandbox_host.py']=blob(b'unrelated admitted CI')
                with self.subTest(path=path,shape=shape):
                    plan=inputs.plan_affected(registry,raw,old,candidate,base)
                    self.assertIn('device-control-plane-full',plan['required'])

    def test_native_independence_is_closed_bounded_and_cannot_exempt_unowned_headers(self):
        root,registry,raw,base=self.bounded_context()
        for paths in ([],['*'],['../cassert'],[inputs.AFFECTED_POLICY]*2,[f'leaf-{n}' for n in range(1001)]):
            value=json.loads(raw)
            value['suites']['device-control-plane-full']['native_independent_paths']=paths
            with self.subTest(paths=paths[:2]),self.assertRaises(inputs.InputError):
                inputs._validate_dependencies(value,registry)
        value=json.loads(raw)
        value['suites']['device-control-plane-full']['native_independent_paths'].append('cassert')
        forged=json.dumps(value).encode()
        for tree in (base,):tree[inputs.AFFECTED_POLICY]=blob(forged)
        candidate=deepcopy(base);candidate['tools/test-evidence/sandbox_host.py']=blob(b'changed')
        spec=importlib.util.spec_from_file_location('affected_native_policy_guard',root/'tools/repository-checks/host_selection.py')
        host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
        with patch.object(inputs,'load_dependencies',return_value=forged):
            selected=host.select(candidate,['tools/test-evidence/sandbox_host.py'],True,base_tree=base,trusted_tree=base)
        legacy=host._select_legacy(candidate,['tools/test-evidence/sandbox_host.py'],True,base_tree=base,trusted_tree=base)
        self.assertEqual(selected,legacy)

    def test_reviewed_product_owners_share_only_the_fixed_complete_lookup_proof(self):
        _,registry,raw,base=self.bounded_context()
        candidate=deepcopy(base);candidate['tools/test-evidence/sandbox_host.py']=blob(b'changed CI')
        plan=inputs.plan_affected(registry,raw,base,candidate,base)
        self.assertTrue(inputs._AFFECTED_PRODUCT_SUITES.issubset(plan['omitted']))
        self.assertIn('host-selection',plan['required'])
        for name in sorted(inputs._AFFECTED_PRODUCT_SUITES):
            subject=registry['suites'][name]['closure']['required'][0]
            changed=deepcopy(candidate);changed[subject]=blob(b'changed reviewed owner')
            with self.subTest(owner=name,subject=subject):
                if subject in inputs.AFFECTED_AUTHORITY:
                    with self.assertRaises(inputs.InputError):
                        inputs.plan_affected(registry,raw,base,changed,base)
                else:
                    self.assertIn(name,inputs.plan_affected(registry,raw,base,changed,base)['required'])
        value=json.loads(raw)
        for shape in ('unknown-owner','candidate-scope','missing-fixed-inventory','extra-inventory'):
            changed=deepcopy(value);changed_registry=deepcopy(registry)
            if shape=='unknown-owner':changed['suites']['producer-api']['kind']='reviewed-product-inventory'
            elif shape=='candidate-scope':
                changed_registry['suites']['device-jenkins']['scope']='candidate'
                changed['registry_digest']=inputs._suite_definition_digest(changed_registry)
                changed['suites']['device-jenkins']['definition_digest']=inputs._suite_definition_digest(changed_registry['suites']['device-jenkins'])
            elif shape=='missing-fixed-inventory':changed['suites']['device-control-plane-full']={
                'kind':'repository','setup':['host-full'],'definition_digest':changed['suites']['device-control-plane-full']['definition_digest']}
            elif shape=='extra-inventory':changed['suites']['device-jenkins']['native_independent_paths']=['ignored']
            with self.subTest(shape=shape),self.assertRaises(inputs.InputError):
                inputs._validate_dependencies(changed,changed_registry)

    def test_javascript_and_performance_component_data_cannot_use_ci_byte_exemptions(self):
        _,_,raw,base=self.bounded_context()
        paths=json.loads(raw)['suites']['device-control-plane-full']['native_independent_paths']
        for path in ('tests/javascript/README.md','tests/performance/README.md',
                     'tests/safe-landing/README.md','tests/mocha/README.md','server-console/README.md',
                     'unpublishedScripts/README.md','tools/jsdoc/README.md'):
            old=deepcopy(base);old[path]=blob(b'old fixture contract')
            new=deepcopy(old);new[path]=blob(b'changed fixture contract')
            with self.subTest(path=path):
                self.assertNotEqual(inputs.device_reader_digest(old,[*paths,path]),
                                    inputs.device_reader_digest(new,[*paths,path]))

    def test_fixed_ci_subjects_bind_all_three_trees_without_coupling_product_owners(self):
        _,registry,raw,base=self.bounded_context()
        candidate=deepcopy(base);candidate['tools/test-evidence/sandbox_host.py']=blob(b'changed CI')
        plan=inputs.plan_affected(registry,raw,base,candidate,base)
        self.assertTrue(set(inputs._AFFECTED_SUBJECTS).issubset(plan['omitted']))
        self.assertIn('documentation-contracts',plan['required'])
        self.assertEqual(plan['reasons']['documentation-contracts'],'unreviewed-import-or-missing-required-input')
        # Apple retains two additional audio Python readers and a changed mute
        # caller. Their genuine import variant must keep this extra owner.
        if 'recorded-voice-qml' in plan['required']:
            self.assertEqual(plan['reasons']['recorded-voice-qml'],'unreviewed-import-or-missing-required-input')
            self.assertEqual(len(plan['required']),33)
        else:
            self.assertIn('recorded-voice-qml',plan['omitted'])
            self.assertEqual(plan['reasons']['recorded-voice-qml'],'unchanged-reviewed-dependencies')
            self.assertEqual(len(plan['required']),32)
        for name,subjects in inputs._AFFECTED_SUBJECTS.items():
            for subject in subjects:
                for shape in ('changed','removed','historical','executable'):
                    old=deepcopy(base);new=deepcopy(candidate)
                    if shape=='removed':new.pop(subject)
                    elif shape=='executable':new[subject]=dict(new[subject],
                        mode='100644' if new[subject]['mode']=='100755' else '100755')
                    else:
                        new[subject]=blob(b'changed exact subject')
                        if shape=='historical':old[subject]=deepcopy(new[subject])
                    with self.subTest(owner=name,subject=subject,shape=shape):
                        lookup_change = subject=='tools/test-evidence/producer.py' and shape in {'removed','executable'}
                        if subject in inputs.AFFECTED_AUTHORITY or lookup_change:
                            with self.assertRaises(inputs.InputError):
                                inputs.plan_affected(registry,raw,old,new,base)
                        else:
                            selected=inputs.plan_affected(registry,raw,old,new,base)
                            self.assertIn(name,selected['required'])
        # This CI unit-test leaf is independent of the actual product tests.
        changed=deepcopy(candidate);changed['tests/unittest-runner-test.py']=blob(b'changed CI regression')
        selected=inputs.plan_affected(registry,raw,base,changed,base)
        self.assertIn('python-test-runner',selected['required'])
        self.assertIn('device-control-plane-full',selected['omitted'])
        self.assertTrue(inputs._AFFECTED_PRODUCT_SUITES.issubset(selected['omitted']))

    def test_fixed_ci_subject_policy_cannot_supply_unknown_owners_or_subject_maps(self):
        _,registry,raw,base=self.bounded_context()
        value=json.loads(raw)
        for shape in ('unknown-owner','candidate-scope','alternate-subjects','extra-map','missing-native'):
            changed=deepcopy(value);definitions=deepcopy(registry)
            if shape=='unknown-owner':changed['suites']['producer-api']['kind']='reviewed-subject-inventory'
            elif shape in {'candidate-scope','alternate-subjects'}:
                if shape=='candidate-scope':definitions['suites']['python-test-runner']['scope']='candidate'
                else:definitions['suites']['python-test-runner']['closure']['required']=['tests/unittest-runner-test.py']
                changed['registry_digest']=inputs._suite_definition_digest(definitions)
                changed['suites']['python-test-runner']['definition_digest']=inputs._suite_definition_digest(definitions['suites']['python-test-runner'])
            elif shape=='extra-map':changed['suites']['python-test-runner']['subjects']=['arbitrary.py']
            else:
                entry=changed['suites']['device-control-plane-full']
                changed['suites']['device-control-plane-full']={k:entry[k] for k in ('kind','definition_digest','setup')}
                changed['suites']['device-control-plane-full']['kind']='repository'
            with self.subTest(shape=shape),self.assertRaises(inputs.InputError):
                inputs._validate_dependencies(changed,definitions)
        candidate=deepcopy(base);candidate['tools/test-evidence/sandbox_host.py']=blob(b'changed CI')
        candidate['tests/unittest-extra-runner-test.py']=blob(b'unknown neighbor')
        plan=inputs.plan_affected(registry,raw,base,candidate,base)
        self.assertIn('python-test-runner',plan['required'])

    def test_unknown_root_import_shadow_cannot_inherit_any_omission(self):
        _,registry,raw,base=self.bounded_context()
        for path in ('json.py','sitecustomize.py','tools/repository-checks/json.py','tests/device/new_module.py','namespace/__init__.py'):
            candidate=deepcopy(base);candidate[path]=blob(b'new shadow')
            with self.subTest(path=path),self.assertRaises(inputs.InputError):
                inputs.plan_affected(registry,raw,base,candidate,base)

    def test_existing_ci37_metadata_codeql_cleanup_and_lock_plans_never_expand(self):
        import ci_profile
        root,registry,raw,base=self.shipping_context()
        spec=importlib.util.spec_from_file_location('affected_preserve_proofs',root/'tools/repository-checks/host_selection.py')
        host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
        ci37=[n for n,s in registry['suites'].items() if s['layer']=='quick' and n not in host.PRODUCT_QUICK_SUITES]
        paths=('.github/workflows/codeql.yml','.github/branch-cleanup.json',
               '.github/android-orchestration.json','tests/PROJECT_TESTING.md',*host.PACKAGE_LOCKS)
        # Preserve the exact legacy37 contract under its actual old namespace.
        # The new seven-target namespace deliberately permits smaller proved
        # Qt-free selections; SevenTargetProfileTests covers those separately.
        historical_policy={**ci_profile.load_policy(root),
            'generation_kind':ci_profile.CONTROLLER_KIND,'epoch':ci_profile.CONTROLLER_EPOCH}
        with patch.object(host,'REVIEWED_PROGRAMS',host.program_digest(base,root)), \
             patch.object(ci_profile,'load_policy',return_value=historical_policy):
            for path in paths:
                candidate=deepcopy(base);candidate[path]=blob(b'changed ordinary shipping leaf')
                package_paths=(path,) if path in host.PACKAGE_LOCKS else ()
                options={'base_tree':base,'trusted_tree':base,'package_paths':package_paths}
                with self.subTest(path=path):
                    legacy=host._select_legacy(candidate,[path],True,**options)
                    self.assertEqual(legacy['suites'],ci37)
                    self.assertEqual(len(legacy['suites']),37)
                    self.assertEqual(host.select(candidate,[path],True,**options),legacy)
            for unknown,regular,paths in ((False,True,[]),(True,True,['README.md']),(False,False,['README.md'])):
                options={'base_tree':base,'trusted_tree':base,'unknown':unknown}
                self.assertEqual(host.select(base,paths,regular,**options),host._select_legacy(base,paths,regular,**options))

    def test_fewer_groups_cannot_replace_an_existing_narrower_preparation_route(self):
        root=Path(__file__).resolve().parents[2]
        spec=importlib.util.spec_from_file_location('affected_setup_dominance',root/'tools/repository-checks/host_selection.py')
        host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
        for legacy_full,affected_full in ((False,True),(False,False),(True,True),(True,False)):
            legacy={'suites':['owner-a','owner-b'],'reason':'reviewed-ci-only-inputs',
                    'full_host':legacy_full,'include_platform':False}
            affected={'suites':['owner-a'],'reason':'protected-affected-dependencies',
                      'full_host':affected_full,'include_platform':False}
            with self.subTest(legacy_full=legacy_full,affected_full=affected_full), \
                    patch.object(host,'_select_legacy',return_value=legacy), \
                    patch.object(host,'affected_selection',return_value=affected):
                selected=host.select({},['reviewed-ci-leaf'],True)
                self.assertIs(selected,legacy if affected_full and not legacy_full else affected)

    def test_nonempty_or_changed_platform_cannot_enter_partial_route_even_on_both_sides(self):
        _,registry,raw,base=self.bounded_context()
        changed=deepcopy(base);changed['tests/platform-profile.json']=blob(b'{"schema":1,"platform":"android","suites":[{}]}')
        candidate=deepcopy(changed);candidate['tools/test-evidence/sandbox_host.py']=blob(b'unrelated')
        with self.assertRaises(inputs.InputError):inputs.plan_affected(registry,raw,changed,candidate,changed)

    def test_protected_producer_declines_dynamic_subset_before_any_runtime_preparation(self):
        root=Path(__file__).resolve().parents[2]
        spec=importlib.util.spec_from_file_location('affected_producer',root/'tools/test-evidence/producer_workflow.py')
        producer=importlib.util.module_from_spec(spec);spec.loader.exec_module(producer)
        registry={'schema':1,'control_inputs':['fixed'],'suites':{'finite':definition()}}
        tree={'fixed':blob()}
        policy=type('Policy',(),{'select':staticmethod(lambda *a,**k:{'reason':'protected-affected-dependencies','suites':['finite'],'full_host':True})})
        with patch.object(producer.shared,'prepared_tools') as tools,patch.object(producer.runtime_ci,'validate_environment') as admit:
            with self.assertRaises(producer.PreExecutionUnavailable):
                producer.selection_profile(policy,registry,tree,tree,tree)
            tools.assert_not_called();admit.assert_not_called()


class DependencyPolicyRoutingTests(unittest.TestCase):
    def module(self, name, relative):
        root=Path(__file__).resolve().parents[2]
        spec=importlib.util.spec_from_file_location(name,root/relative)
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module
        spec.loader.exec_module(module)
        return module

    def test_only_exact_ordinary_new_leaves_are_ios_and_android_independent(self):
        ios=self.module('affected_ios_inputs','tools/ios-build-qualification/inputs.py')
        host=self.module('affected_ios_host','tools/ios-build-qualification/host.py')
        android=self.module('affected_android_inputs','tools/repository-checks/android-build-inputs.py')
        paths=(inputs.AFFECTED_POLICY,'tools/test-evidence/affected-test.py',
               'tools/test-evidence/AFFECTED_SELECTION.md')
        for path in paths:
            with self.subTest(path=path):
                entry=ios.Entry(path,'100644','blob','a'*40)
                self.assertEqual(ios._kind(entry),'independent-host')
                self.assertEqual(android._kind(entry),'independent-host')
                self.assertIn(path,host.CI_HOST_INDEPENDENT_PATHS)
                old=SimpleNamespace(entries=(entry,),revision="a"*40,tree="b"*40)
                new=SimpleNamespace(entries=(ios.Entry(path,'100644','blob','b'*40),),revision='c'*40,tree='d'*40)
                with patch.object(host,'REVIEWED_CI_HOST_BOUNDARY',host.ci_host_boundary(old)):
                    self.assertIsNotNone(host.ci_host_omission(old,new))
                    for mode,kind in (('100755','blob'),('120000','blob'),('160000','commit')):
                        altered=ios.Entry(path,mode,kind,'b'*40)
                        self.assertEqual(ios._kind(altered),'application-input')
                        self.assertEqual(android._kind(altered),'application-input')
                        self.assertIsNone(host.ci_host_omission(old,SimpleNamespace(entries=(altered,))))
        for path in ('.github/test-suite-dependencies-extra.json','tools/test-evidence/affected-extra-test.py',
                     'tools/test-evidence/AFFECTED_SELECTION-extra.md'):
            entry=ios.Entry(path,'100644','blob','a'*40)
            self.assertEqual(ios._kind(entry),'application-input')
            self.assertEqual(android._kind(entry),'application-input')
            self.assertNotIn(path,host.CI_HOST_INDEPENDENT_PATHS)

    def test_exact_metadata_and_security_guide_ios_exclusions_keep_neighbors_and_modes_conservative(self):
        ios=self.module('metadata_ios_inputs','tools/ios-build-qualification/inputs.py')
        host=self.module('metadata_ios_host','tools/ios-build-qualification/host.py')
        paths={'.github/dependency-security.md', '.github/workflows/pr-metadata-context.yml',
            '.github/workflows/documentation-checks.yml', '.github/workflows/workflow-security.yml',
            'tools/repository-checks/metadata_context.py',
            'tools/repository-checks/workflows/metadata-edits/pr-metadata-context.yml',
            'tools/repository-checks/workflows/metadata-edits/codeql-metadata.yml',
            'tools/repository-checks/workflows/producers/legacy/repository-checks-protected-ci-v1.yml',
            'tools/repository-checks/workflows/producers/legacy/parent-qualification-postmerge-v1.yml',
            'tools/repository-checks/workflows/producers/legacy/protected-project-tests-ci37-v1.yml',
            '.github/workflows/documentation-push-owner.yml',
            'tools/test-evidence/source_admission.py',
            'tools/test-evidence/source-admission-test.py',
            'tools/repository-checks/workflows/producers/legacy/parent-qualification-metadata-v1.yml',
            'tools/repository-checks/workflows/producers/legacy/protected-project-tests-metadata-v1.yml',
            'tools/repository-checks/workflows/producers/legacy/repository-checks-metadata-v1.yml',}
        for path in paths:
            with self.subTest(path=path):
                entry=ios.Entry(path,'100644','blob','a'*40)
                self.assertEqual(ios._kind(entry),'independent-host')
                self.assertIn(path,host.CI_HOST_INDEPENDENT_PATHS)
                old=SimpleNamespace(entries=(entry,),revision='a'*40,tree='b'*40)
                with patch.object(host,'REVIEWED_CI_HOST_BOUNDARY',host.ci_host_boundary(old)):
                    self.assertIsNotNone(host.ci_host_omission(old,SimpleNamespace(
                        entries=(ios.Entry(path,'100644','blob','b'*40),),revision='c'*40,tree='d'*40)))
                    for mode,kind in (('100755','blob'),('120000','blob'),('160000','commit')):
                        altered=ios.Entry(path,mode,kind,'b'*40)
                        self.assertEqual(ios._kind(altered),'application-input')
                        self.assertIsNone(host.ci_host_omission(old,SimpleNamespace(entries=(altered,))))
                neighbor=path+'.extra'
                self.assertEqual(ios._kind(ios.Entry(neighbor,'100644','blob','a'*40)),'application-input')
                self.assertNotIn(neighbor,host.CI_HOST_INDEPENDENT_PATHS)

    def test_complete_source_reader_complements_exclude_only_exact_new_leaves(self):
        ios=self.module('affected_ios_reviewed','tools/ios-build-qualification/inputs.py')
        host=self.module('affected_ios_host_reviewed','tools/ios-build-qualification/host.py')
        root=Path(__file__).resolve().parents[2]
        revision=ios._git(root,'rev-parse','--verify','HEAD^{commit}').decode().strip()
        snapshot=ios.read_snapshot(root,revision)
        doctor='tools/repository-health/check.py'
        paths={inputs.AFFECTED_POLICY,'tools/test-evidence/affected-test.py',
               'tools/test-evidence/AFFECTED_SELECTION.md',doctor}
        self.assertIn(doctor,ios.INDEPENDENT_HOST_PATHS)
        self.assertIn(doctor,ios.INDEPENDENT_EXECUTABLE_HOST_PATHS)
        self.assertIn(doctor,host.CI_HOST_INDEPENDENT_PATHS)
        self.assertIn(doctor,host.CI_HOST_EXECUTABLE_PATHS)
        added={entry.path:entry for entry in snapshot.entries if entry.path in paths}
        self.assertEqual(set(added),paths)
        self.assertTrue(all(entry.mode==('100755' if entry.path==doctor else '100644')
            and entry.object_type=='blob' for entry in added.values()))
        before=SimpleNamespace(entries=tuple(entry for entry in snapshot.entries if entry.path not in paths))
        self.assertEqual(len(before.entries)+len(paths),len(snapshot.entries))
        app=ios._boundary(before)
        own_host=host.ci_host_boundary(before)
        self.assertIsNotNone(app)
        self.assertIsNotNone(own_host)
        self.assertEqual(ios._boundary(snapshot),app)
        self.assertEqual(host.ci_host_boundary(snapshot),own_host)
        changed=SimpleNamespace(entries=tuple(ios.Entry(entry.path,entry.mode,entry.object_type,'f'*40)
            if entry.path in paths else entry for entry in snapshot.entries))
        self.assertEqual(ios._boundary(changed),app)
        self.assertEqual(host.ci_host_boundary(changed),own_host)
        # The historical anchor is independently reconstructed by the complete
        # immutable reader audit; a shallow candidate need not fetch its commit.
        self.assertEqual(ios.REVIEWED_REVISION,'2fc894a0605103843b36653f250f854714a963ee')
        self.assertEqual(ios.REVIEWED_BOUNDARY,
            'sha256:8527f25d58c8ebf8eebab8a9e43517899b7afce2e511026d2873a69ab82f1794')
        self.assertEqual(host.REVIEWED_CI_HOST_BOUNDARY,
            '90da341e226f56b8dfb8b925af7c0273ecc41772ca424e3426b04c80acdb9a7b')

    def test_new_policy_uses_existing_native_browser_and_package_host_routes(self):
        native=self.module('affected_native_route','tools/native-tests/check.py')
        checks=self.module('affected_repository_route','tools/repository-checks/check.py')
        packages=self.module('affected_package_route','tools/repository-checks/package_checks.py')
        paths=[inputs.AFFECTED_POLICY,'tools/test-evidence/affected-test.py',
               'tools/test-evidence/AFFECTED_SELECTION.md']
        self.assertEqual(native.plan(paths)['mode'],'skip')
        direct=checks.direct_browser_plan(paths)
        self.assertFalse(direct['browser']);self.assertFalse(direct['native'])
        self.assertEqual(packages.select(paths)['package_set'],[])
        self.assertEqual(packages.select(paths)['tool_projects'],[])
        self.assertEqual(native.plan(paths,regular=False)['mode'],'full')
        self.assertTrue(checks.direct_browser_plan(paths,regular=False)['native'])

    def test_new_policy_is_python_only_only_for_existing_ordinary_pinned_leaves(self):
        codeql=self.module('affected_codeql_route','tools/repository-checks/codeql.py')
        before={p:{'mode':'100644','type':'blob','sha':sha} for p,sha in codeql._REVIEWED_CONTROLS.items()}
        before['.github/workflows/codeql.yml']['sha']=codeql._PINNED_RESULTS_WORKFLOW
        before[inputs.AFFECTED_POLICY]=blob(b'old')
        after=deepcopy(before);after[inputs.AFFECTED_POLICY]=blob(b'new')
        self.assertEqual(codeql.select_languages(before,after)['languages'],['python'])
        for shape in ('new','removed','executable','alias','neighbor','legacy','mixed','config'):
            old=deepcopy(before);new=deepcopy(after)
            if shape=='new':del old[inputs.AFFECTED_POLICY]
            elif shape=='removed':del new[inputs.AFFECTED_POLICY]
            elif shape=='executable':new[inputs.AFFECTED_POLICY]['mode']='100755'
            elif shape=='alias':new[inputs.AFFECTED_POLICY]['mode']='120000'
            elif shape=='neighbor':new['.github/test-suite-dependencies-extra.json']=blob(b'new')
            elif shape=='legacy':old['.github/workflows/codeql.yml']['sha']=codeql._RETARGET_RESULTS_WORKFLOW
            elif shape=='mixed':new['actual.js']=blob(b'new')
            elif shape=='config':new['.github/codeql/codeql-config.yml']=blob(b'new')
            with self.subTest(shape=shape):
                self.assertIn('javascript-typescript',codeql.select_languages(old,new)['languages'])


class NonreusableRouteTests(unittest.TestCase):
    def execute(self, status=0, product=(), include_platform=False):
        import execution
        registry={'schema':1,'control_inputs':['fixed'],'suites':{
            'selected':definition(),'omitted':definition()}}
        observations=[]
        def run(args,suites,cancelled,result_callback):
            observations.extend(suite.name for suite in suites)
            for suite in suites:
                result_callback({'name':suite.name,'status':'passed' if status==0 else 'failed'})
            return status
        controller=SimpleNamespace(ROOT=None,run_command=lambda *a:None,
            Suite=lambda name,layer,command:SimpleNamespace(name=name,layer=layer,command=command),run_suites=run)
        with (tempfile.TemporaryDirectory() as temporary,
              patch.object(execution,'checkout_identity',return_value=('a'*40,'b'*40)),
              patch.object(execution.inputs,'load_registry',return_value=registry),
              patch.object(execution.inputs,'full_tree',return_value={'fixed':blob()}),
              patch.object(execution,'platform_suites',return_value=list(product)),
              patch.object(execution,'capture_execution_environment') as capture,
              patch.object(execution,'_runner',return_value=controller),
              patch.object(execution,'_write_receipt') as write):
            value=execution.execute(Path(temporary),['selected'],include_platform=include_platform,
                receipt_path=Path('/fixed-receipt'),_impact_selection=True)
        capture.assert_not_called()
        self.assertEqual(observations,['selected'])
        self.assertEqual(write.call_count,1)
        return value

    def test_empty_platform_context_runs_exact_subset_without_runtime_or_reuse_claim(self):
        code,receipt=self.execute()
        self.assertEqual(code,0)
        self.assertEqual(receipt['requested_suites'],['selected'])
        self.assertFalse(receipt['reusable']);self.assertIsNone(receipt['environment'])
        self.assertEqual(receipt['results'],{'selected':{'status':'passed','fingerprint':None}})
        self.assertEqual(receipt['platform_results'],{})

    def test_started_failure_stays_failed_once_without_runtime_or_full_retry(self):
        code,receipt=self.execute(status=17)
        self.assertEqual(code,17)
        self.assertEqual(receipt['conclusion'],'failure')
        self.assertFalse(receipt['reusable'])

    def test_impact_execution_rejects_platform_inventory_flags(self):
        import execution
        with self.assertRaises(execution.ExecutionError):
            self.execute(product=[('actual-platform',['python','actual.py'])],include_platform=True)

    def test_legacy_owner_forwards_dynamic_selection_without_capture_and_never_retries_failure(self):
        root=Path(__file__).resolve().parents[2]
        spec=importlib.util.spec_from_file_location('affected_legacy_route',root/'tools/repository-checks/android_handoff.py')
        owner=importlib.util.module_from_spec(spec);spec.loader.exec_module(owner)
        selected={'reason':'protected-affected-dependencies','suites':['selected'],
                  'include_platform':False,'full_host':True}
        proof={'reusable':False,'environment':None,'conclusion':'failure',
               'results':{'selected':{'status':'failed','fingerprint':None}}}
        shared=SimpleNamespace(execute=Mock(return_value=(17,proof)),digest=lambda value:'fixed',
            _write_receipt=Mock(),inputs=SimpleNamespace(load_registry=lambda path:{'suites':{'selected':{},'omitted':{}}}))
        controller=SimpleNamespace(android=lambda:SimpleNamespace(_shared=lambda:(shared,None)))
        with (tempfile.TemporaryDirectory() as temporary,
              patch.object(owner,'gate',return_value=controller),
              patch.object(owner,'host_selection',return_value=object()),
              patch.object(owner,'selected_host',return_value=selected),
              patch.object(owner,'platform_owner',return_value={} )):
            base=Path(temporary);candidate=base/'candidate';candidate.mkdir()
            status,observed=owner.project(candidate,{},'a'*40,'pull_request',
                junit=base/'results.xml',receipt_path=base/'receipt.json')
        self.assertEqual(status,17);self.assertEqual(observed['conclusion'],'failure')
        shared.execute.assert_called_once()
        self.assertIs(shared.execute.call_args.kwargs['_impact_selection'],True)
        self.assertEqual(shared.execute.call_args.kwargs['suite_names'],['selected'])
        self.assertFalse(observed['reusable']);self.assertIsNone(observed['environment'])


class InstalledCompilerReaderTests(unittest.TestCase):
    PROFILE_MODES = {
        '.github/workflows/ios-integrated.yml': '100644',
        'docs/ios/SIGNING_AND_DEVICE_TESTS.md': '100644',
        'ios/ci/qt-checkpoint-artifact.py': '100755',
        'ios/tests/ios-full-client-sccache-contract-test.py': '100644',
        'ios/tests/qt-checkpoint-artifact-test.py': '100755',
    }

    def private_git_context(self):
        """Real commits and immutable reads, with an explicitly synthetic policy.

        Fixture hashes never claim to be the seven-target shipping certificates.
        The exact production five/R constants are checked separately by host tests.
        """
        temporary=tempfile.TemporaryDirectory(prefix='overte-installed-compiler-readers-')
        self.addCleanup(temporary.cleanup);root=Path(temporary.name)
        source=Path(__file__).resolve().parents[2]
        actual=inputs.load_registry(source/'.github/test-suites.json')
        names=('device-control-plane-full','shared-script-behavior','test-evidence')
        registry={'schema':1,'control_inputs':actual['control_inputs'],
            'suites':{name:deepcopy(actual['suites'][name]) for name in names}}
        def write(path,data,mode=0o644):
            leaf=root/path;leaf.parent.mkdir(parents=True,exist_ok=True)
            leaf.write_bytes(data);leaf.chmod(mode)
        def git(*args):
            return inputs.subprocess.check_output(['git','-c','core.hooksPath=/dev/null',
                '-c','commit.gpgsign=false','-c','user.name=Compiler reader fixture',
                '-c','user.email=fixture@example.invalid',*args],cwd=root).decode().strip()
        def snapshot():
            git('add','--','.');git('commit','-qm','Record private immutable reader fixture')
            return inputs.full_tree(root,git('rev-parse','HEAD'))
        git('init','-q','--initial-branch=main')
        required=set(inputs.AFFECTED_AUTHORITY)
        for suite in registry['suites'].values():required.update(suite['closure']['required'])
        for path in sorted(required):write(path,('fixed authority or required fixture '+path+'\n').encode(),
            0o755 if path=='tests/run-project-tests.py' else 0o644)
        write('.github/test-suites.json',(json.dumps(registry,indent=2)+'\n').encode())
        profile_raw=(json.dumps({'schema':1,'platform':'shared','suites':[]},indent=2)+'\n').encode()
        self.assertEqual(blob(profile_raw),inputs._AFFECTED_SHARED_PROFILE)
        write('tests/platform-profile.json',profile_raw)
        ci='tools/branch-cleanup/cleanup.py';write(ci,b'old independent CI\n')
        for path,mode in self.PROFILE_MODES.items():
            write(path,('old '+path+'\n').encode(),int(mode,8)&0o777)
        provisional=snapshot()
        independent=[inputs.AFFECTED_POLICY,ci]
        reader=inputs.device_reader_digest(provisional,independent)
        lookup=inputs.affected_lookup_digest(provisional)
        policy={'schema':2,'registry_digest':inputs._suite_definition_digest(registry),
            'lookup_digest':lookup,'suites':{},'targets':{
                target:{'profile':{'mode':'100644','type':'blob','sha':sha},
                        'lookup_digest':lookup,'reader_digest':reader}
                for target,sha in inputs._AFFECTED_TARGET_PROFILES.items()}}
        for name,suite in registry['suites'].items():
            policy['suites'][name]={'kind':'device-control-plane' if name==names[0]
                else 'reviewed-product-inventory' if name==names[1] else 'repository',
                'definition_digest':inputs._suite_definition_digest(suite),'setup':['host-full']}
        policy['suites'][names[0]].update(reviewed_reader_digest=reader,native_independent_paths=independent)
        raw=(json.dumps(policy,indent=2)+'\n').encode();write(inputs.AFFECTED_POLICY,raw)
        old=snapshot()
        self.assertEqual(inputs.device_reader_digest(old,independent),reader)
        write(ci,b'new independent CI\n');old_ci=snapshot()
        write(ci,b'old independent CI\n')
        for path,mode in self.PROFILE_MODES.items():
            write(path,('installed '+path+'\n').encode(),int(mode,8)&0o777)
        new=snapshot()
        write(ci,b'new independent CI\n');new_ci=snapshot()
        installed={path:new[path].copy() for path in self.PROFILE_MODES}
        new_reader=inputs.device_reader_digest(new,independent)
        self.assertNotEqual(reader,new_reader)
        self.assertEqual(inputs.affected_lookup_digest(new),lookup)
        return registry,raw,old,old_ci,new,new_ci,installed,new_reader

    def test_equal_old_and_equal_installed_readers_omit_but_install_and_revert_keep_product_owners(self):
        registry,raw,old,old_ci,new,new_ci,profile,reader=self.private_git_context()
        with (patch.object(inputs,'INSTALLED_COMPILER_PROFILE',profile,create=True),
              patch.object(inputs,'INSTALLED_COMPILER_READER',reader,create=True)):
            for base,candidate in ((old,old_ci),(new,new_ci)):
                with self.subTest(family='installed' if base is new else 'original'):
                    plan=inputs.plan_affected(registry,raw,base,candidate,old,target='apple-ios')
                    self.assertIn('device-control-plane-full',plan['omitted'])
                    self.assertIn('shared-script-behavior',plan['omitted'])
                    self.assertIn('test-evidence',plan['required']);self.assertFalse(plan['reusable'])
            for base,candidate in ((old,new_ci),(new,old_ci)):
                with self.subTest(direction='install' if base is old else 'revert'):
                    plan=inputs.plan_affected(registry,raw,base,candidate,old,target='apple-ios')
                    self.assertIn('device-control-plane-full',plan['required'])
                    self.assertIn('shared-script-behavior',plan['required'])

    def test_installed_reader_rejects_wrong_target_stale_hash_profile_and_neighbor_bytes(self):
        registry,raw,old,old_ci,new,new_ci,profile,reader=self.private_git_context()
        with (patch.object(inputs,'INSTALLED_COMPILER_PROFILE',profile,create=True),
              patch.object(inputs,'INSTALLED_COMPILER_READER',reader,create=True)):
            plan=inputs.plan_affected(registry,raw,new,new_ci,old,target='apple-main')
            self.assertIn('device-control-plane-full',plan['required'])
            with patch.object(inputs,'INSTALLED_COMPILER_READER','sha256:'+'f'*64):
                self.assertIn('device-control-plane-full',
                    inputs.plan_affected(registry,raw,new,new_ci,old,target='apple-ios')['required'])
            for change in ('guide','helper','mode','missing','neighbor'):
                base,candidate=deepcopy(new),deepcopy(new_ci)
                for tree in (base,candidate):
                    helper='ios/ci/qt-checkpoint-artifact.py'
                    if change=='missing':del tree[helper]
                    elif change=='mode':tree[helper]['mode']='100644'
                    elif change=='neighbor':tree['ios/ci/unreviewed.hpp']=blob(b'new neighboring input')
                    else:tree['docs/ios/SIGNING_AND_DEVICE_TESTS.md' if change=='guide' else helper]=blob(b'changed bytes')
                with self.subTest(change=change):
                    self.assertIn('device-control-plane-full',
                        inputs.plan_affected(registry,raw,base,candidate,old,target='apple-ios')['required'])
                    # Even falsely substituting this reader hash cannot bypass
                    # the independent exact-five profile check.
                    changed_reader=inputs.device_reader_digest(base,json.loads(raw)['suites'][
                        'device-control-plane-full']['native_independent_paths'])
                    if change!='neighbor':
                        with patch.object(inputs,'INSTALLED_COMPILER_READER',changed_reader):
                            self.assertIn('device-control-plane-full',inputs.plan_affected(
                                registry,raw,base,candidate,old,target='apple-ios')['required'])

    def test_installed_reader_keeps_lookup_authority_profile_and_nonordinary_failures_closed(self):
        registry,raw,old,old_ci,new,new_ci,profile,reader=self.private_git_context()
        with (patch.object(inputs,'INSTALLED_COMPILER_PROFILE',profile,create=True),
              patch.object(inputs,'INSTALLED_COMPILER_READER',reader,create=True)):
            for change in ('lookup','authority','graph','platform','symlink'):
                base,candidate=deepcopy(new),deepcopy(new_ci)
                for tree in (base,candidate):
                    if change=='lookup':tree['ios/ci/unreviewed_reader.py']=blob(b'new import candidate')
                    elif change=='authority':tree['tools/test-evidence/inputs.py']=blob(b'stale selector')
                    elif change=='graph':tree[inputs.AFFECTED_POLICY]=blob(b'foreign graph')
                    elif change=='platform':tree['tests/platform-profile.json']=blob(b'foreign target')
                    else:tree['ios/ci/qt-checkpoint-artifact.py']['mode']='120000'
                with self.subTest(change=change),self.assertRaises(inputs.InputError):
                    inputs.plan_affected(registry,raw,base,candidate,old,target='apple-ios')


if __name__=='__main__':unittest.main()
