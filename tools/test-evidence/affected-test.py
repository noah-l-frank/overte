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
# 46661cee2452c8f53f3e1c7a8379b60de308f63e / tree baf10c727ed59814c9b20defcca877407bb8eafb.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = '41867d3782ed2ba9ba8d463c40377723ab0af1941251d067d3c9ac51fde3d266'
_MAIN_PROJECTION_B85 = (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    'c-qa~+makdvL)E}`HXsQ9QggxUokQ=?<syU2ZBswWaWiLbW8vHEcJ*4!73o!BN9C`NBSHVL3WviyPKNo*1fm>&wu>ar^CzV*YV@<'
    'Fh3m+^M~WV9@5i?m#5+3c}Y+I_1p9D;UE9~fBxgkaZdmE@BhfNtf{Jh{I`ERe;)j8QDnLQsq><n^2vY7@^)ELInGnvWK)+fS-H%4'
    '?*GHf*T?uT81IkcKmON$`?l<8q3QF7$K(BB`ns{&IF|mqn$+}dHV<j)nzo(Blx1zUl+8G2OWRaK*8P07$6@+?_>?~U>-hBha)12S'
    'hfm3`9bOK{hv$vOr>S33m5oDJFGZT$q00NdO~aTsQ_*GB(o9*Gwe`;ze@c(X=flhK>FbB-bDDnNTCtw0wpcvZHt&{s?o&$rQddh>'
    '&AlJmcSBiJX{>&};!Apd`SARDcu61T^q3yz^e`RL*1AKV4_T_mx)_RV=!Rmb>#-cmye;#p%ci_8>#iK~J?n0*)sEAckA2(r&0N)~'
    'Tc*CA`qC;zJ`6+IH+f%o_4xC(-d^Rim;00+UOxQub+|t)hiQGQ|Mm6D{m)nL$7O1kt}V(jU+TUpnx)T6Pkn5=B5S&;8rsDtzH9ZT'
    '<8Ntt`4GST`SP+3OX;BwLp4oHYU?qt>b#oscF6lF%bVFd_l@;?mi^C<>hjXXlCrs(%YM#_Z0WKr>;2?rZs&aP#=C6pva$NXFCL#P'
    'Co)X;2T%FqbolsNdieeD@ci-95byc%>(5us^I@vSX)4C5s@k!ry4j)0+d9p4=eI9)%G)+8u37cbFZaSPuUjo`nW`bRT{&h`TljHH'
    'H;(hrj7!ljS=(hPP1AMj9>>e8F2mAhlg}t${JtXVhpZ^ua;&C4b=A}^!!$TRS3TpW*N2O1PI=Wd&Abf#Saq$RH}qwb^<6%eX-q{m'
    'k6D|R<*GH~OTL>vKOMiMyXWcnc==a%b(LkF?BHu^rY=pXAL?>wGar@MRZnw2clmYCdfmap@FhJ9-0AKq4UdP1PZzf_JG2gUs+&sG'
    'OnH^cye}N&X>774udAxbD_7O^+j#tPHyt0A!{zmz;nZ|x-85Z3tk+^w7Fj(u?u~ga+!Ir4kLA_t$Gtq?{rSf-UR+<GuCl6{>$-JG'
    ')R`wy54~{ehV(_2o<in+9<E;B7wD?IxOSSBvK#7R7R{DYXm6){%*$+WYfVFucXL@a*^b{H5#?XQ*N+eBB_iG3)A98s-OY#L)5G!k'
    '<uF~2Hf2A#rBjvHQ=KZWzwc5ST%B3n)IPy^ECwk{fAuzA=f{f+7hT)rDKF;aMrr3hp1z$lQ@+fFgRqRg#MHLC7e0M>=hfH5EIz@P'
    '^ykav08~5dQj?;r%dRX_Y^v^4JJz$)*rzF%#`Mj0xV<0bg)hf1hv|c`_s8Mcjp_h?9A4+c%ia0Li(B^MiLC21RC6(mDV2+8IL}qz'
    'S5+4=F>mU48J<jg^KRBt8HeM3c$G_Dj#6z?PIECgedT>L^Dv5=eOL6$GPh;6<ax>@TiNZKd6iCHj+FB><lR&>-ICRQ`%q6s>uPXJ'
    'q<eL@)WckrMapm9!|&<oA>H4tZ|UMr`eO7z=C+yUb}ZYa%8F&2i>A)yV@s3dWxn5Hxp^mFh6m~Pd?&~EDL;L^`+RtgT;<}fvbeaK'
    'rRv5kO~Oc<YL}T?RIZShc9^x5r*!+Sj-!9+kBwl~Oi{T^^(b0aW6`$0-l5Fqa_Y+D3lhhg_@}q;;_+O04EO7)ej28i%Ym(%tFCCP'
    'qHBt!Yee<BF57ADhNkdY7gg5Jsp!W3<}Jyomixn}&o8@UZPS*Ej4B(ddUUlU=REK7wiAEi0nKHmW?S0v9b4K;w>*GashPEXnUzh^'
    '<way&vMi6J_x7@`?7Fg;Z{C8mV;1ZVe>m88-yYHBEWo!ij9I^^-#mk|Yddj&Yy{tBR3$I@B>rT#KbGeg=j!su()%>pSb9`XO_NJ#'
    '>3z482h}Pk+qN$I`W>g}WqA6OcHaVvgf|<eS@y9szLDf$=T%$#NZNQpjr^d`((P~Ql&!v91>^DcVIDRDjnAa_;YiQDmJD_=G)kkU'
    'Zl<cp$EM1LT%Ay*U$mzk*Hf7m^=>~leOZ;MpX(_b7v*5?OYUZ$aYUSH$=<o6^^UsR6$YnT{$AuROc!HUq+yuT*!i+mIYU{Npn*l2'
    '_0IQ}9{xBy9Us2<7f-M5a#>dd&I67q%W)j*sc}V&LzAkuNkcalo|zkcF5kDO-M45rRP6v7$=ha39gJqKRJRf^<>e^%Z5((zs(#&e'
    '?hcZ`Pp8{sBNH6Q&IdKO#gqxeqn9=I&D3`;i_)Dorlqjm_igQ_TYhW-S`uR4_yR|hg-lT=c72gga*=AO%3<!OU$nL9_+`aOwjNls'
    '45{oT@>QP;l<_`0Nwe^6x6Pc7i+i>!=U=m{=k!N<*r=+Nto>BS3sgi30Ga32Wx4C4C{qUwEd}!7ef!xJ38aTrUk1c5r=_3zW^m&U'
    'S>y0e0NK3pLUU#AJGb&(R`lht=Ns=~%tHVSWh&KN?L0x$`g|Nf26hK&OZhxh%lr0qeQM;r4RS^}2=p{yt|fy*<V{ie#GA4!?6As~'
    '@xA+!AKgt)3AX!k81A1p&;cb^RTVDUt{<gs%i>{0PLPk1-MpM&fGXE_?`cm;P`dnmIQ|D(G~~H6FRKRWLvG5hQK05SI~T?KHgiMv'
    'CWjoCyvdu!2~#!?^&<Ok>!r%mkh^jU_h4R3@7vh(@%0I)H61@Exb<{7o3q}WDT)S9CQ!CC2Q*$*eUtz|^Vvh2Kuqu4Qe>5PJ4#px'
    'lY9->SG2XtY#H4%1=M9Oi#owQg{Lm-^6FP?XBiInuNy#bS9MbwQaxl<Jxm%Vt=x8yvrL7@G?iu7YoO%s{H|ZVJT8a(^sQREeEeIN'
    'epBk7G~gf+vjNL^ETeok3rJRHr>L8Ee%&umug@=TlHb$Ur!8pInU`NW-_@9M-*oRCX}8F8$J|Gy`BKeYdQU}g#bzSQ&a{+ZqD8Om'
    'lLj3R9j|K4oUm!E%DRU|?7RNYAocm5T)r*l5*p~UfR47c`$9pV$z<z%tR=EA+Pa&%ZeND|>2(cv>FLYi`FZUjUQEWuzSob4M#s{n'
    'afWGVmMRlRZKf)9Q#Q<E&c2`g`515ic-#v3aY3smx}k5YsnV7$gf{hg=LVm%d<MrkCi~Vrr7f33rw&%(;Fa1Rb7WC~@00_$z$S}3'
    'XU<D|nD^yR4=(>d(%mqBIb6O;bT%X(;$J=%O{4n(m6(@FBeV4XN&r`-VAxp@oLAigCT5vSTv-+cQah!oQP@{bJQO70qe;0Y4D9=s'
    'zCTI3bBw9XQ!y&?)rV2F>Huk@YM3ticx6`1V-JMiSucLy@7Z&d+F5N;mGfLe`Rlfd0zdV#=h9L3S*xYhW^;SR;-|uNIzFYl-&~Im'
    '>2eJbp;a)`=cu%g+ooxu%zYM>d#@SQs8fe&*@@A8zk@HwKhj!^x`H;YLcQ|3)mF_$J@J5Xr8SbyxEtYOy{f&{c<6`yd$=yDOp_;`'
    'm5z0$^;K$g=_fCx?zxkeTtEp`VCu*H>+cLL`MjtdyCG_AI7-_&ae=rw;+=ztDNsh<UG87_6km2cb2X6nu9;i7zKYx_?Bvp8skvIX'
    'aRJ1j6aCL?m;S4Sy?lpgWM|TzLFyV<NL$G4I}aY9pLyLmoJ2yl+`jy|+c!PFUVaYFT|S{IWC2B^g#<C9&KoGPdrm*0Yc*Q>8#c0U'
    '{c@=_IdfT`W~by!mby3(W#JFH0lLr><D6ap2}syiE{CHqJYB|u#?eh$M3>dAG6{KgZBJ7wY9C<|96OoDJdZbTVc(NzJ%8(En%)Dl'
    '!R)Wt1|I&PK2C0S$yF`SxM3S#Up^ln_5qsl@hcL5I?jXo2}LN?ttLtZSkYrr9eZBY4G-ffeS+yIROY*XJq?eKTUpjLX3F2iM<Emh'
    '2Ig`c>p@RgMV@lCfygl2@L>R!E;nJDMxEAJOgcAL(OLuzF1l^S7$GtkYPB}Ww14US2|?cu{ZIzEWYLUBbLK{>pj(yXV6I19#-P9~'
    'SKLQ8Wd-^RwWfFD`TNNuR-A6<Gz1hl*a`03G&SXpYUuRKKO7z&Utd0Y>-T3?)dv~=hkqrBH&{(Yba6L&by1~y>+AP7$?TPiptS%*'
    'z}<_-Qq()Lq`&RP>L1b^#Ha5!7Ny7C@Dh)18#o$NiPAJRNP&Yi_$nr+S6R|lY7c$l6kqKQaP(&z+am2OPC(>O9!n8egDZ5NyG8ZU'
    'jzPdf4%5%uL77=E>o;=a<t3$RzRk!^HG4&b=zx!Eu{L!`Z;mLQNINV$mwbc9B39mc55v=!<I~-%e{UmesS5|e9jW6251X1P%0EzR'
    '-?e$Zpo!&*QDJ=VK2DYAhcj2=<MY$>|227Jdt?8v(Mf*3l@q5V3amBL+`u!Xw_S%f=oR6fR#L8^foA~9onOypK>2OEcWmbkKv=hR'
    'IqR*)wm>BeRxYq0@(?vgg+H-KhwVf1xgZ?fxS5s2dHTAMNr&g%pU>PluhPI&fTD`zHlDCdyfwA=FxUP_me}l|Uv2Jdd_COHC;VqG'
    ';3~3ph(N{AV*u$<WwRjAwrwCFFf#3yGWePK`!{#S?7n+!8$1-pE}oZ=FyU)L>ayqtYcgQuG(|8T^3+%F-`GJL=;`gHo=NAIkp+FK'
    '0(-90Ezj|C<~+I`rG{~VPlsQKaGrPlFWA|GJL_K4V|dc)yZn_U5qgA0>sm|oVCSNzHa|#dM2%7NY8xX>*YDreDd`a-zU$ClzEsBn'
    '$*Tn}dUu&XH9L@V?^E-|VcS9lp#I(X{;gdTyJmTYZ{LTHKQDe4ou)s6Q-o3t<mh^+*M?tkEYIos;mcadzK)NdhvyA;G}2@v%-i0i'
    'jtw+HhBN?-5df69E*$NLY5WD>*y$?V1z)%NoT3D5XDR@QZMQ<EOB$!FDW)K)6&_rc-oL5m!>5%UaUcaz`R+KBHDJ+YsOSS|S3ulu'
    '8N1G5(7Ku=x*iyOHT`ec+nVX@XuEf5&iiPuA;0#%J=L&^D8WK&B_cLbnxW6X;1IkC0WNQ6(Lcrl1<6WnKtml^s3{tCL0{(qNb8rn'
    '5pLYh+a5k%cU9{5TU76_oX3ExIyV!JGNJ_P)(EwL+UD)eZ}Ho%){An3braAPa<=<$5T`0fQQ{59g6ob&8A1ib=664zbBMnT>6AsG'
    'SaRjKkWnEZtoSTqJP1KlM=S54omKtbz3ez<1x8Jf`cN`jC?npkPWvbyrfz_4PJ?VzKf8VRR?hXq-w)eH1jwRXT3VfxVFa<4W!BC}'
    '|BHXC^unT}0sw#S)~?tRP!QlFD&lKZ5~?vstMb3RpktczG`0bcXBVo;`S271qVvvDk=|MnD<C^eFWXq~qMNg1lWwTewwwCMr}_*6'
    '(UdT8IJvTBXv=H%uvNsW(i9;@SGURo1p!4~8C+&<rI{2%LD}ZCfV+S9&PJ1dZ$`~fEqd|jLM71&*;<WkA!S3L&UGR3{zo6D>u-2i'
    'wor>yXz(L(4N(;9{X-M|Frp>uG&v4BRpUkfh`~7@C$+dNbGZL_hpPXbMC&g8*+#$4vOeGv(>Lz3G{UcHiV|N})s$l}#mja`mzNF7'
    ';blywpBJ=qeSt1Xgs3VpXjR-}XjgnQrGTfGRbF1^l<=(od860cmt!3;%ed5SQ=kmeLbZyvQkN>Ce<GThfAFIM{z?ylihmrQUJjH~'
    '66KZY^0L7pmz~d;chF#02{}%dPkKdlq{Tt2EEeq|?XrtYu3w78+~04~+486bH1rXECmg8^pLNbaZcS3ScT-K@C<grKj{T1XPsEVR'
    '-^mcjUR`EbY5?C>o3TNF^2L|EYM?&V#nZ;`dmfKp?*4FV&)X>t7_(PX*N!%D1jdj01*=&IB*D9*%y1s({zuL0Q?@dvKMwI0)pw6C'
    'vHG4wFAH%38c6__4t$EmI;t*ZzDsh%f6r!3&tYrPd3byY?aUfs{$oW?@2}_TsbyXxZd3=w9S2<|{cBi)Fxs~H+(AyU+xM;b{7qH;'
    's3`dM$Cm?J5gk=pVxO*_2GI`k3J5*7gBAlg(^x6TX}EC*kB^7fFL!%3G6h>(Hz~Di8@Ej4#<N%+$yvmDv|tp5p}uk>yB-3*OryOv'
    'inmn|MO$D%fgB<K7>Z_`h?3oBKawC{UVA#;yI+o{6#h(m-2V2<Dv<k;nvGysfu{D?ya2BUlaC-pkGYfO&)4o|1&r@LB@OqjmLsAU'
    'im|hxn=h<Yk&j_CR9zxju3AVk3{F+HdkgD#u<Ko*6wK&mi+~nXv${gIT4;2NX#c~Eya$+8vHM;8|KlC#TzuJB63MocR$wI3yjOnb'
    '909NuYPHi<#VvM$)@!+U$vHj$u6uQNoL=t_f9`trVAWV!-wJfnNO{nBl;S!keT80*%Y?v`+WN*Ve0qGn`-~rXpPn~hO+Cd~@yO^w'
    'yF{};uS$stNT-b6T7hHdZKUiM>;oy<^^WSk!86jL5fu=}a7deFiMHPyB~x$_Dspn_nzGD)&4yNhX-6|U!0<YB8zuezH0%6QOVm`z'
    'qzWlsVG7<=+1$7*7xxop#Pi{IfBW`#7ZWd45Nb+a$$@&Q36QDPk)_C-JKe51WYJm(#f|$pArQmYdjTzKq;&Y%75jHcHADQB9c4>X'
    '*U_D?QAiRSk1Fza<_jwCRNs26uHH{xi~`3*J5qGLS^|rPO2RXn)!;(vB>66X=qmE#{d_r2zwbKSLl-?9MKxayo)7djS}J)6`9l-6'
    '1ZzR&zf5}<K39w5;bGolU#e6?877!bIbFJMG@MNc^_#%Xa>11db!v8>=f}fztUfM>KVJg%U%}7IaV<1E5;}Q=-eZ)-K^Krt2I>Jh'
    'R)feo+U~mb|DsIozE+g!L(ok%kFds~Ppw|An4MI(M0%rbu=@aI*KOn}tX7`(Z-R_TDHJw33R)1|FalS@?1m(UNG9(HPysJ{H{riE'
    'h#FVi@l~W$bEuGkVEu?f<WiM>`aa1jmV`?%4NB4*cW}ygc0Z3$bf|Iz<{|=C#Os42j)cF?QWC?J6;exA?Y`^(IQrYW)zT=c)s5&R'
    't;%%oN)ccT3R@N_zeR;5bW#eOU=?n!J?>nvcldpD=vobJ9|8$%4IElmWLe{sV4*Gyikqzk31+_jkF-mArRNT1hy(As@}ieMG)@J~'
    'p>e~@^m6F6{=?Ris}$|6F5l1z_o1NZ^@#JN-(O`3V~Qt0m^pPCxc)L>C~XCteL88KC%97%aL27EqGPT4CIXVROz`*mq}`sXy^F2C'
    '^muLu$A7##{Tnia`yFl908M?mvx=P!MvM3o20+Sn4<9!v3!9~OoU>cDb9jixFV4mI%6IGO?(ube<HB6tlaTN71>!;{z;_d{XV$sv'
    'm?3GUw*ljgxcTqeQ>feMrP94?X^XkWv?R0$4R`@`2bP-9x%mW9--Bt&I@oK&k1Ua{*w1(E8|lH4UJhR_UsLWt40ievWiNGb+*Txj'
    'PKS=K0~8uF`R_d3va5SfN4Ga^g=TLdizYqWtxnA|dr&!+kRn7YE(CV~3wTI=%O1Y0?LaMwtvwWQEa(e_2f!qKgy*@ieKSn6>_;p{'
    '`yJ<7_7L_y_V6_CcoxacREFY->zOYF+>RZCbHWmVlwoej82}Pfd&@qwMxz>keAR>B^>L`VdzCPyfuoILh}kIR=j>re+C|+Gw^q~N'
    '^l_|U&E4tVI-Tsx?<aFNH|jyzEB4kHAQ>nZX9*<$18|D3Cf#;=VDrZ(0Kj=S|NL^lL8_C?ke47Jx=$Dasdp;=U#c{uB_ZE!s%W2o'
    '!B*nWE@K8PR+?77I<1^CencLN7=sv#Io_r|aPDqyZr@9=GM@(@%LaNAC?@nf4^0YD2yDxn0^iDKWHcRL6ZDdlZrRB5@a2&v?K$|t'
    'r`G-!ao^v-6IEC|4*DsLg=~LO@o1rqHBul(wT~v<6#HL7nLh8R0IH}tz(%c}c<a;9U(tsc012476_f))4+9);*~IDdnC=x~m-m1_'
    '7BZ0;cH}c5fC~YC3;6~4XqE%l@$TCF$7cFGyu8V1hL_E=5<Fo@c5sw+m!;Zp6+pL}1sT=(4U<52H~YicH<QP+brcBq^9DkIkO1IH'
    '`aLbaRkRJXE3p?yTG%vs9093x`-9kt1bez&j$^1LHB*DAHau=5NvNM_+tN=h_j>AdYIt5qjiP}nrmD$H3i#a{i5Nb8o$k{)Z<{73'
    'B=WbH&#N22ecG<eLWhi!&}2fF%T7NL2#PEaw+|ABULa&3AAZrEb{KmhjquSU!VhOdVV3lN0(({Qr@aaq;Dce<{gMsM2d;ZB8;tjY'
    'gniOW)94+;=Bo*!)wBp7*h4-otg9u;xL>lPr}WR)t(cF@9G{K|$Ipw&V<eRvfgGqR+P59aEn!U6zIQ|S$4`fcU06$_P38(raY3`X'
    '^kqY<E7^arW!Y1@A*<lLymv>?kLS>6JWOfV#{}I71b6Kt>Xv$AecmWk^bkk(wqppG-AeC%QW}omRMT5~@_xJ>HHnrJ3s&KXHR}+>'
    '%PcZH{N6=Mk>>aA={dc)sXoDWABM;0&&Q2j5$#sEf{<PP&L$jH;w{c{%_<lca}dN)w13&IULWs|!)2&>2^3xd&q@@Vmk)?i1Tkkp'
    'eAbB$q#mKEYKr&n>E-x)dN|W&FDF|t++f8{>Xo6EjT0V<M(8-?Pkl-7Uc~msn>RGiPl3iir4;|h!zM@2wWVyNenEMG=HZ=oVQ0rI'
    '1gEj93Rf)J%B|b+528_V_xa`JaaUjx67@}sl~=*5K`^MWJ`ob!FF2N5s2bj_dGp>4Jx@=E$30iSuGZLuuQR2C`jSRf@&|<F6{`H^'
    '4iYL-CFeUfv`sVBBgw;oKt(whGGmpj>Y6<Qi5A~TmkSY9J>Goa=i`?_oL;Ywzr4OL$Lrj8I#9-7;YLohV&sICxHssp5+*hiVeItI'
    'E!`hNYP$oiQ>JuPqG}$6KMENr)(jbDq}CNu#V*u5B2x7$_M@svhb<$ZaIl+eSe^?)CPLbVeH90di41~S5e>mG3V-K@Le9irZdZgR'
    '?!%No@X4HMn5}XPyov9FC?D==v#c6cQQo?x6XWRH8T(FgcKOxS;ZnxeoKx96NTX>&+vwXXa(HiyWL~P%>{o3o{))=D!;)1>;<bg7'
    '6%QxOWUR%hg#_{i>%3jaBqev*{i1y>+x9l$6rCWBqGM=@DqQ6-yO((*;)s>d$d;Doog0c<b%&KTW0nX<3)U+%)Cb*ZNA%H)Q>LQl'
    'ASFe6D1YZ}PAtbKhwcRfa#LA><%)19)u<?0=>$lx^5Au=7CFp?brOdQOw)Jn>U@8^KJ0v0I<|0G`K`NsP{P*KO&y*{;5;CB41I6{'
    'o6=ji_38L>3{JU(`@FY}Y#Wh11h1)}zOI7hh){_@F)9GG7F$F)jM1B;cOVPF#|_x>@);X>Z^-zCW{uXMR%)!e+#EGU6EInOQ{#KN'
    'btCu3d9|}TnMYkle5!CFr`1Ct=~oSaO9QP=O{DD&+hu<fk^3EciDKydlFs3K*Hr>`$OF?>yrOEF<5318S7=0dRpC$8Dw0$u@7vfa'
    'qMp~2HXS!x5s{!t4-qE#+4d;FQxMBB?uZH%anTB0!J%9CbcRL#dQ96}G6X{fYd%Cs;-Dl97nY#z>dX3+#mM-m^V<s$tFqfWzrUT}'
    'NF{|0(~*GfG$%OQb82pbYD<2PnTF~cWb>QTl80k7jsnf2fA_?;7{9su4DWvmu3}n+3c)EzVOThUYx0mY@xr;e{y45V<f$COnSI@e'
    'iWD`B7!XPGFeVeF@y7#!h{j`zDGd|wG2MK_f)?YmR`Uzl`;Z!t)eu(6q5l>MxZ`O0#~)DaO+28?v$4<RJv%yEL)^W54%fZQ+hGQr'
    'MW4d5lErXI>#eWrhiMu;FYFkK#+y^4b4jKS5*-l^w@C+~&2`qX?_pNGgqwoFr$g>t=pGcZ$yQV2=6h_tN#}icN8x7I7GT!KF<<^F'
    'R|HaP$?Imb*3$W6c0%@Y`(D;Np0s1{X(vjo<oMo=s<4`1AN<FOK2+AUo;n!v5A!~nckbwqFFOoA!aD@&V(?Ru3OIEqhsM-yMz+#1'
    'Ze^BO57W(g&>vkSu73oYww2zOS+IxtfUL_HdtvD=>>=G*QC;(wRwnhsJ9d)(48D9ctasavTD))jFnAd8hGyiFs16O?akKhY2^A)0'
    'ckkKMVSPGj?_=t7^6e>Hkr8W9Tfzem<BCOG6$UXdkT7H^`}ghWxT793?kBRcVD6ekV&)NE55SCyAdHIe%_AbVw?m$>lb664j!zqu'
    '!zz;XGF%;6<Za%WWRK!=O7hksD#IltfbZDHnG85>=?&5BFpK$=!SGoIvGAQVf7r*BbC{wy@|3h=de2tA-BTjqMxHaNm>E+-IH0^_'
    'EKSBVhi|1o=qpjxyUiW(U$L3(?jQgx)I#*?PIVgyjCLi}D)=WRhMB0s6C{oA*i6U^H?&hiS;$|)U5~9_U544-6qDej%Gfayuz?4`'
    'IK5{VFX7gC7bLDtEJ`^XEm6&C>6C=jesqn6JBVEnB|&B?p7+GwZ#hK538C@dFni*!!D`P~EnM_o!_YJF)-+YBN~R+~`=jONH0!V2'
    '^KNZyZV36gVACUl-jT~-r(RUdebTm2a{7{iKH*M(%O&Z-gk}Pka^l!-h~Ko{xDQq_6mbkMHcVsqlPl6$#?yf~%dqz6R*(0rc-{;S'
    '*8jZO+m=ZVVNNm2n?RRZgLQbLjVh{MVwXijjD_)j$^$;>Ndo)#{=^%IvfH2q$6F%_^A4I)wOE(nOe`jJI2J85x`jqVeFa?clYOlv'
    '!tPy>!B6qBSOas9Bqi3_W#z#dwg@9T4d>niY^$4hb#9*Q-H%ilL^+Zz=nTX;*L=fFz|kkHbV+Gu81$9rH}B_r7UkYeN%~^kXjD%q'
    '%DM*OF&NVHIP|(<P<wVZSEO4%+*JIt{d-zl-#7r|-RR>IQ@|n2D~r%bqApTrK`qa2-P80mJbz{j`EYz0w)Nj&CES@lG!!g5;HOCB'
    'VgEW~hp873a20&T75un=+szrX*gqV|8;e1u=D(T#7hymaS`dlzUg2d9(X13(H^+d#!%jOl6}Cb%_5?v4-hWI=V~L-crG(baN>rvy'
    'l03}w`!*HT@NT<4J}c#NG7Xd*hcUP@eJp)4MRFTBc<6@8=GGm3LsE8ch_P!iPK2j*ihDK2IAsQ;$puLeF$w*1S@O;AEgsJBtlND>'
    'd{plivO~3S9exJJl}f+#OXaCGgMPKTd!@g1N9XcWKK1%3h6QXu@lYmQcC)X-y@Uk~a`F<Rc*|&fHL5KVD?-WU-P<{}bB_D3H@&xT'
    '-SjcRotC)f%$f}Cq-qCL2(wGLC}Vo(&eq<*-aW;v!8#OPdUJ#hGBT|dlm*pj6@a)*vTJ`huIH*fJ%4_EiG*?geF8cakn*r=MeQoN'
    'ENS+*c@c-GpcET4ABxxA`#NuA{j{IoBIfkE8cDz4ElA-Gmy;8>R|2!BgA6jWHrG&e6T(}4XW&b<gm+xuzh_6s@i$46DplCTEq<6c'
    'j4;AbiO!WCjX6K=TlkF$<?ygMG_b_S?v`s3rXTF-Z-2CzTAC>8O?6>n&&h~E2Bd}4622s(n$_*sQ$%6izoW$VJAH^&yj=3%^UKR<'
    'lnMxiG6O1vjz>PSL`Z;)b-?d2u0PftKeSx=*=ElD?(>s5|J}Kszr2;u&n@mU^QcUn3ks<bpcPXV2?z#`{xfRr6?EsHY-Ka`cR@f{'
    'Fsno7qfR#BTN4#AKUm;J_^e^<SNqS^%P@i{&jjQ3KL@$@d4t&+<0E)2dKyhQ<Dua}#FiigFbKl|(pHXXO7Gdl){_uX%pnN3IiDtR'
    'U5asOMGPuo5XtNnHIYwFwm*$NeVPx4IKcFD(6{^H>q@%b(3k~}I0kStl#AKzg^Ia>J0T}1p#kr;+WiVL)M+22e8bb(>h7c>*{YAp'
    'y$~=XiU2g0aD;(rBS6Kx^%51Ft$N!p*KLC}_ubPFS>WBL`0G|5Jxp&YYUW6lnKcngAg(Q0;I)PZ=+78aE&J)N--ZAFdBch=yhYlW'
    '3xKl=xWEh<1E%QXs==Qn`_*X}n&!I2Pp=?8gI(_ds{+o*gbrzuwFz%h?I<j8JVp-cq0Kdfu)0DYca~X&e&$@$ZEJauVhN3zVPn6J'
    're$J!Yl}}37j>>b#ePR1tjFs%afUtLK7<ViI)!!$<Ts3-jSg9YmZ#w6D-(1ppfv74-d*`U>N|0I+9wUnV>-&L6^C-iGfN$dKwU<Y'
    'm-mc!)Ka4x7?!Tv0Yb^JPMqA&4<I&11{9i|$S_pYdv~`Jsfd#?V1lv#4^8JTZex|CY)e7LJoE=#EC_X)xF!&g)zpGF45T#TgZJgU'
    ')K|WSbBO-#5$v*1<7JVBHnfY$x)C0YXj_G4Fb|Z?;78*kjaR-AJ*`owj1#)CJPkN1KkKikuz+-c4l}=WXs4jmxJ{W}aO=8m`PYL?'
    '@8xCVW29yC>v+b;eF+BBFUsjbIai>t1gUolz^<IHUi<l9hpp~(OvnuqsInlGvFss&u^UsFRC>%tK;L<2p?9wx?(`>G)0eO=iMa)7'
    '+~YY_F<B}wUjtp2zyP=_-I*ackANYT+j-1TsEc>*WK$btk{T0$uE4+z4{}brF%cGJ$k?dWdyA56smANK5v!lMUOTB3hWzvtQq+wx'
    ';TdGZ`ObY2MhRg7RtCNddAj1|ge2%g@VLMJEtTMtmqf1>V&3G#@%wW=y4Y0wuZ(7nNn)tF0;yAj=R~R7RJZTyx8q^eRjeA1yXAiP'
    'v|-B}t!FLrU=Piq6bQGZxae~#VYye>!5D&7+`gleE)?5CnfqyLN)AiCB?c>V`4h4rOFYGvP{0J~TURY+G8p^b-@YBJ#Ulmr`R$p#'
    'usoqQY(P0Wdf}2+mZ3A@Bc{9OvNMORi*XsDVy$_TY!yr?0QPlM)1ZCz=f;>Q-W6p8(2_i;<+0+8AanR;&~u<kS<F~1wqVipr#f-%'
    '#qY8p3}trUjBCf4<spx00XA!gHQTnV01N#ncdzPLY-AHo;XF=xOhB4L!B~a`ejdCicd1jVWaityRjQv`O#f!o#jW%AEkm0nsIies'
    'a6W_*pkfw$C1yi32@9|@%&<m#%6G1RLYp@X0%N+W#ugB+2aJTfy?TZ>)Eu1(kDbISWy{VL&kBJzHSL~Wn`sC#0+$q>39~?2v$Bco'
    'k?t(IHdC?on>KUlw;ddx$TpyUn^VWy7%ZTmj(N#3dy{$+_q|?)3S5MYqcQ?_Gh_R<?7vRw;!&EkWmnFFPDj(|36lbJUOCZ?!L|?P'
    'fX-r)uo-!a`MPsyjtoxHUynYRn#ap8o%2B#M5q||J%tpa3==#`5m+at33N(PJzuwhRmih3><ZNhH-b;g5CcI1NUg$kZVr#a96P{J'
    '^dj5)$k&O>8$?t(M&(!xwgLkRQhYaK=$Jl=E!0FIroL{98V<)mOe0YL`8eIZygqDstA*;uodvB$EGOeiF{G15+IHBM$A~HFplMU~'
    '8tbmeT0GtDadI;JdX-3oGGd956!KAM)f7^7bRp)qF}*0;v+CD}iRfS!x^~*r1fLE8aKesKk##Xq+j?48ahR1wE!*uva=c^lv!Ck8'
    'p5SiVeB2G>M$qROVq$d>$QX*RBcy|uFKB>TF(K60vouh5`Fh<iw@Mx8X=dV)%L6>MNb>leo7+YGxxW6U+O!w>Ej|3s-uxq04IIX`'
    'vEh?vW`+?KF$W6$D8(S!DKdOM1PCs(8JZ6Arljd@(bJsp7#TSRCv7==+9><$n5qK~L@kH;5P8S}q#u!LN9ZJHV7W2vT>Z_y{B6dx'
    'ROnOMc<Q|OS64@B*Yy$81w+I5X4m2F2&EH0sRjF;TUd#lhl|Fx09n5F2=++FLlC+|GU^Of1^!*~<z-QvY|0PcRy?;lcfD-Rj2b;e'
    'YB3rb#^-sbfHhEK*bcGWV{Q6F_vfFleB~R@X&+>q04~CUWgUx()$67h>c~`@1uu|uOLxr{c06;+3a$n|<h16Pt_(US1wgP@SyWYK'
    'cu(Q?x3TOO<HUyD=4mQLuhz9#@h9*fI2ji7R5Bu+uCVIVLtQjYw-!CluVE|l`uIcT@Ap5m7c-=IGA-6|dS_+;FTur%WDsE*$1-M3'
    'Z&u8w6`xm&=;vK^DPv8|s3Pz(jRs>8ay*{ad&Z?fE;3R&da~`fcj3oS@*2^wp>)<X2&O<EeT^nuhma&?0zTxJs6kvr=riP-EQ@c;'
    'uAT5r!8iXJsJ)&6@{(vtp%!SJWJCqi4gpP&f2U1O__tM8vdb>N81`^D`fUmg6GhC@h7&XPDuN_?2W<p4th~eOohwIKaoFZoH{p-q'
    'k9wR!l$AoJ7wHg_-|)qBgt`9adB1njl}Ga?wxMndInd@amwl<#WOgjTa4yZ^z@DSnrsh;sw_F?4kohK&?rjri`i$CfOJQ3D@aL9<'
    'y%MkxYwDb9-#5|AH|RKizGAYzZrv4+RV+VlsCzpt85}RRi(SO-um<vhF^g?O3>7Xh60~{e+Ha~tDcR*^U4%vs#pF^wOTRvNC!tj#'
    'aWsyPE+Z!lo4cLMF85zI9J9<lglWUr1!U-+9H(Kato<+P9jQ=>b72KLmpja>1=H~R#Xz|L)V1+rXm%EOgdR&5C29xQ^|Xhuo0S6Y'
    '{hUq>mxuJKT)dpo!_%Q*U`*{_6*IrT@JpuNHYOW)MoA&X?uWe#|MvRj@;6k6tzpc*rc%#Ci@<M^ptp&<HVhbfk;VL$X6JgRA!K*Y'
    'Umy?{AFwXY5Yo@kJC+Qc8uNhr5I0GQb5LBw4Jp8~cilJo?e?q9k?aBpU}Py+`iLlFU@a;b5i)4&tlG`En66%VXQXmubxyDjk{?}3'
    'F~X>{)c!Wo2-B9Fo2qfy^uzwP{_*(xMjvx+*1F(X(f6Uh8HuL(YOtxr3=7V$(H_;_C=v74HxyA0O*kYIWV`r?)%fhW0l?uRg%nnG'
    'j(1({UGMe&<*?2vy<8R=y%Zj_LCXsPFIcUQ7Jkg%1jaLN)~+dbe@}0NKbOJs`;?ymZJ{ZJFLXf4F$xNkz$_Imd%U?|5UOUd&(0lu'
    '=a9T>dE<<vH@tWdez~cJA8jCbz&y8K3KT|9%p``L%b$IbIji5leBM9<LhQklmZKt_jIJcBB=xEItPjU^zeZ#yRoS`l^8{Yn0F_|&'
    '?%Ej%a|$n1o|jd?4$1=zEEQ^m&9=N|LC<*e;Nl%bhYNd=p}w=D)n<6p5Z?a67D*kP&2`xCUN@Lju)G}rHP|rJy2@ctbQ=gnI1P(n'
    '94g45sIe_QHhZJ=H}|6NjHoXEbZUsHX=9d$qwGs2)Q66PPJQD(b<P;!1iSYRK4G>%@~?P~zi(vlf+4@M;AVjyVqTS;(!BCTkg=WM'
    'P4a)(n@gYjF>8L6He|0=7z)ZgnsEHnuu^-6o$E@_Bq9_=6^v<b$#QCPU;eG0DSOa`>yU{^YR<r^jp396c({>o0D$UdzG}rgoSBRF'
    'Aq1AMA_w!B&TC|a%fj-QvPD$>%=8+KJMyyYRy}1rhv(xCJ+C1_)Zcz$5z?tP7(LM!=v7cIlgLb5%|p5Sce5@#t$#W5;eMwC<WffZ'
    '=|HWgY87zM_i5bv#7)nf_J)zy#}!I^eGEd&Mn?cK+hb)<98P?aoZ87&E9iejj|7ssL~Pl6Q=B|B_mvDzskvSy8rhm%&dAV=Hs+wS'
    'gj-Q*@Es@1es8&QGK>r((WhaDySC{_!6Nn@$1H)BDDG}<Vm3*LF!Gg_Id5eKRDlnFKAqn1$2)&zZGN{wn(2ePr`=4i*tF0FX0B|!'
    '+8D_a<&qkPdN99c;kQXu=aD0qKealny7|(%sqoMJTu4B89aJ&MqKfh0;&@S9wf@<uf1h=Im}GhKA-=;T)8TB*=n3j;9@9nTWfOgN'
    'zUkKYw;h}jiTm&}e`5UtE!gnr<a^T*muZNwzQdD7q>4`>kI_At!VtHy+2khtZ4bK^_L#Nz#{k=CYxJB@wH)kdvFZ_V3<{g$a;mOg'
    'IR5PoY6xQuc&3a6i&2TpgcPK!Jw+P90w@TE=HhJKA*cB<yFRtB&N1zG0hBsQzBoc6GF0_W>cexp!F~?v`o@Znhetw`twc=e6qw5x'
    'QzNSwP_UN&hGWP}MpVUUBX8Rr{b+3E_ZL*~MyL`rO{<|SgPk#l$)k?BYFLI1zywWiHUR<!zH%}lC^&f8m`>0_EQ~M%n&QaDT!|np'
    'qkfH>hvwwnu%4Bb7;x%0ZRmQSlB~GZin30>-Z*-*AH*=+M<E(WFH+{4e#6gN)L({g0~tTO{p@eHf4he!(smDFkr1Q3su*hv1>q!9'
    'm<Smo2<n-fW!z@N?%B|up^6mD99jwJRP)qCZ47Nt_eqQ4$^1!TJORE;@viOc`$$H^qReC_M#CYA=03!Yb}tWEN@-JZ$CR5o>&rV?'
    '$3H#}hmCoJ`E1gdMt>BdMMMI%0S<REv(tQ>prYY^ZTiNXw*p^}+INp{uEB%m9&mx?QESMf%Y>jQ3xr_|Z57(GI8+bQzJ*_+@+G!6'
    'lp>zOW@)1BJBCm25TbuA=`KY7Bzh*Z_%!>FHq7nrwO0x5>1t0;PwOZO&B84UQ#RNLLnA^BdzBz}gld|(nkv`>2Ruu<s9~?z#FZ4L'
    '9>~moAm&Xf&I0Xb&6P#vQU?T$@5Z!qd)~tLJNWH2GOIm5zet9rR-s@G=PS$y{661(ApdjdA){k%n!q)SU-9*60{6ixS~;Lm!ek+X'
    'b_By~4_2yM7yxc}#p>66f@G+IkivnOh-qZWpAib>p(to#-1P)hG%9H8md8V1?!Frszke_hRzA443?VpLnKvF2di0z!8udPe9Ebv7'
    '!0FlzoKwtQvrvH%<{nR>eVb51B>JY6b&(n1{`C4#D)(Y@FxJnuuzwzv1JH&|jUrkDM1p|R2Hll?jWI=`TE~#&*KT9~EY>Ad_u`HJ'
    'ORX5DLl9mN8Fkkj-5G8_b@XU%+rb-4=W@AY<`!B6#+{^-bjm2&z{$|ts3h3gl+ghmHqn~@*uuW<Cxrm3lVVI*oW`HJ00F-sXbVH2'
    'wI+k0oNr3W|9$npQyf<Vl#SFIY7!1TCXE7u5k<7f<o?k>3LOvp&Yf6I@7l%=rX?;^-cPD+xv*xtw~w|&tj!xRk0BZ+6oYHK{9XIl'
    'J(|^c71dWC*cA%|4o^iGr1z0RYvQp9Qx`8~clBmsLhIeWkza8+@M$wMnRcrKjf>i1C96%X+e&p5o?PzitM`D|^N>Dmi!b4|o`0y>'
    'iZGrryu>s$c|0;Kg9uvnvI7ilk|2J#f#>kD+qy4w;Uh(&y3`2i!w)&=Eh$W5Sy!6u!u7As=4(U5+jPxcQv@y3ts;pm%zD#GKUrrs'
    'LEPwBnoxgESAUgnTi89V7L#p3wy#1<qi$^L^%__Age7#0(be~jc{?}m<J(}^T@L5Cz(yf0MU2rd!i{H)bW%=%1f<K1^A<xui{aYM'
    'oO=4wiwP&`E~ZsIZFC4*sf%I;@(pN)ed-NPApyu@obxcC&`PXs-A4>}cvv$m7uDwYQN8vyW*g3V7Di|4(AAo@X(Gj4+O_*WZT5$M'
    'vX@haZAT9~6nHpUi>gLp5f1oXjmit>f+7*|5e>ta1QTfU+qSZYLC(Q&iXn*n?s?(4=2W3m7?`8JnAbbUbZxNWwV?|_&)I9M6N0#f'
    'JFW|YMJ=IM&qb)zdU4U|o}(J6z3S=OsPT8v!rd<5XC$1*P=gm@856ANj_|l9|EuG?qLvHbP_O#Rt?V<*ayyt3LywA)sz*aP-bZd5'
    'w!hT-&d%J_<+Zu?a)0>r*|+d|zEHnlhHeNN;4i+yI@+p6AHWbP-*U)M8;oodBQ!LEFnn#6^(nx<hp<A8<o9lQa$FCaY7RkCr&*&J'
    'tllyegT;tqg)~qUE218m{q@?dh~kJ1!^7*N&t$CykH=+Wj+;J$Zjv+$`3QLwS=+(jPKE7}A(!ZrmeYLgLouWF;YU}=-}+dnesx%{'
    'LM1(V+y*@@rgA*b;oRE9!A~zXQQm)F`n%@F`a-TTgU(`_TuAt1qzNNdojgh(^xc|-Ur$Y3=dn3ndt?#FuVap5bxL@$T;UT#LrR3b'
    '7@y|Or(48o5;lSkQ{TRiP12b89RA0ccP36y=psn3OZd2$V5SxcP9)mc)%Qqj;VQ*M89vXDcLvXS3^L$J>*)j~lyY}Wz+H?o)zJ<6'
    'xI#f;5r_=8vB1SDTy}(KGm0{ivx`_#t?obBbi*!oY8mvN^poYmREAm*hVA-4%G5qeR;B}{6Y>7Ix=K4q{O-<@zpWAt2dXFDSEEAh'
    'gwxrut>8YRnQKvyMCNruV7zt@*O9Ol!aP?*3n$afiuy)snGL}aZek=63b>Es>IWe@tZqW*7U}ksMUHrw*Dw<ZqD+{|BfxCMwBZbq'
    '-3;Lkcl80eX43o=ttd>#@KO>SaL~ZXl!}<!3gwtMT-C$X>F;?5&S-?tT|=)miiy+E(zPh@OGI<-T_$-@%7x9@tZLJCDQ?@y<8ck?'
    'Znnep`-bZT00XTyzS5A*c>@YmNH<oOqA6z1FF}IoZrjMpQ`qxjGD#)hha?l{pcJ#;Mw)~!zRcj{B&d5#UA#70JjD8eEe2zQe1ISF'
    '^9FjLvzW!yK&(Y~mkns7^B*y;A`jhe(EP@$kIK2PdR;@C`U*iru{uFlqlFt(d#r2wYGO1g#-ofVZ*JSmwXJPNi6G}Z$c7mk0+Ksz'
    '5HhtCmKe@-6TaR>JKnaN6PIS!MsUKAl3Z%I;4qD91%cPOYHj#v>rLgshrjw2t)kO&e!f$D3SCer#&pscuZ(FrHg#|zF~<itFApwH'
    'rx~wJ1s@O7@!L+e!)ka%O2e!Z1Y2S@`f3j-58iJXQUzYF=DH2H?BeuZKBXfIoh@>xLB@D53{DK*;G2ZW6-qLMo8XtrKSD{jJ!ImC'
    '+c<|4?j148;qb79xtOctZq<;I3QeJwaNqcFjs77+LJuM4(8kMedL(aW`3iE3UIot%I*KKWL1p5p;;G8R<0xNJfrFmG&ackf*X?{q'
    'qTLOV;=Cy)71eSeO*3u0$$e<Jgv*!q(*CBf9lB{dZ;s|l>`!}SQ*BTXg1W7qtFZu#Oc79&`%!_zh;+EM_J*6z(3#=8_qpUT5oO32'
    '=utvwXS$9-KywHp6~R85u=UNBYcJ)$?w^nh?8E6;394u9CF}!1F+?aaA(HkwEHiNH0J)e|*XE7h&X`s#JL)`Rp*M?(xOxCWSTMYJ'
    'a6u-nWQ0$s*htU3BhbE#)#<A1H!|}Q{q``ts!xa2X<(E6<HXc4t)L4LI{u`$hA>ON3Y5?roI-)tHrH;*e>o%1Yr0^72Z<yGe)J)c'
    'c4A|O!Fn7R!&6MtWQZf)T)UC|#Nil;J?Q%e^<J3c*o*&$R<l|qAzaoHY-)sSqa2*>>@q)@=02DTu(68>BTjJu>VzJI7eJb@*{G0O'
    '$uT4N(~e)ciwo4=zm=J8nm%sXIskpmjy7tHUTeM#t81dbaC2F%Jt$G%Ivz2Ja%(aJ&G?MGBx0m6AB{;F{O)7y8_P{8i5cRUdEK=L'
    '$eCq(cb2|}`_D#cgS72i?7|-lLRkd?5oaZj!Q3zaCd$z&?yua&S;hahn@xg_9zu?{R#(9{3_gZCg<*mWWuUIsC<JW7)646(!9h3l'
    '-SWdzopm{E5w>CN#VkqG*YIY?plM=&y)%ow1fO$gn`;l}iHH1{HbTQ_47+Y$m||t-Yl)k<!0eyexaGVH@SVQwT-~(#J{EKrfT;<w'
    'g}fu26j^4pVu7AHbW#`8{yHiAweMlIEjwA1?18d_oU`~4IsfpTF|$s_-p8iYdPPkAL_ZJO#?~&bi%4Tw0Gp(cyx}3{DpLhhQC2uJ'
    'sski8r7gb7)~esUGrnC?=lMb#Baen)+Y|M(jT&^7^s=<1bNrN$gc09Qad(fqSKr|h=Wt^L;ZU{)Era&r#gou@`bgmo8x4uok~Y~n'
    'f0>2skACKAHmD96D}6~)>v+lhYmIJ<R(>=^@Uh#pY4dvyGe5g`|K=TG!XMaXM!hrlrEtR%fK4$WUQ?Nll`>uTx#{+;xI3`1LF9z3'
    'DW(s@>&Rs@^T9JJL&4>;pMpFq>~8+h^$hRJ0ZVjlBU-wuG6T0qbfyPdr*Qawk<Sc=3lq0~*NPFd_9+Pn-0{lXA|otawkhdrti&KT'
    'MnqvV6xuKKrWpCVW%oo117K44JvK4OM}5L0*pSrttRX-o?-(^uk4>w|?^eZ0jz07T{n@2B1bIFWOG!i9d`@&vVnh~mVOT4f-LqM<'
    'ez)q*8-gY!uXqX#;ghAqOcqdsgDLCTtQ&Cv%`jqR6BquEg?G$w!qsIj!%24PV$y1ZJ%o}mKniMwa_0@u_5%=pw)CkM|L}dn{^4b7'
    '-n_h678D~o8C5`zikQg_$C~0A;KMCW*Sg9-y%E)v%kk+;^bE;DhWoGoV?%!gCNM`{A(x5#x|K25-lS_(hdhGD>ipLH+{*U*_0Fux'
    'KtQ%k{JDmP%7l-92h8TVCo0H&r6H1J-ojCDFI?HKSoVzfZ?7F4Npl%f9347B?U%6augzxWP_`skvt9VGu3h^L+}^PTI0v3M8lEah'
    '-zzLqP0|dv1cK}o!i*G?s(<=bt9o8y4<D3=i?Ou-_1p9D;leM5f8yg}8pUuDg1$a{=7|`Cb_V#OBV6!Af12Z1<u{~^4{Mtf%J$>W'
    '`1`vjTS85RU1gvZNU2)y1d}%mtV6M)b}IuS{W&K;=7653Yd?R8;hX>U^5@H?8AC-6G1KCmJwajwCAW0C2{S|fV01+yNAYthn-KWn'
    '?MMDtknuM|h$39-HEtU}LnN*vUF*XUTnYyhf;DRyrT)@t!KaSD`><l|8(k?{aU>6R)9MACN;44A_EZkqgf*@^jDbu1PwS><dDRDe'
    'j_56%3s-+~cm9*RZ>9y8)0a917^AeXzvLxiJR6RK8H{q5;5vX{@NxXJpKapX?|q8C?9+B2q^?#Gbb#|b1U`}#zIlZEm7x}D_94uu'
    '4A}e87ZfemkK^#W@ATV$+z7hiC~tVI3P3e95Mh$+w-`-aFeZ^d4<T+}?O5wHT=V7sKK@_nevJqJ=kW4*1A}$3;^#}a6+(f<j&UmI'
    'VI7DU0J*o_{<t7Lt*%Kjeg1G}XAmPEAGhU~EC}&LC~6}p6bK1ZOuyn6E#8~PL5N8C`a|;PkJdc@b%RkSw#Ps_lbZ~h51^Y0%{a!0'
    '_NG|U*aBmIm=}J(<SEPlxH9NArf-{?iZkbeE5hf9xN(rQpo-Bdg}(_w3eM@gZ@pO(eEEYd*VCa=<kg0rrhU&7kcOMilWdG{e-_k_'
    'A5zkOu->Ova}+n8XW0+Y6@@ptE@gsbXjo^ue<T)6F2n}h*?!-84ANe<hK@EdDv9BrA7r$-=;!&yn2v~r;~3VpF%Wk8>5-fcA5KOG'
    '&mTV@7Ut$~yVKmZ$Kysc-~>mK%2$zXER{0MJN)2;B$zx*5mQ-Ef>!KUI@a3eL>O&vCLH7L@CRkp!C?_7Lz=63RSuzGVwPI}P(Sq_'
    '3qGwt@|H1nhzlp=<1Bnjm?=}^qTv$5GKW>TVa2*z$}H_z@%3?&nXfb~5zv92eNbJr<;3+WTKhJ^LxC-sN~#-vw%VM+U>m*ps|45S'
    'e-5{<%`;hr`xhC6)W=Lzz)C});$A`Zu0v{00qo7@SFLJn!eOIk8pD-cM}lP3l5Pzpco{YtF`Egm!z8&n&(c-PZeCzh$oTcGkg8K~'
    'R~RS^C}3f$1ZZu885dJK@@p17)#8_L6KbP?{lm@Ia0mw$hegE*Nh3U#_~NbVb7ntV7H{aodOSY-^A*go98Lq8cf4HbJQ^mqZa{B%'
    'p@cIkz6Q06iZPrkL+3F4{3-uz<vlbJ!Ue82B7!)}at}9z@ryJtd{RR3!giT^RdMyN{=5~K7#EWl(l78I2`^L)1vi^hJ4Q=Gn_aU-'
    'qhr2y;T>~pRf(E#4f}{*a%(V-uD*_?S_;v#?fh~gzvYLPk*B4fpI_4l1Q^-NYTx+yGHl5eYJ_KBkULezgrrr3gMd%l19yYhT+p)c'
    'KJIs|xqZiJ7obyDL(7<fFkpzuJArbjSzWClox%kq7v8npo+}RIijQf6i)rf%J6-Y0S)zZ?H-Q9<`a~^Pp>F4bFI$->Y9DnhkAG^M'
    'aP>C})wATd7N^+L)JF_3_NPhF8Dlu**gJ9}dv~k2VBFzL*pM?f0dgqw#eZE~{1BB!wQIRY*SBJDW4J=G>iy8P$mEUc4Tp=&-<uo7'
    '2t2}X9>%%dt`&de4)C`)Z_bPFUh)&;0fG34_<6v9Rd6XoiMRx&JnmZTGzw^g1Vt*<$FOFm&kZI8G#iGmwv7^zEr2eH@Aapr;T+fB'
    '{<>$bUy!D0ECNgIgEQ+A*P&p&0A*E_1>S2fL-+F~<v)jrrythO<@wD#WWy>Z@1nKs&1p;cOguzC-2Y-A%vBb~F+Sb)>Q%SLVQ}I#'
    'P>7sZ8ovZEC9}oh;fqXAjgyB4A(i=Ie`aH8P5t?}EL$>qPOZFfWeU>2Xou<Z4?%73w2}vMzA)~e_peSS_^;=n96r8oa6k<i6KN6q'
    'cuQCOu4YxC*NgZkLDLW-0x`0D|H|9pVIdlkYijwxkTGtuWa>Bzc@^nc#-+yKy%?6|iZ!kC&n><j6rFt*TQBpgIUvPM4+N9Mq5$(0'
    'j^BkjPIm30XW97kMpuU1kZwgsh67_6!m5Z88bpo~(1%|E?MB`2Upz8~y<@~URxrLPgH05eIs`PP;}FVHv12Nbuak|WV*lc>N1dUU'
    ';Uw((^K$ee!H6Q5@pB!Z8SlCV;$WDXD5m|#I3UjTaK+nxc>EG8KbxJpG0TqO&ydCFwjkme))g$YF>Dgu3utiK48RA__x`odx6w&j'
    'x4}jvFIaW(DcsuuTav~?HEj?CR}&HuEx<74*}r)F`Q5jK{jkNItpf{?N}<6x-a*2w*)wpaETZ7!zeZk{*J=Oy;ZM2T3oLKJ?Ze8_'
    '{CEy=Z-4snB+mVKP8SYmvFc%8o6Uef-T8#vh2~U5dJkn421`U+-f)TAfj3&W|NFQ7SHpSd)*EOujVm+{#{&Oo3@8ysqvL_E%&kMo'
    '<YV7+iJV+8e-cdpW+N|S)X&W!-tl^QFqwEl+d*<3`ra6L#rLY)^NEMbh)#3uIP9pyQaEipKPpU^h1r~gR?9$*Mm+1BG4d@Ovpq3w'
    'H`u0M;V#OI(Uo|G*|l;a#<9u7!Y`2ZbP9{xpN6uS!I=zTxEwI~@>2U%A=&161TYA}5Q1upqk_;j1(g?=_|ppW<R<iC3}VRewC8v6'
    'D%EL(R1O^=R*@sOjNVuq6P_VYLB`iX`DuRs{PbzO+xl5e3`q~xhtV`~{}hp+XPP$dKj6O>GXsZI{`6pl;OfH(Tu;n#KhB3`9iI4d'
    '*ywOdTy>eapwak*!=!{JjKSEc283X^s{{`WUF=<Wd$w5}?qF;Vm}vpH<W4@(JltW)hat6Hd?w?C$N6sy{;g)dyz&%dr#nBbXIAcZ'
    'lRBmty)=a^uZ<x{KGkXW%G-@xK7J~5WJ^Tv;8TTncVv^)!HX}4O;kyv`qP)XuJvX)^Kn?4CmSxMcw1^K1KNU1UxXwBOq&877Inzg'
    'DK_LYKYzM^Us7y+>n>jQ)__X-hK3|PWVGXla@GiXW$?My^N4QJ<og!=ra<0EoXEXniaETSvrLe%!?Y6C4-EG?g{G3v)39&N9Z-v*'
    'LTpq>70ee>F0)E>bJN&H!JGtG3A4Pl9``L62=teTc9-9#0cdU5z3W=giy~Lh3plT2<}e723}qMHVA{Fn$|K&>c+(p+-`dB+#EllA'
    '4^h1~l&=TS<IZAwi^sIo*R8uzchDHb{3c&;a!vpq^01DY9E?Uyqmj|8<D2W2#8EzMxV}m;gE%AIH0>l>n{WcGhZw#WL7p851ozry'
    '-?Ewws6u}lAT7@|1jRo5JTN#BdyM<Z!XS*|vFrD(y$OuS^vx+^e^o{=Bh-{Iye0f}HQ?%)hlYZdkGogfBn$xvXjt>m^+KY-gv}&-'
    'L<+<A2>w?LyD>Mox@yHAP44+S<j!6^2K5*#NSs#U^ku=_RKyvTtgfZgGiGLIEP9rHj>pS0Dix}R26jO&iw}5hBj8pCwHYNW?inf3'
    '&@Wf5c(;i<6AT%RlyI&l_N9Q{F!kq@BF$x?1Ih!-_CFp{xv}gnwyIt#iv=~RbPNwmr?nj-gP|HSjVeY?Gkvd${<`H?&BX=_O}zmX'
    '03-q@qDRd?HJnBP6oOS7LCT*t*R6X}G+a)U0D3&#&^KH0$y6j{LtZB|Qfj!EcpcB9D0g1wr!*9Y^Q=eOC{|skQ&^q?O92HCnj(cB'
    'ImFUbV=8I-zP+z{Gy3DWq02z=fnG632R=bqNx6YoQ$=&fNDOG>f809%>;L$F0Iew*E&'
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
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
        # tuple, exactly as shipping_context restores the actual installed S.
        generations=json.loads((root/'.github/package-workflow-generations.json').read_bytes())['generations']
        accepted={'npm-consumers-sync-ci-v1','npm-consumers-sync-ci-budget-v1','npm-consumers-sync-ci-budget-cleanup-v1','android-owned-npm5-sync-ci-v1',
                  'protected-producer-original-default-v1','protected-producer-original-default-boolean-v1',
            'protected-producer-original-default-required-context-v1'}
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
        self.assertEqual(len(manifest['suites']),61)
        self.assertIn('native-owner-lifecycle',manifest['suites'])
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
        installed=[row for row in generations if row['name'] in {
            'protected-producer-original-default-v1','protected-producer-original-default-boolean-v1',
            'protected-producer-original-default-required-context-v1'}]
        if not installed:
            installed=[row for row in generations if row['name']=='protected-producer-seven-target-ci-v1']
        endpoint='.github/workflows/pr-metadata-context.yml'
        approved=[row['workflows'] for row in installed] if endpoint in tree else previous_rows
        matches=[row for row in approved if all(tree.get(path)==entry for path,entry in row.items())]
        self.assertEqual(len(matches),1,'source must match one complete reviewed current or installed tuple')
        if endpoint not in tree:
            previous=matches[0]
            codeql='6d55d0fe4e9edc86204c66e1fa3967681793a2cd'
        else:
            actual=next(row for row in installed if row['workflows']==matches[0])
            codeql={'protected-producer-original-default-v1':'e9aaaed9693efc5ffb4701697ac2a4d51f5f5ba1',
                'protected-producer-original-default-boolean-v1':'3b7a88765b7181a1bc7dd6f48b9b459e590055d3',
                'protected-producer-original-default-required-context-v1':'7b0703d88d404f38c1b3dec92f77f03586c9144c',
                'protected-producer-seven-target-ci-v1':'3a273057a38255ca368d3028594fb94227ba7c3b'}[actual['name']]
        self.assertEqual(tree['.github/workflows/codeql.yml'],dict(mode='100644',type='blob',sha=codeql))
        tree.update(deepcopy(previous));tree.pop(endpoint,None)
        tree['.github/workflows/codeql.yml']=dict(mode='100644',type='blob',
            sha='6d55d0fe4e9edc86204c66e1fa3967681793a2cd')
        return root,registry,raw,tree

    def shipping_context(self):
        """Use the actual complete installed S, not source-only B.

        The native inventory includes the new reusable workflow's membership.
        Its protected certificate must already name S; this fixture never
        rewrites that certificate to make the shipping positive pass.
        """
        root,registry,raw,tree=self.source_context()
        generations=json.loads((root/'.github/package-workflow-generations.json').read_bytes())['generations']
        historical=next(row['workflows'] for row in generations if row['name']=='protected-producer-seven-target-ci-v1')
        self.assertEqual(historical['.github/workflows/repository-checks.yml']['sha'],
            'd9fefd275d9e3c6977cf9350a1945a6bbe5051b4')
        actual=inputs.full_tree(root,'HEAD')
        installed=[row for row in generations if row['name'] in {
            'protected-producer-original-default-v1','protected-producer-original-default-boolean-v1',
            'protected-producer-original-default-required-context-v1'}
            and all(actual.get(path)==entry for path,entry in row['workflows'].items())]
        self.assertEqual(len(installed),1,'installed S must be its actual complete old, Boolean or canonical-result tuple')
        installed=installed[0]
        future=installed['workflows']
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
            prior_callers={'protected-producer-original-default-v1':'81bcf1933edc435826e2de411a777cccd4dec7c7',
                'protected-producer-original-default-boolean-v1':'15d1b9ca9d4b58831cd5f8226efcd47681dd3e8a'}
            if installed['name'] in prior_callers and path=='.github/workflows/repository-checks.yml':
                expected=dict(mode='100644',type='blob',sha=prior_callers[installed['name']])
            else:
                expected=blob((root/template).read_bytes())
            self.assertEqual(future[path],expected,path)
            self.assertEqual(actual.get(path),expected,path)
            tree[path]=dict(expected)
        tree['.github/workflows/codeql.yml']=dict(actual['.github/workflows/codeql.yml'])
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

    def test_source_and_shipping_fixtures_bind_the_actual_deployed_boolean_variant(self):
        root=Path(__file__).resolve().parents[2]
        actual=inputs.full_tree(root,'HEAD')
        generations=json.loads((root/'.github/package-workflow-generations.json').read_bytes())['generations']
        for name,codeql in (
                ('protected-producer-original-default-v1','e9aaaed9693efc5ffb4701697ac2a4d51f5f5ba1'),
                ('protected-producer-original-default-boolean-v1','3b7a88765b7181a1bc7dd6f48b9b459e590055d3'),
                ('protected-producer-original-default-required-context-v1','7b0703d88d404f38c1b3dec92f77f03586c9144c')):
            variant=deepcopy(actual)
            row=next(row['workflows'] for row in generations if row['name']==name)
            variant.update(deepcopy(row))
            variant['.github/workflows/codeql.yml']=dict(mode='100644',type='blob',sha=codeql)
            with self.subTest(name=name),patch.object(inputs,'full_tree',side_effect=lambda *_:deepcopy(variant)):
                _,_,_,before=self.source_context()
                self.assertNotIn('.github/workflows/pr-metadata-context.yml',before)
                self.assertEqual(before['.github/workflows/codeql.yml']['sha'],
                    '6d55d0fe4e9edc86204c66e1fa3967681793a2cd')
                _,_,_,installed=self.shipping_context()
                for path,entry in row.items():self.assertEqual(installed[path],entry)
                self.assertEqual(installed['.github/workflows/codeql.yml'],variant['.github/workflows/codeql.yml'])
            variant['.github/workflows/codeql.yml']['sha']='f'*40
            with self.subTest(name=name,invalid='CodeQL'),patch.object(inputs,'full_tree',side_effect=lambda *_:deepcopy(variant)), \
                    self.assertRaises(AssertionError):self.source_context()
            variant['.github/workflows/codeql.yml']['sha']=codeql
            variant['.github/workflows/browser-client.yml']['sha']='f'*40
            with self.subTest(name=name,invalid='mixed tuple'),patch.object(inputs,'full_tree',side_effect=lambda *_:deepcopy(variant)), \
                    self.assertRaises(AssertionError):self.source_context()

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
        spec=importlib.util.spec_from_file_location('affected_host_policy',root/'tools/repository-checks/host_selection.py')
        host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
        actual_base,actual_candidate=base,candidate
        original_base,original_candidate=deepcopy(base),deepcopy(candidate)
        raw_readers=[inputs.device_reader_digest(tree,native['native_independent_paths'])
                     for tree in (base,candidate)]
        raw_programs=[host.program_digest(tree,root) for tree in (base,candidate)]
        routing=host._ios_routing_views(candidate,base,trusted,root,target)
        # This historical full-subset fixture uses the original reader family,
        # just like the protected finite routing comparison. Actual raw maps
        # and reader identities remain independently preserved below.
        if routing is not None:
            base,candidate=routing['base'],routing['candidate']
        # The installed compiler-data family has a separate complete raw
        # reader certificate; retain the original target certificate as well.
        reader=inputs.device_reader_digest(base,native['native_independent_paths'])
        if inputs.installed_compiler_profile(base,target=target):
            self.assertEqual(target,'apple-ios')
            self.assertEqual(reader,inputs.INSTALLED_COMPILER_READER)
        else:
            self.assertEqual(reader,json.loads(raw)['targets'][target]['reader_digest'])
        plan=inputs.plan_affected(registry,raw,base,candidate,trusted,target=target)
        self.assertIn('device-control-plane-full',plan['omitted'])
        self.assertLess(len(plan['required']),60)
        self.assertIn('attested-runtime',plan['required'])
        self.assertIn('test-evidence',plan['required'])
        self.assertEqual(plan['required_setup'],['host-full'])
        selected=host.select(candidate,plan['paths'],True,trusted_tree=trusted,base_tree=base,target=target)
        self.assertEqual(selected['reason'],'protected-affected-dependencies')
        self.assertEqual(selected['suites'],plan['required'])
        self.assertTrue(selected['full_host'])
        self.assertEqual(selected['include_platform'],base['tests/platform-profile.json']!=inputs._AFFECTED_SHARED_PROFILE)
        self.assertFalse(selected['affected']['reusable'])
        self.assertEqual((actual_base,actual_candidate),(original_base,original_candidate))
        self.assertEqual([inputs.device_reader_digest(tree,native['native_independent_paths'])
                          for tree in (actual_base,actual_candidate)],raw_readers)
        self.assertEqual([host.program_digest(tree,root) for tree in (actual_base,actual_candidate)],raw_programs)
        if routing is not None:
            self.assertNotEqual(original_base,base)
            self.assertNotEqual(original_candidate,candidate)

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
        self.assertIn('native-owner-lifecycle',plan['required'])
        # Apple retains two additional audio Python readers and a changed mute
        # caller. Their genuine import variant must keep this extra owner.
        if 'recorded-voice-qml' in plan['required']:
            self.assertEqual(plan['reasons']['recorded-voice-qml'],'unreviewed-import-or-missing-required-input')
            self.assertEqual(len(plan['required']),34)
        else:
            self.assertIn('recorded-voice-qml',plan['omitted'])
            self.assertEqual(plan['reasons']['recorded-voice-qml'],'unchanged-reviewed-dependencies')
            self.assertEqual(len(plan['required']),33)
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
        # Exercise child routing families even when this test runs on main,
        # whose parent-owned bootstrap does not enter the child comparison.
        variants=[snapshot]
        routing_paths=tuple(ios.ROUTING_DATA)
        for stage_index,stage in enumerate(((0,0),(1,0),(1,1))):
            routing={entry.path:entry for entry in snapshot.entries}
            routing.update({path:ios.Entry(path,'100644','blob',ios.ROUTING_DATA[path][index])
                for path,index in zip(routing_paths,stage)})
            routed=ios.Snapshot(snapshot.revision,snapshot.tree,tuple(
                sorted(routing.values(),key=lambda entry:entry.path)))
            self.assertEqual(ios.routing_data_stage(routed),stage_index)
            variants.append(routed)
        for variant in variants:
            with self.subTest(routing=ios.routing_data_stage(variant)):
                before=ios.Snapshot(variant.revision,variant.tree,tuple(
                    entry for entry in variant.entries if entry.path not in paths))
                self.assertEqual(len(before.entries)+len(paths),len(variant.entries))
                app=ios._boundary(before)
                own_host=host.ci_host_boundary(before)
                self.assertIsNotNone(app)
                self.assertIsNotNone(own_host)
                self.assertEqual(ios._boundary(variant),app)
                self.assertEqual(host.ci_host_boundary(variant),own_host)
                changed=ios.Snapshot(variant.revision,variant.tree,tuple(
                    ios.Entry(entry.path,entry.mode,entry.object_type,'f'*40)
                    if entry.path in paths else entry for entry in variant.entries))
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
