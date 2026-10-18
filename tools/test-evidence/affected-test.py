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
# 852997e1fb1fef6017fb2a54bf4c153564973b29 / tree 9d3a1f20f72c27ef8c0922a9889b45956c535677.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = '6ae69e666f373b953536168e264fbbc587c848fd2265813152e4e5e1ee14eb2c'
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
    'c-qa~+jbmR(jDsi{TO|1H1mA$Q+VvL?=kX7mIR>CI7p&B{O<dUtO7-L6P1|-`taMo)uQBHt1@%NikLCyjQ{bEe||o^e0l9Zbr0jy'
    '@i5*T|9qI9ZeE_chv#{E`sZ)Y$A^FX*Z=X4`{OwM<G=nRO_Hi8{_$V_@%*Lpw^^2?{-;c{W=IGBDM{;jp7MSi$|@O}bWZYlOjG|K'
    'UcNrYe?fnD?EmpU|I4>!dkYO;ZXS<!hvDnWYJH#k@2aM%t&_2vhNi0Pp`VhZPUgJo$7HUnqDz|hS9|P+-@DJ#&7a4o-{-sIpEsW;'
    'zqWfh93P%n7Vql3ZL+ed>$GpuqD_i6&Br1y=dSDXx@(HQN~R)vfAOd3@%VgrIX->88NN)z?`tcTLs4h5=US)DJdW)&P3>G3b5e}0'
    'AKEruo)uGHyuaeh^!#%3{CaqqZpP_xdKjmN;V`YO+b3Byq-E7lqu*RNRi7tw)8s{0_G8}^X`gxFeYIuXwYA2o?AvUP&%}RYmvvn^'
    ')vYh6XxeJ*swyq|)O&q@t+!YC?Bza94=*?WdhPBG^I=%t>Oa5U-@U(j+s{KaH+7cx>0Gu&R?S|jr{331mQ+nqboJ~L-?aME@waJs'
    'xryKYe0f=iCC|FD>xyBRr@HLZqD+f1t-G`xlC&DV^EsQ^EzADrM|E-OChdngZS#B@2j6a!RZ})jMVfZCvos82F-}80{N#D}PnHuI'
    'hP#8O{AoCR`fYmn{qXSo>2nwF`SI)ftNO1WihdZfz9@>i&x&TOhAgeiX)GJReJ-c8u9Ixfs*irT7k+u&Vy^S4=%%{K`(&uIvGFDM'
    'y$`FOvwBYICYh#T*thPnzr5<)&2=*PjMCZf%aXQBvb@gwVrZwP80xtjy0XdBJ*z&wK3rULNQ<hf#<^?zqN)A7uFb2Y^}6$^pR!`?'
    'lX{xxU2Dddd^>!3I^IvW&%^QY@~>{nB1t^iF3qcIXr^ImyE5<Uq|6$zs~pC5Y|?$tdfCB4cRxJ~+|%vT)IA;^K409%=+HXUQ&|<F'
    '=9Cswp0=5TJP6NKS{8+n;;P!ejmP`j;rK8gF0bzlPgRqbRn?^3axGSQmXu;!Q;uVn*j#Oo`R?`OULJ4%`eW`duHXC4lA;*PvUW+7'
    'i6>EZZ8BtTNMB^`DJ1UaZuk1WKv(6(wWnduo36}8(QMA^ULZ;PG*3FW*3e~XGv-B=Z20XFQU2_{etMW*BGTPH9baFj+wstSemFkA'
    '9EQu$CU1wnYXr4&D5t{fZ<}fAT%Ac-l|I3-&pIhfyL%h2<KxAJv!<@nDHTxNDD~LJ)3+0s={#l*!tAOmrn=s|@ae-luf8N^@d>_6'
    'f4y7|K&8W8PhFOmc_Y-vrpk7z`*L&|+i6G>@u6A|w|AYq@a1@a7;c2UKMv1sR0r@=_c|V4ZqGMf+_D!>WLZvKF=kyqP5CSuj$_fb'
    'MbSh|Osg_ph9^^By_@A!#^Jc@UgeUPqf}kx!<da#TX-Kbj9%Q7*R}I3*-7R!of64ba{XprrIVK<<v4U{Gh|gWC#B!sl|xp$8XObp'
    'UfIlLC#}q;^y)qQK0Q55cel%1y10`z>phUMu7<Ie!_GyL&Hb2FWm>n@Tup6V`+l?e>Ydzo57O=NR*vsee)@X*<?tN2%EetJadB01'
    '(e%kQ2qX1Wy3E|7a)mUv!=x@erR#Tf?EOoBtOT=ah{|Osd(pD!v%2>6c6l=9LnC?0Msci)e|r5c9?z9WcekACr*3$;9N3z%XtKJ<'
    'nkt){N>ne)ydK7;t1_Q;RwV5>Wli5+y(Kx-e0TW#<z;iMt?GQ1Q6*hb_DlUU3iD~*h(Gaw#ynB8&2|5QEv=<n9zdzoOzJjI@+xc6'
    'EV3?HmPgWhdr6ZkUb6A(El4{?!S3*fgMIt$5nav#d@Eg_w6prnGsv5|5%>E_@SS^A@|+IhPjdZZd46%OE`KboPos{d`!;W+_USyg'
    'zT3frs+E&<UFL21fm8I-J$;@w-vYCQH|d5^_Ayt!k;%bMi@NlY)bWJWercOb*T1Dxw)%Dz^vBnSv0Di=K9kmmBR%(864*sojs8zr'
    '4MmprRgrY5I-!_;(VjM3Px+)cE8D(m^CF+xu^f_qRt~1V<Yx34N5mQC<byj}?x@>MVQ?tr?^)`?bTKyB)OF+3H@<9DPM7C-S*oGS'
    'kG{9*;g7@9@!{UTczSi0%epLZo<IrmzVFMSaz*rAH5GL=bxognW^VK`|Ja^3-=a-d)LpKss6i$TjAkrUw-PYrWiR)w9C$k_e%*F%'
    '50b#or`uyC6YTrO2Q}8&kO;)Rm({n`&^9iM+@01>b7s3A+uBvPd|v~!B*eb)xveKz$Pjg6(`M-)7b)f<@5XlcMOzz=_X|$4_Q0yS'
    'oAOp758V?e<9#-gX5rgzt1<0o_iU4ozh+m@(;w5rN>#07ZHF>mpdwNLNIb75NnIaVJ~hzLTp;g0wx3OrKzdlTc|Z)~G`B-rb#B})'
    'sT}?RAe&ZRXsXQp;8woNitZ0vzVQ}#*ag6lPq~__9tVh8oAw>Z!0sSzQ#y9V{IPxQPmR2{PR<AiDf>KNt~r52q*Ye<#H+l??664Y'
    '{-gVnAKea56Kwb8(A_<+paV*-qR3pdP1{S`=GnuFoFMHbyJ<f3Qm3)~@Se7$1i8!KhvR>sMO~UY^Rj9%B;+P<Dg`Q3a?G-iZRU#X'
    'O%B=5X_Z!$6Q*qL%31bbmvfO$UFyoo+=FR0d~9RS$JZyI)^PkX!L5hO*_`#pL{ZdvGJ&#9W8PMv>NZM%d1#@z=>TH-;Fcn*yxma3'
    'LYU-hz`m?5Rc3SVp2?stW1hk9(^+_G5?zvCv7Na)+`X;<y-m>!Q#X}eQk31GVWM$Sc5;>>^O%M_Z(0qM^n>5^%l+egxSPIJYnP9I'
    '?b5IEPIU$j5-}^VjK|W;cawl*b#}6{`rz07^7Q)r;wJfh`uem6jXLx4OXs`jr_?vydPhSGC{6m*M>REbF*egjDuNxGi7Y$G(;6n4'
    'wax79>3HaP6@B7_4ZY?>3yaux{hvYV^FO(KTZ}n0&}RW1txNZXf<BSSmT6x~WMQ;rGc?V%4Eyuz67Hs_`@{3|(nGwMjP-4+9}$g?'
    'xtaPArlDD?OzgFpim4frZWMF2{p2slc>BlWTELGBT0PNpZCwn7wrnP}sm~iX_?V<4IL<NIw&p2qxg0umurdcP*ZvqIivoO4DS!)X'
    'GP`p|JyY4tw*2YA<^RWY+l}{!%QuP6hU7#1)0(U*-4Ce5I1im>p8uNzxC#Zs#)9Cy>J~6DNnGN}vM7-1VHzrhec{AIK>|J+lxxDk'
    'wr}bCle9U<81i(=dPTnaFsfD^ps^^+My}zoC)wDyK=_UI;`jZYEk~)=3~q~j9CIjtSr<{@Pp#}(FL&};tEJUuW4&YXQ(-zBpQhX2'
    'T#paa<r*SFt6-+jQB<Squd1QUZ4#Axs~J_PQ@df_h|zt&gZtwj(^8DOf>y4=6fRk3*_`xE-UW;+t&w!b-3S+JRqeILL)&fN!@j68'
    '44!zBJJyNTmnOYBA)WKI>zuU71vH@w3~j%C{f(g|9cQ&;(?zWfN2wbpE)X|Iym1hVMtGNZ=i3)P#g`4wTn*&CYvyLIuPk*68@Y6!'
    'Yp!N)TmUiXME`T|(tnq*m+ugb>_pnrNnHaAsWX{<<G};;6R$gklSs(s>z6-w`-aEY%g@2NO9xbiB%o-t5Os!|tb!7|=kybrTBD`C'
    'Vk6tu&*xH;GnMsec1pfvsk8HtXa1n+pbJ&jkIDW|K*GLoIUI%V=`t47_ioZGx~y)MLC7mhdm1K8ohF?G$3~_xj{VhJ*!Co9&)<59'
    'rgw*IF#0RDfrsCzk0&>~<f@csT(OO>FJF!i+W^h@_!S929p^#)gd#MRwI)gdSkYrr9eZBI6%XTS`V7-isEoINK6Q_eYgyLN<3~XV'
    '%ea#R19Lg{Wv3^sBA-&VfymHZ@nHa#E;nJTN}X0&Ogc9f(OLuz&bn<`A0aXrYNa;Guzl(62|-(TZI=hRWY&zB#>9<OK(`9X!C3aX'
    'j6s2!cicx;Wd-^RrKWe~`TNN|R-A6<&;=CO*$M94FjV=5YUuRKZw?QSuP>jx^}92x>PCit^XDY-2CJ!vF78IJE~->-efj=^cBE7U'
    'tpy+g?w&oCtlW?#{jeLW-%Mi=pT6H%lpeR;OFX)D;HXn2O4HOJ84gnCs~DVKWl3GAJ@kpE_-Z$Rqwj5OjkGg60g*p>ELmU;uF!F8'
    'Q0<ah>$Akv62O`bl$qtSej_(tUQ(*&+l=f~vsXlj4tTE?tEUF(%@M^Dsk?dOl5fyh#L8Rmp?kVNKHa|h_g1o&GIJ2zkvcB$u%Q~F'
    '`~$VNO`WDQnpmnB6~?#j<5YRxoVgO8o}Y&Q)8vu$js0(<lf1u`6Q?8!tR>T2!84_|O*87gq$%!cA?4~Scm|-{`Sol%l;67fz;@mM'
    'gk@Wov)-bwGgQK15L1Oz=U2^9;7`obVf&DL&Im_WZe}5Ip1y8m((ZZl=QCE$t2A)RKvCJ`HXg7{yfw9VH<tcLmRN0|U#;$|e?8od'
    'C;VqC;3~2;h(KA_VgTt;C8HpK_ZbKXj7+;F4}NC)@y(qvyYC*`3J=Axi{~XI4EUOmx+J>6nhY2@RThkgbZU!_Z|tBA^z`;p&!qFq'
    '$bvpqhCSElmZx|*V;bF#T*ElSr^7EqI8U4Q7wqi8opq<_(LHJPUH-}@5xR#(>sm|oVCSNzHa|$IM~zYQY8y9YUw(X7r=&-W_^v~H'
    '`BLpWB(EB{=-nj()#yNutxwGthiwZLfciK6$G5g8c8&53-@XqYe_s5~8clx$rwFAQ$kFvsuXVrRSf11M!~IgpzV?q_y5|*kG}2@x'
    '%-i0ejtw+HhSUL!5df69E*$NLq5lQn*y$?V1Yg(soT3D5XUG7Eb+bUG^VAPXl?_2s%RIPb`uL`v51$uy#DNq<<-6ff5@9H&+=Kd|'
    'Qvt+n=Dukh2Cb_>qU(XdSEv64ds{M{4Q=;k8q+q~YsjyyZ%;L>BAQ^Kr4kVvX&Rx=zu*wO2>~u|XVyQ)0tLxRZ9qc}Sg6V>bwOLE'
    '0Z8kYx)HA2&f6Y7?Yk=V`z@;XmydnGRgIeoM;TE9b*qP3KyB0d>bLl9SIb4Y!nz6Q3OU<-*ojkxqbTu)W5IR%EDxaqV)KWe&pE_j'
    'hIH~QQ!Kf1T*#;p5LSE^F&=~<s-u;+(9WX#=w3D)Gun_MNPQ?7q#@D+F+A_(!_*DX&7qTx>Sxy<-paXt`0=o<M1Um9rMcEQ>3R@*'
    'o+tH)^gsKzaxW}8Dgf}0Zf(bwfPw%YQ4wFOkWlqOT9yB$G)?+CQ(p%>o?NIV$HP+yh|W8kvgxfAu>i8&@Uo5t&$>BtGU$dXZJVKu'
    'e5y?#5LFHnhm$L72-)`RVXcT&r71$PrmU3*3Id9}Jh;r-N+T(Tg0iM1+y1*ZHk$N%6KaNH){93M%85=|H9WF~lnsG8)rCmgpM9LJ'
    'zwTjPLoKFEgCB{ji=tTXADZZg5iJc!FTJlnsl4c)F*wKLpca>9c6Xm{QT4x*Xx+v?Tj|$X)(1@gmc@NG_3*2bqQuu#RCymvabm;i'
    '^0GlWyo|}T<BWE$FVIX9A*xCYS`~L6+7;hSF5u~9<(HQ^B|OW2Ug`C=d0z(1($8gGWhjHRP_?2h*QJW+KM~E0KlxDse@zd8iht^!'
    'UJjH~66J;I^0LAqmz|H8chF#02{}%Z4thmpq{Tt2%x3K(?XrtYE?<ho+~2R#+0v*5H1rXE2OOycpLI+?Zq=l4Z-$bZQ4ILm9s3^('
    'o`@lrzmqPIy)sX*)BwJ<He-bV70SL=HBg@F;$h|YJ@?1^+dtge<9bR1#%$HprK1fTf$^h$!D?m#N$_qjGaUP|{aN$+l&y@@ABT90'
    '>bu96Sba;PmxMS0jU)g|2Y!mh8mca3zDu&le@{kD&u(qev3q<8?aUHk{$oW?@9*d8sU=<`Zd3!s?K@p2{cBi)FiQG6Hjq>7_H8RZ'
    'e^XUIDhj^+@#VmlMMrf=8lSG72GI`k3J5*5gBk-k(OAj*p}TSikB^7f``axW8G@~?n>5u+8#kZGjYqLOlCy~QXu&89UAc23n;rtb'
    'Or^cni?>A(MQdO{h8!XP=(4IGnvU9m)Nt?G!|~4jay+H*XWHZXx1Se*-1pRM1j7n6wZG;Ccs-bW1SxvVjVyoMyPE|tzWqFDxUaPw'
    '5xr21odw-|VXcUK45OiFCX(f%h9tw_RArmDuzUxb-UUj*h;B9uXhAhA3uLRAMkkB*Kg`H`fN5o$-^KqO??C6`eq~7{+eTV}k(dl2'
    '`0vIDfVEJoovtdbu?w_b^Q}vc)AR4TSGULE_3rT3re_aUjivRiKqr-y2aQK5u5;2B=;gRf2u!k*E4T3Z@%8o#e&pTsyaH?LDUOOq'
    'x_|8w&Hl8=B_<%9JbG&xj-9tLCBI-FNYSo$RQDC0krs`pfH;OjTFrB`{l+Mnf{Rd)lT+8^dHQQMv;a&Sn$ZD<m!aFp>Gy|G=a*Wd'
    'q(UZDnBo;q!Mn<<D|hAMe!`4+KK$-)-~R4m;-v~gO=$}`P%AY7GSxb=6q#eA+ckzPS_>h&az7^oqWgL$phb-|9p1ZQe}q&M#9!G_'
    'GFN38-T4xQWMbn{ME=fvLFGM_*B-0g`(b4va168~S<|W|uxO|xJhM>^E~E~U@BF8(B0t~H{c-qx)8X!#=;0`;>pVOk=xel8(h%~8'
    'CTb4Wg3Ny&wk~|G7W>1)xW>LzsfIF4FdI_3bl)fvD8kZM1$LGSu0*IqwfQ_h9)@G_X+He*5~%+IeqN4iq1lnp$s_b0qbv@(fOIlY'
    '56H0^MAlI^`_})PGPU_yQKol6H`P4C8jC))db!9^iExSZM(ber0m}Am<SDFHp0;m-j7cdJHaZGg5M9>;SHtXvB!);P<t^hQ-TXBC'
    'w+2yT#~oipN;QTG83@+)C`2w*>8J0LtYV&U35HHddgTsI`OfC&5sD5~Zophbz>0W%aKsTgF`pk|xV%7WX^PEv{U1kvd%IW~MYXyT'
    'oupNX?p-bd^g&@uBIUQJu!K%ZffKC4^|kwr3$_lwj}Bdn6^;YZ!q&i{WkHtJ4-+iZg+Xz%wjjaG*Z)3kl3wY#LmA@0yRN+Gxebj|'
    '26L#~@G`v=daeJkw&Ws3d#lS=bi!>YC|W(@bkgrHk_lsqCqS4vH5$17GGHjJ1)Oa<X`LsyQwng$t;nKdt@<VclC=!*_wuCO9*V7t'
    'Ex+`5ZU@JIygmIJGK0GfZPx%zeY&HHoef5f_!0&{%5@JPH_6AAA$*L<HQPBnMB^9dqJQPP^>q9A+P`sOF7HXmcliQwp%dUcra<|q'
    'bJs9K(n_xb#_MtOKeVS%x6w;Ycdn&1<{HzI&>~de1<)N>YCz}a6GVLvrpe1-uXR7OMB1^R@7g!ggL!&6++V(?+<_SE^drh%>fpGo'
    'NC2G<9bX41G-mSOvAbqhcb<-J@3a=0y@e#2^c=YwHP7flrC36W5Uscn+yN}$A?Y=HxL?|VS`uq};LR223xo&2Bz=VExv+gROtb7q'
    'EJpk7$7}Ww_CEITG;Vknlbb0I#S_;vUkbP#I|k>3B?2kKSdlXTB!1>zwZ0Fn(Wu5BU-jTOeH?1;RwYbn;Ao>5Vm3<oIeXZVc2P6O'
    'tyQ&GeH;r|b9=hCPAB{F`$^o*m3mP2ioMkbNCwKqSwacG03710nXWrMu=(Q?0N}ivf8F1$km@8e<Ru7*?h}SU>YcC`Q>7s-3HfeQ'
    'Mf>;*wi17K88cw9Qq}s^)50m^N93`HF^I94<Mq@A&fSdF^?M0c=5yy`SwU|C#e{yRp-CYMslqZ4qeKam%V-+DCg>&8bj?PdyZc9)'
    'wCCUlpIZBC#C?AQPgG&?IB18d&t&_vibo5rFOdQ<s(m!mRk8mil<DJ!3ZRIZ18h|5iPt_2{S|$P4v>JUTR=G=^f18wnoXQOkKs-s'
    'c6kr@V<8h6VMjg_0=N+H*N|V3k7hY=9q+E*er$#>-OHPdrh8dEE5Q?nWCurCcUh_pR{?apS&&hk-!KVece6d5eKUDHTStL#zpNkx'
    '2nhhLNx!GYw~Drbb|v-#Nei1Mk0T(JW_u7jkzh}^%dro&q-JUm)w;)(BnkBsZCm=O<z5brP7TissZlgg#Z)zUUiRD1YQ*s2>u@)n'
    '^R{7dLLz^A`LehH+)e9sS?G{a5~@V#a@px80zr`l;`Tw}&<lhNq}?yt(*|QNq!B)PMEK!sD9n=n4`8n%{<Kv=1AH(Hn_se_@xXQO'
    'Wrgvck+2VXX&SwK*nCw%v>Nz%PS`^}Ev&0K%D7*$qo?U#uWK<MnK?ck5ssf1lgCIZIRZIQMYL}@xZ=Lp@JBavcl>;K*o3uI+GMW4'
    'DK2PMm%eOhbs_r?wk&%}H)Ii<myhlU`tckZjfY{{^f5s<0>NGSh`OcTSesS~6+Og$lthGp*{$^9C#B)|O*Or?C-2AGQIlvnv0xRB'
    'ShIFPyi6j)!|$D?6w~<8Jv~n^ZmQ3)-G}b+`O9%-S46u7t{`Mrzq1NQm3WJzT(by<#TW!}6zyNOtJlZ7V|N*9o&$wfz_Sv?=H&yT'
    '6hX|H5ubIU1F1)7Dyr<GdwMzkK0TaivzL=C7;dm)2lYx<%Ek!~MI&?^@~1W@c+X;c{nZ;9$EQH!pQb7PjfYi^pleInNd1EH0?ora'
    'ZNkouSqM&JQ)I4Kw3TbO;~zw$;`YnS%j2fNBqZvaW(%)^SA$?sV0|JaxL<HAxlmQSThr>J8+sm|4v$-|eqF7ewKH#$p;TYes7n5T'
    'u)IQ*-`qh$MXKcdz=qaorg|i4I1s2P$4q9dl2u*zVM<KNH@RGhsLKB813w<`J8^osKK}Olz8tSp-)Tn~gM}M8(Snf^R^r~Eze<?c'
    'OoXx12e)*02&wG`v`(4Q6cbf*FZ@x+K(R*1Fe9}llPWf$<`I#KU$Gxm&2(5Z0tyGav4rKhAY>w>ZP-_F(3r>|m}Sur)H+Q*xS^0U'
    '@t4~ap^5u2B@lcPXBuX!+yZan`yk4Pd)g?ghE?R(Zt280`gX>?Q=DCXb!E7e75aco2s&vrO=ul`dqocKjh@U)b(;LDZN*<v88=w6'
    'N=dx7aI)gzgqe)BIMk3pzF>{F3z?+k&YNGfuX)|xCY+)th@<EjTA~71In3^5-iSD2B{Y%|{qVsJ#jU!*%9=4tgrgbj6&mV;ZnPuX'
    '=*1~h(Q}ZJqCJ#;a5pEG<C8=8f&saztiW<bIFxD>l&o|Dq*rP1x>buD=E6FO!v&`42X}S8KVBa;J}ezuxUBrv-QFo-%?;=pJdwb8'
    'K=2s)-~=|M*KX_c@#PqtatZf&Z!6h0B6|p4r;Pf#2$my4B?3jS0MJ^j5#=yOua4e<ECe4nV9U#AtmnNU;}@DWT7z1tvFdVj)D%s?'
    'WbI9j@A=w|+#Sco&gx_ybs6y~!ik(#4~3*%GypCQv^q7Bws*{3P+5!IAJ|J2L+6)t4&R%u60k!Wn6}~-Rnr`gJP^4|Bf_f+f3jMU'
    'q&oT7#ugFvxSX`%xY~+{1WkH~Fu~8ZMFAdySdMW=RH%rHR_Fo_UAw0<Eb{kbTHjKYwklZjAwm)dC1JQQ2X$9p)~75+#z&oAUw~MZ'
    '-QM~AZ3IUODQuXI1Z<}{!P%Zua~)J$@_WoQRNo+*U!9gb9HVg*XdeB$C$`4;P2FdB|3h#Ur$wj`oPsF~3kPsb8geFHI9Jyn$0dh6'
    'l|wkQuPafJqJ|LzB54}NWTG_wcpwnbc${KN!vK7ouD)SGi}6{j`GxFlNDauU3#;VNe~Sd%aWwto4=DBq9#Dmkte)nN?C5L_ar^Qm'
    'T=y<-hZ%4ZeG1D;7Q-d2wZ5(&rfKxNuwy71uTG85C7C)%bVN8@Cmn<~*ICEDhgr1}ZVCpU4!L)xdyvT{YfX)-@3G}39k<;bnVVf('
    'fLR;IeEF+f5lF2iuba(UOXrK(3E9i_ds*&y(vGdCohY%8<9j!%!eW4Z@E<4oP+8M@>R`w}%=@T5xT8PrHyC_`cL>zQ;HPZL;M9#A'
    '8dJOK*-FQ_l~H2d4Oizue>9P}{t;-}T6&)+!5(S@vd&}dg{7OYhjeE}b<JN|nbdY4*va%)@a3anz1eou;%(iA!Gl>%9Q5*~Iy7|0'
    '&FWtzR2Z1uePmOI<>^dYA5)u>Zx7*$j97!(5*~OMS1jU+Fo=PHgdt1ber!j_4fU9DKarIMbJrx25q~ySNas`pVN`@~9ucv=9`cNx'
    'yadK@d|II#7Llyy;p$K$Z}ZM1dla9iN#2@8WjKcf@B{lelL3b{y&;+%W-*^K7(UA&7QTb#5BoT?&6p}U@|3jw^pUN6yQf6Jl{{xq'
    'F*Bxwa6oy<SgM3+4&O?F&{v|WcbhxnzhX1%-9Z3YsD<d&o$5Le80|``Rq#(t3^P%MC&<))U^5{vT+vPmWg&kFcRjX#WgcdGLrj8`'
    'Dr3h;z&aiT{qT`pyo6ilZIHNDu_)zmv_v(lrBf18`_VNP?jUwSlmwZncs>$)zvU1UP6&<virEu?4OV-`YT=@{8it;Ux2CC56fzwF'
    '+8@nVr&)jJp0`V5b4AF{1)Clb^p0ExJN2Ss?vu8KlGB$A^a*$RYc5F-CNvYUloQ8xMf|4q#(l7ep@@BWv0)m+pInj7GM)~^S%$Se'
    'w|cx|#q(xxu>9xM-nLA#3v-H5-UPbT8Z5&btyfXC61yZCVl0feQy%b1PZHQ4`x9><%4UNW9B+*z%sXgGQDa?#GqIS^;aIfL=w=!X'
    '<qo*woqa7O!scC(!4L7WSOas9Bqi3_W#z#dHVY#=4d>Patc$C6b#9()-H%ilMA?%q=nTX;*L=fFz|kkHbV+Gu81$8<SMTS07UkAW'
    'N%~^kXjD%q%DM*OF&NVHIP|(<P<wVZJJPM6ZYuuS_B}1FZyW&fZuD`9Dc}(1l|*PHQ5UI`pq3}s?rC`Hp1-h#d^o;z>-ul767EbJ'
    '8VZ&j@KYr6uzww~!_*51xC*{(2S4uLc5}uowhssL#$r&Z`EREGMHrBUW<=t=S9qC2Gz-Pn)iK~l*lFXY!d7U+o*<~h`;SR!Eb$Yw'
    'l+e0aiOQ5olDl#I*ruWy-fY*$XC<Fcrh$^<Fa|fKkEKtdNUj4158Y5+UAv=iNXq67F?P-Rf$+4P;$Dq0PKg0&azPSAOhW%$mVEVl'
    'i-*%a>vr#mkLuk_cBmFE!_T0`P<N%G!sd(>u{)}`SK4cLbS^*TQ?H+6SilMt4`sq-H~T8wOIXk#C(kj8H;=|wrP?B~B9yE?yq!}!'
    '=eYfP(|ZfoO&=57X^v~otjW+$s&+tyFgv4l(|-Ek&X(T5);-0n!7>zHdUJ#hGBT|dlm*pj5rDW%vZ;SMu4mVtp1-`lM8dfJJ^`Hy'
    'NNL!$qITt6mNa|Zyof_oP>Kzj55?=|eVsS5eA>@%5p#H5jHF-i7Nl^8%gKq`YXY;VgA6jWHrG&e6T(}4XW&aQhj(1teq=|-{x?aJ'
    'DplCTEq)kRj4;AbiO!WCjX6K=TlkF$<?ygEG_b_S?v_0X(@*yF!ym1tmL`gNQ%#uIb24I(0cqj1gfGdcW^w!V6j4~W?`UHCJ>5hr'
    'UM~6X`Q>FaN(F>MnE(|+$0Hw^BP2k^8sK*y*B|SSpIWZGx0!Rl`}}0ie|N6uFK;FEbF;h5JStP?f<kHpXu*_40)l~~|BPC@gYNv!'
    'R#sDg7X*X_vpRG>>g1u1CMsfnu)wqMS;N>bwx6q)t_M+`3C7ER4s!4F3bQrFNAOzoG^%jML&JlJ%|Qr=G2_ZJZUUw$ePkDFPeMd7'
    'halYMe44~{Q;bW?Vo(W#NM^67iF|UB?P>Js(|kC@0j8&ezTI_S7t-~L#w>WmF@T$)Tp5&J6>|l5LQYUZ1Kvxu`wlYHX&<C~-P76X'
    '?xZ4FtB=XO5HKT(05s-sgn?-zK*hZE92K0cdfm?Zw!xbF_Nj|3@b+{3b*+ycrneL|W2DN=ng}Hj*XAVfT0;Z$XN;+q{WSY`;lF=e'
    'v0@8vkvirA;Oqh}Fhlx)DcZPd@Mp<>bsD;=+PC=W6~t$-={;aoz!{m)AuX~t;Z3R?g$0hs$U!}{xrPuHJM?j9nN{d#&Nbb-mIo=8'
    '(3lxE_G@oiCZ@Nx_#kmn=lWCZcLc(+-?xb~?D_T~tT@mqw5LFR!|2)QkU4013U0nKLAL@*;|`?F&hJs*iPO_IX<!=DQAVvelsleT'
    '>R1HoJes_`XS}1D8r{IKY2OYIO1fp@<aT}lu`x2B(CkEpp`zZqyPZfyoQwezjQxLVI(Km!izH=T3eu;cKj30Ps8hu?fq<;07QA5~'
    'xe*_{FUPsu`5Mk4`nyN4$wG~nMH1T3CMN4fcr>DI5thL`P&R`fjf>Rpd?R{Vy-*n^bY*!Oa8!QQUr}KJ=>Q#Oe(BH-L8)<@GQHr|'
    'wQu>?gG}$`W#wa}W%KKJ#>agL2GcJ}=|MSHps)m~cL=~PA9t_){O4h<I~@~pg9NH92xTmLh+yo-R3?=kvk}mD8d~VhYll1iiPm%<'
    ')+I5wVCuJcP8Cd+GR)UN*Cj9j?m~B_3(g~8h~;(~GZf0~gF9K(2AQPB1fa<<aKnR~lWt6eMHw<SYVqEpB%6zV|2AUvGuLY)wZf2}'
    'mO_fUF(y2NY&hS!FTyAxEWq->mmyC(UQS4YZi2`C^@mh~Pu?VYEfDi6ACBLj^U=hn;(ui{V@wi5)fGsc8ayXT-Kw~LSHB$(i>_kP'
    'c-+o+-RBis=4d@@kq3Kd45dK0CB;RbQVGkw!Vbm|tnB(7ophnt9?IO$Yg2Mq>di4&naiJ$1zF-LHirTxNZ-0@F_XdA_xAejU@aag'
    'h|h1&?1lLWwP6Ly(a{T+ygUz`2_G@tJ(rz1Y)y>I2o-C|n`EtEngU>7Mm2TXSAVUHiQ-+6M*z*qgK8ct-Uu>>Zw5UFnv}$h)ocwG'
    'o&HiMF1`3o7KEY94xDl6II}$DF)hF*b+=^OmK9*3ANl509gCH0!YLg4A&m)0V<;H&u)t4)7v(N>N|nrf``1eKbBpQUjJmjW{=Q~t'
    'GY2&`QVGt7Py$rUjIYFKh$dkHc7_?&Xiw?J^-pN?ia}sZSJl`8!nJ^raJN^_@P-<rQ{l0bSWU^iamBMj;7v`trPpQ}f{ef=MQ6e+'
    'kk%}(B73Aei>}R(E&Zm|T>5PX$0xE4sNd?;u{s6|D5zsza?IYOp2U4G7oh?dA>*iwz+KJQzAgLbDP25Dlh*9YdC=)-8a-iBfX*u?'
    'x<1(U!5q+8oFr^U-eSIPT$&?;ll1qa52ohv@=ND@&;$`G#(fVVg~-DMk5UBIiD?3zQdE!oHn0eJR)$@nI^jm}Y3X7hNC2rtxXz8?'
    'QJ7)}7>b@HTOau{ae0M^O2?=ii@{c4KtYP{W(*zEN3n&HD8$s)RZ+v?7>H>E>c1X`+n3jeHE*?0-MF)$wTR_pTvH6`q>;8Aw&gKm'
    'iaKammA%Hg3$hkZcYU0k48L3?5}}NkV<d%q6k0WeR2^N2`E5)uO17-}^<f}77=^Bl_B6q#LjWAGqf}%~Ow_iX)>Ry4Wl_y`JChu5'
    'Sp4j#da@_DT{j<h1Gy3OdAgWbodq(6;_C?M;H5JfpjJ!>HMT4b)SbWX`{h<C13gVlJaTz}r)EhW-*a=js6Ut2UlptNBEL-!zq2?0'
    'gjEBFac!*l<e8aaghkAOLO+^f5bY2dJ|6-Em(dJO2YFS}^tR|}PI!!r?1PgwA3m>?{bfwm0SBU%!+eN5<N(r-NVOw$k~6T}7&fl{'
    'W?%j`V_GWod0Khuy!RJZM{3vQ5z_@j!}w;G;qC~f6F;d1+l^aTh@6Lu#<l=izV-<ANXK0ex<oSS3{?gG-Q>$lqBvQVAHJ=4Zgp;Y'
    '*_;_QdWh6wG&GFQ^PU3MK#gHL#Bz_d=}+CC-(Pv>8&7E;WSjsl!h(4ji;C6jrs&GZRH_*-kaJ73XA2viIb{V`10V9V<e07uIwu7{'
    'uvb}B6=rx3;rF+)?7eYf-DdMNm7-VcS}gbz_z#>6GkPi+kxo}wb?Twcnx<=u9>>?P6?uL9sq**xpV^8TQaqU!>o~nLGl1vdVns5D'
    'FpXmwv!+)o=F^JLi$(PFrn;1|re;(Yc$r3nu?Q(1PwhS9(jXTZDIGo8y5G9+V<>rzXjoA?YZ?SoppCvp6|O@_k}?4wa!k}9E+X{l'
    '(p8qlw`G@3_^RNWe+|@L&j5Kzw4_iAv`#Xjf~mWJCdj|1RZjS~RTr|$CchZ=a5(z)6dERqn7IxoX6#i2N%juf2y9q+hm{*wj<Vvg'
    '&aJM(AHg5BIE5%HnM^OzAtt}!i|Gh+{Y}$$>!J&f=1puv-4=47)n_jIQme`ASb*VNn!|xTN3l)Ksi>~GHmD)fRU+NnCeHL3wd0z?'
    'wg}+QEeU%iU?JAjIoH0gqL**bar}J6WVvtM1&>uMKdz{I8!Z_eFSd(K#O|;L@_{jntwRhIE-@0capT%=szNE*<z-!jMh?Z~Qaww*'
    'K6odgRUvUSj*l)QB@7#zjmyq=UsoKn%sqr@!`KC6=$;&>VyUeCFX`>6P>FM41sj(;jEe<R_xr^_IRn(S@ndLq5_p6jOA{q(1K9Pn'
    'yRe&;0&e}BP7Rlb=~cOSIirWCL&LzB+P^Ahet+SYOucPPHtvj)LW<pXTNnQA_5SiVREDi#%)X{lPeY5qZ<3(5io7-q7<rM!{FZ9t'
    'dZ!^|x6k(wh>H(c7pDv9XXqVshEA1vz-@?|q{JyGF5-q1VBWg!8~t|u)uu>x0R%9z6fAv2lrgXt6^sZOv~^bPW?T%rSKb(@99f+c'
    'tb@sqE~FS?RGMpl8)<}TOU_NzIIsF)e_Q`}{C%a5xio8C@T}<D(BJe#(|k49)MADO=htYDVr!I$dFv~RD2FB-k_ob1e8g&e_S^vA'
    'aFId^t2)QKF1D`sdiQcz=9FG83yoe1589yRg@6~V)<z3I=5GSy88>U!WShUIx51xtXZdZ)Pk^@2G=(p8K*})+3X{Mr6)t<cxnK~g'
    'X0Xr39en4IylHvkjHEZbco2TMsfHhIAb7w$x8D>fjGmZD3>%j}`yz8zzkB(zf(C@xgC{LVMLHQ>NmfbfQ}J0Jj_ZDj$WE%VapC6y'
    'ytD!;!R+0&BNFBiUZ^}Ti+~-J2N+l?)Cik(zGp$tc=h1o9Ylu<dy%2Ov!m5!cvBbN{=ybX9h}W|*lu1om{hR54FEORFx0xrVNi4('
    '2t+syi(nio$e^gPE!|gJqx3iTqVJ5TF8_3Dh@q-umWQM4OD5EZj)P8p<34rH7~urF^$tE^wm|Z)c#glXWblF^zp~(FfgWOBm7LPN'
    '@>!6vo#0LKf7qH!pZhUOel@MgUW+gklzUX+_@`l|_6|GOg`i19D2gf=r>!N+smXo$w|b`RL1(T*CL*ah1E)5IQwreWM!o?6DywnV'
    'inlm37w<y|EMG+q<}sbu$O@N*<uPTmsQj7fRT_8XW&2h=Wju%H;|4viAwksNeqt8VsX7=v(HCe{P%e|mOkB-fzWH~vE<3G%IrHIu'
    'rv&6uM*8VMEvIS`aM1T@-1@{#&m6Xfk=MrsN_>3`Ld!}=05RKRWltPVe3G2f$yO`qe?*T2k~&9h*?Lo)JT$kJ3{I)JUO5`sl3k9-'
    '(2O?5ptFQqQEu=ZC(CwgxpFd$3?tE}ZiBnF=}5sM_8rG8frTjUZmwcBNr*7gg_b$4Wd>A%4}U$K-tebee`RfcyF!|2gS)5QOs`ng'
    '&<19%Y`p3i$r9y~8isl>-Lvr9q^k4Ck;|W28CKnV>D*NK=YB3EAiNHW7-UhzcyMt%%XY1QcIw||T^}Y{o_vV!Fv)Z{YcqO+`kKac'
    'QF+-wpPjC{_5HAeGa_*pUgl4%U!Vmm9-Vw|8sahy5!QEj(uh>?Nu)8l2U8g0)>o_Cgdg^>X<?69d%q8`jkZS5302F%juxvP5yzmg'
    'InIY-_rmdSuTVo6Yrr#QELe<6WG18_UF|8-2o^v=Ff<ou?G8E3kJ<F8g>{Z;zcZlJQS!wR5|N>*ccwNxw=3-Dpsug1_;`3EL|IG3'
    'lum)U^f5KEhyevl`ENLeyrf4}j5hMR&C$=sR(^j$1#g5ZLDRJ8@;ulXW0*YZn5%|m*Z@q>^lB3zP~e@D2|>ZZ%f@tq7Ghz98PE_%'
    'Hs(qMX&LpaUp+J@?}p{9EX06QziCC+1C?aOtyYwE`t`=qoBbe$;XVq{KzflfUG*D&)}p@ez71r&dHdPlZ2vY7O{DGa!XhC?dlfO('
    '77D^iCNmK-Mi7)EIZMCJhTXEEEkhM4m^ri((5dFBiRu{Ipzf0v!;|@w#CQUHne0Q`+4hn2hDDjlOpJy@63u;x8|_{ivXtDW;*QBz'
    'b=H@6vW$Ox><%mQ2-DG|F^&ExM6-wlY6BeZ$;?jkae|75`?cyDbKVMkJ!;=AzPSbuntQ+nnn$f6k1i8}rX&!CKD1S6%i>Vk4ciue'
    'iOQGQ-cX8o3ah1wwr?Lk!Ci>{wWOO6{gddK%;M8*L)tLbo7Y|>xTmXqdU{$$QD_#fS(viHMi}Z5YS^m;xg%85%+*xE9ys7x(nSrs'
    'V-q_mOf8U^{Xoo{RGbCc&6+ET%B2hl8sCj+=lZ;b?|1OqYh+eiettF?np%W{HJq<7AMpEp_ksM6p@)o)xoHA>7T@vpX#%&wDq1+8'
    'QNko4gLVYNYY$ecTNnUtvt#vrpCB2kAf#|0CSn?y^Jj!Yc_<2+7<WAY6^#m7yXEoF=iBcF#%~`?gq07j%|i%|R_2YzgdRPoghss$'
    'AqS!W7;xCTfpdzvX%;Fl!rbE_v~L4Sh(zDCvL-SE+@Dq-O68ud4#s+K3)|;WIRJIo)F`4gKqLq_ZO~oWS07Upie(H*x_2AfXR*$q'
    'x)*Q!ztoChIt1Ybkx_Sz(VgM;Q$~;Gx*fc+bS{@WW^SQHVBASMNvDjW4V(<UjY@)@O&%TKZWXQhk1cHLeo_dqI?4J8i_`d17a-sl'
    '1Z`mmwAN%0l+#ry`M<CJBgJtsKv_w>p(f$bW6~%f7*RxvOzs~Iq|oue@7#&S@S$yNU|QlrrR|{FmJ4gPd;4fh#M-<8(-@**LNU0u'
    'Nk6oY&7)b3S5bYnfnBjc;P8}%L3$f0v?d;#Fm>^qH@i0z6IyS#jr@wsflr&6$+TMyXk645D_L!7-4?2&@Z@r5@7@Dq&%^Y2U3>|z'
    '_54H4mWA<*;U%W2$>Wh>8AQ;k=M7+Jl?3tA4LpaJ-P(Pj3m+*G)ul#A8-B<^Z<)d*mUX4cE?ocWWZWAf-ll7Anj&bKW)VpwVb(h>'
    '^pj;~6U2?4r3&@uu=}fg+rs8)wU}%(vV9R+8g*k`F4wraCoG|3jIO?K%-gwgAKwPUZgM!s1vUz4&SH#q7H&L!q?2+ABp_X8oVOSP'
    'nss|ObL#0!F9w{X+n84Mw9+B0r7nsY$Ty%F_Ng~Ggajaoan4<bLMySlb{{d^;bF<JTvV&$NA=q4m~A+wNf@1}Ll<k>s)`hMu9xon'
    'u-YGfXD_D=+m0SKDDZHyW>t;CA{_9&8kHB$1w|s_BN~P;2_{gd*KK7BgPeom5JM38-Sfh8&8b3%Ffd1bF|T)w>Dpk$y`c+2&)I9O'
    '6N0#fJFW|YMJ=IM&qb)zdU4U|o}(J6y~<&4)c8@faJvck=?UjC)Zm3!#sn+6BRsCj|H?S8sO17U)T`XNm2HMuZU<9h=ut6J^=K%^'
    '+sJLh_Lq9!*%_-c-<xaCcZbhkd<(DV3-ul|bVbkrfAJNT(N;D30ES5UmO_T=U}T#Zp`j6k;k{Yb=K%X2!U{E#-`n}gaXqZ6IRr_a'
    'W{qaBdd*Y}79)yf(m+uxi+W`A*S%X2#St62hu24+$x;g*kMqhLH+=-%Bxx4%5%MUqwu8Z)3fm(=F3~5=hjH&iF{Ae3XIIG&eJoVJ'
    'GOSmjk{&&7gPs;sIiBZmZf)Y=r)R4u@4qkoU2|i3A$!cAlb9wK68;!z!iZHTkJ1Nyw<O`$Qxn&DZ1#JPECTsH<~UZTgeOTAJ~1>T'
    'N7#$;Y3_WwMXV-aBj_;Y_4`;QjhWBke~fu&;sk}xg7i9vkBbRrYLVbXqK)moM`8=R6cc&)JVV|YJf|_pfG4e|6O>TO-F^b@Vw9<l'
    'uGq&81%*W*GTg=j7b|et5uVK`N<_{kVo9;M|0Kf|yV$5@(0kHPmIqTAYC#yb>;F-vwo$S&9Wb4U_s8xk?IiKLJxl)9N;Dj(mUv%{'
    '3bhkXN5i&)`;2C;ML`momJ<Tw-aYIiVJn1ru80;+rkfS@jnp#ff+JkTNFo$)AII(oAv!E>LgyCg`jkbEc$n8P69}SAn93u-Y{j(U'
    '43XV*;SIO@fb5wxKSV1E(=oi11P2^6a5AML=C(pPCJq;6w>$kk@4y+25V~pTwMH><8d|y*C4Px$&b`Yd4@$YPIU7}N+Ai638+kk~'
    'A>GY(7=B-Iod95<)y7vEvN>-+fePuy>QXet%=tM;FwJ!vS$GOtUQ8mX<ohtm#5pL%?6;mKp@}auI5`v4J*F=1jTR5Feqf8i*dQO^'
    'hy1*P9_TD4F*Oit(cNVO8tME;jH^gPw;MFSe)my1_f_{bw5hKUL=>w7bTwMILAA%awy!EilVUu|h|=o1z3gpmGfD(Gr$IJM*btE1'
    'X@iidO<{@QOjqISoz?wyyE$=bHf;na3@OQ_h6@hUC>9WSnX6WZkG9@a8hrTOuV@jSp7ZmK;#25?LNTV3#&~5+)4nQ$3yC@2xp{eT'
    'c{)|UHx+z5499OfSr4n>6)6p~P7rK~+32f1pfq^Dc}Nv_xti<NU9*eRd-*&aS?H{hLk%*<dtq>5@CM%`Os-IpA>0JNT>cSCy7eIw'
    'Ki$SToN(`mQ4WWPHO$3a9e1mSlvHR4wS@b|himi?84`L3F^4u@detL&JIg!BF?tm|JLo9pBnFj<r;4W{4UeOAo-!Qt1a`hVZ(p|a'
    '9f@``M2hpKm{e5Dfi%su@do#y;Sw%i+DrQz!glDY?YudfE3rRskxkV>K?v%$dalF*Ffv6zQSL_t4kOax*4pc?IzwlM@7Cv%#zd4Z'
    'VW39|p`GbE1_6yBh*SjoXu{SvnfG4Gf8ReL8Q6x?u@Y3z+Dq66f?|kJVnQVCby#NL)&X)ctM=xN-cCO)Sa#HT#zL<a6LIwbgs@<E'
    '@!*0CT*(NZP_dDoc}Jjq8LQJ2`!_Q368-itysFQK#c5!b{o}-xF|D8p5jy^)w}voFzY3Jl8yrG`R#$sB<iDJe=bkPY;6WmZfggQH'
    'q@CE9VXz(t#_$l+G#TQEH+wg-oj4pLu{(X=pxz5}9DDKK&}tT|B!tUSf=!LEH_E~3&MxzVY3`k=04uwQFya&kpibyPcmbpdn~egg'
    'l^ipIKkfL=U0k5{{!nJRY1+7D%K-E>JL;%0TCMp!tgeXy!_8&hdr+djbv$Ac<=SKhn(+~NNyM1Kd^9Fy@Vk$(Z!9;ZBxZ<X<~4f}'
    'kTc8n_AGr3_n(#025H;3*n~e8gt7<%BF;)0gSlY<Oq8Ql-0s}QS;hahn^l629zu$@Ru;iG3_gZCg<*mWrK7IaC<JW7)ARk?;Gi4&'
    'Zu#M<&bl172-~psVwNQ8Yk0F`&{Q$N-kHT-g3md$)!xH-;vqjyE1{t`hF!NWOtBL4wZu(aVD?XS+;ZLp_)cGTEUsF88w<J#z|@4;'
    'Ox_VriYzl~u|UrpI;jh4e~lD=?|WEm%T5+0TcGS9=gdAt&Odx-%&e2Kx3MX;UKUe7(a(dnv9^nS5vdOgV3QOkZ@7!O%2dHrlm*U='
    '>HvvNX^XG2w(2+UjBl6JdA`uf$fGXU_C)<`qdHwBy(}&16h9>-VZ`@C+}-`=)i=1rIoudQIFz+P%b>k@@gy{!K2mtaMnhsXPpj;l'
    'zs*9nM?Z5lD^!PsmA)jYcD!W%rA9YKD?gen_}KNdYV&&zGw<EIKX^x&@CUXTQSZ!s$=t96U_(rZ*HorsrA*g-u9|HtZVqg05IJFM'
    'is{4fI&#^JeDI9QP;j~Ihak@iyQ@ERIm6p>z#N_1h?b@(%)o6Co#}y=DIC6E<TJzJ!o;oJv|_}pZAt<Hcf2yUNDoVwZA$toD=~<T'
    '5mDF-nf6P$Dn|Zp*)5U60GKKK9;+DSqdwsgY)EQ+)({|)cZ?dS$EwxjcdOzgM<05H{_Ilhf;^vwrKF*4J}0^-F(Qe%Fszl#?pdu_'
    'zgu<V4MCHV7CeQz@X69)CJQLR!IbrE){QuTW*D)uiVOe8!W(8d;p(!N;UqgWF=@5J9zx0JAO)pDx$y>Q`vC~=Eq$uRZ@y31Z(i2s'
    '&C82rK{29}Q3d2Ei<#VTtRb!eKHTDTsjK|%ji{!ak5Bi}Gb9V??!Nx_75x#Iz#MsnTq5%8R>oj^lde%6(g+%h^IP@4mF@TIomrEC'
    'fUKGLa}5oZ2_OFkn9XxfRFL~hLnO((g`?h{xw7q8_Kf$huN@spa~Y>NI&_5EFJaqXn$66iY@T4vcHzU?yY?Hny<rP*4m@!*JXMgs'
    'S6HN)q#14r1ldyvGp3kS{q9$->UoJh+$axcV`=~S+w<|^!Y_t@;^Sf(#c&dWzBYX3i5P=+2Kb^Qobg28&2g;q8&by2(&mJ+{rofj'
    '{_aWUP*Y)78E6GkDwaFJ<P8JsP^_rk@_<O+=j6v6(DQWd=bIS5`OlZXUM|fT%36q-7Vqc@5+f+NrPEcI8S)3CD-t=f_oZw?;LY2Q'
    '{J9|G2SW&nnrX~lT?|whV_=V{R03zX+KEvl2LVSUmsSftb^P7Ug0-)7rD(;GJlIXE7j!DkKt$V9IcO7>xb83pF7fZyP0#YG8+?xF'
    'Eu0Hie{y^NliP2m1((y8G6oo<w6MSAC1N}qj)NJDa+lybfMD=({ImBq@$L6MMPK%5JrGh?s|Xsvc^U#A$qL^*!u`Tf3pINeW>g03'
    '{p<^hmg}d!``vf??LV#r-EfpQJXQsu8tRBJN%m`uCN3C*$e)G~w=FiTbsDbu^8X$G-|23N2mh^m`Lcq+x>)h^CEN<3z+(G2m1DOI'
    '#0!Aj+pd3Jke*i8BpJTkoY@(~h{wlu`6UZNJQ0f82nrcO!VuH1_(hBNrg0D=QojC_{Q0vr&wpKE)QRme(9Yy0gXRP1rb080F`~UG'
    'mNd4&n4ji_-!FN}@;@yMx|QkMrl#V|x!|(!IU;WCBrT|7v`XP`LXd)UI&NEUlmuV?VDsg4s1$j%p{Hrz^8}>frt>5l<J+GE_2Z|M'
    'w4bc^`PCf7mFJnaU35j^jjl_XAQ>9gneHEn1(OT00e80DwjP7Dm$jjzRg6kv_~!>1ZH}|-`No(I1*A+ctZQQ+?C|c991b@pql4#9'
    'Uk)>KbGY4UZrkH=B^q#oBT40}$TpTr8Ri{+a6%GH9;S$?EGR)MHY^=$t#cxbwl@=wad-HGvg+Wl2$Uhs)x65PP%tq|Eq|(?`i}*l'
    '79e@e7(2v;1M+baz9r0*sd3S8iD8+;D%`MQ6VjGs+OXp5<0>;>X_zCR13lZIx@gOZ>qWHoZGwjaTQZeY)4jLaIEBGBdh=HauG9Y<'
    'Ze6QqvIzGtG6<=UnW%u3%H8Q+LG>;}YEA*{&8E9nH8$a}QZx18%B~|pGHOY;h7vpv8;zLFgx6t`T$v`*u4Pv*upwmp`c_EQQ*c*`'
    '$Q6)kSP1}H>tM#k)Q)t|qNiH?@@+zG6tI7|`5F%4z~Zo|7$Iqd#}Z$>RejFny=C!+ZkFS5^RHJh$9y;qXx{L0rSoW*+`0k1;e`^;'
    'sQ4PxE-J=wt_+>S@cvVNZ{;mC5yAzoHX?#J%W@Algz<|sFnm%%@xpeQdsVjkSASUxOzf)U4x#4gLt0sBW=oZbZm9gRQVV~MCefFB'
    '7v3<p)*X%8fH;U?i&DrwA_T%nr+NyW|Cs1<Ys|eHjx|GHryB$q*~?<z`1sPT$rVb3XJ3#z)vrd<%ECdwr|p5e!AmY^Nq8T(o7P;v'
    '<FpIVsf*69VGkDW$%@06L8+uL1<ovc7m!?d({fv`IFKtorU@>lt<UUq#Vcot{z2aa642`t)m(*|jSIf4WuB;g)UiDNsd2*9-z-$m'
    'lH*#OVoy^aF~Hb&lcF=maLTba<V5!FR&l|&!{@LeXKn)IQ09yOJ{J5Cl}52?xkuNxVsK@+LbmAr(6q?pjp_}Di^SiX8^s7b!fzVJ'
    'xy_~(f94MGL!39~rSS{Uu#E=<;v?dx0RtAnr3@wF9GG&yX|dBNpcN7nsZ<-onwdUVm=w@#7{1yTbAqOf5En<SdiOM(<NDiQx6Jhm'
    '(lm`lV5x0zW?kYs6s#AZtctS0d+nub-d|GwbBK6)vwSYkZ{{H@RxxQ4t!-~kTf%4JA^PF|7Xx7|k}!_(>DIefT_1-5ERZ^*4w<>-'
    'Mun5WX#ik`n=}#nJZp(Wk?dbuQ-3_p^O}rakmZFdQ;_~eJ4~Oy3u=3#mE4i@g>nD5eRVRyKc9ng`1rcQ0ri7LTEsry(gnY(QB~;m'
    'BK}Fx0(}5@<iqxr*TVxI(wt803zi9U7$z_(K`-XW(hU=K%keR@%N=W4=U<mYE@4$2T4B=wAaWS;EnKAyKjMhII&x}$XwI~E(X(uP'
    'rS>isr+CPtvUHgk6}~ha&c{fP0s6Q|0IVJFH!_BeW5fz6LpXYHC>+AeI($7P!LUCKS3D>BvyMq}zI}1nqt4JvcM^8}wW1V{nQgj2'
    'eN1{b=?3Df|Ibq%2f;`e33D5y=N(_z!{dFd{A_mW$}BsEKV1@|+k%K^SXZ#n`mjlKFQCC`GXNiCP}|o&-$o~C-3l8~A|3|8fqJtX'
    'rJ!>G>zNE)82aNSy8nq0cf`>6^V@F;`(cecTLu;&l|qAYyn}>UvS;8-nMJ|Je~r8@Eq8qJ;ZHf=2`q2H?Pg(VemaM^w?F-K66bz8'
    'rwfO(SoN^2&1S%#?)-$@h31q+dJkn426IGP-f$DQ18=mf|JQH(?}qcntyj=y8dqo@js^ZvA5bEUM#lqRS$I=2xx}`dw37?wJHhk^'
    '8+id#KR1PV$Lr<6Wa0^J2g!Npdt=}g->YWJCmt#zI?biyu%Ql{!fD(2QDMR?%;xO0S~}l5@vL*k$TxG$+6@bD2HV6ecTr-DuEZ<M'
    'u9Xupj!h;Oeu1o~r?9wvw-$*RoRa|zmjfnWUTVK0B-<_ufI$d`5L9a%6@<1SsJy_$cPq@3o6t=k#E|Z3%kSb<s?!Lmg!gwrZ<kv}'
    'Z>)|9&yc4e<LjWjo1Z^FeeQ49epVGj(u4J3G!0jLQ9y#8XxeZM0{&|;GjN#lcMnzwu5M1?`otXf(|DMd;fXJYl@6!GRhNki8jVjl'
    'OiF0N7>u22KnRArO7OtY+17>ElR5n-0_qk9vEcX!d07@1kiLcy&_m3Z4bO<J3;s|uU#>%j7(3ngX)UvI+z)b&DMl|1A<L^{2$D~A'
    'sJ5=W3jZ+J01uMmBDe$atW(e=mWv0Q$~7V1HLtvTH^?t*y;;tD>Xzooic2ZpmfFgIw&2odA;|#KPJs@KI$Bf|8~m5v|5$%qQfz(e'
    'E?#a7wFTP4!T<oaFVolIFS(!VWT+2(Qz7fxw&*tn^5s)W(wW2*b9gsrnIK_@X{F_X;XKGfQ_1J4+qUKgsAZ7lH{sRDJ){bYLb_Gv'
    's7To1z^3B|ikCso+ZGH2`aYuF+F6O}m3@^7uk_`CM;HbZ5>lf*^LdICC7(C`$P<rvOXE#%(0pqj4-+?9gf>L=+EBh8K#x0%=`9}9'
    'T<%+UWpIKNJmxp~g8i%t;K7lkp(dvhp{CKuXw~u6z9n&#4=cucS%{SMr2*0*>I!@!jh0QjoF8||GTC<LvTs?<>hxTd2ELmm#9%=;'
    '=;De?wgNa1DUJ`DtY+KVtH21^w>d@Zukz?+gqjkDH;13D23#5Q&`{9Qe)DRpgdqTdLOl&#FC^L#sRr32QW(BR@V{c%jk&?at`&ba'
    'x#vg7oxOMr>M>Rj>YC&9CBfY^UDT*#R69C7V`kEAi#|&~`{U&ql^{Dq1Dl|i#Rt5!5xm8qHhX<>&q#^7cHXt(?JDZ5P&XQB!nqpQ'
    'm*P%`sXwO_X)X&LP###e{rQl}m1Q@vRrONA+Uis37#@~RYu!Z#Lp5X?Rg9cw`d+->vHtn;i{@g5g{IyB@c|NfJw}fj_#RH9TIPaP'
    '9YM;UR{PdHDH<*(N&r2cZfSt)h9q$kK)Pe-mr8S^?_0+6$llM;{%zqU4aMO+>ycIjE-{Iccq6n=1{nFc!CgQJX%ps@nNTkHZtJsN'
    'js7utLxutmh6-q|YOKgu$Y{D4RUzfA7cJp`e9-^%|M~v`yoMlh'
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
                  'protected-producer-original-default-v1','protected-producer-original-default-boolean-v1'}
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
        installed=[row for row in generations if row['name'] in {
            'protected-producer-original-default-v1','protected-producer-original-default-boolean-v1'}]
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
            'protected-producer-original-default-v1','protected-producer-original-default-boolean-v1'}
            and all(actual.get(path)==entry for path,entry in row['workflows'].items())]
        self.assertEqual(len(installed),1,'installed S must be its actual complete old or Boolean tuple')
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
            if (installed['name']=='protected-producer-original-default-v1'
                    and path=='.github/workflows/repository-checks.yml'):
                expected=dict(mode='100644',type='blob',sha='81bcf1933edc435826e2de411a777cccd4dec7c7')
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
                ('protected-producer-original-default-boolean-v1','3b7a88765b7181a1bc7dd6f48b9b459e590055d3')):
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
