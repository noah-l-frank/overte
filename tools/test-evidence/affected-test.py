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
# 13f2ea1a5f1476174c802a2bb6a397ca2578f46b / tree e185cdb16c754f5a92b20facd0938d37b7dc998d.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = '450a83fba39dc13e90580c3a0c04198c2ec9618634df673a0d87b49342499784'
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
    (
    (
    (
    (
    (
    (
    (
    (
    'c-qa~+makdvL)E}`HXsQ9QggxUokQ=?<syU2ZBswWaWiLc1!>JEcJ*4fhr)}BN9C`NBSI+D0Z2JySbX`*1fm>&wu>ar^CzV*YV@<'
    'Fh3m+^M~WV9@5i?m#5+3c}Y+I_1p9D;UE9~fBxgkaZdmE@BhfNtf{Jh{I`ERe;)i}QDnLQsq><n^2y(2dAlsB9OtQSvZ>3LtX$?i'
    '_y6JLugCZ=81IkcKmON$`?~CCq3QF7$K(BB`fFpgaV-6JHL2;_Y#!3oHElbMDa+byDVuT5mbR&eto!+DkHhr)@F{)x*YWB1<^K4u'
    '51*1>JG>l@56>Hm&%K3*xyYA1jcwO<O|$sDSv3}Q-IQHfrJ`)}=I4t)rN`s*;pO=B*N5qInttC}v7V~7SUlG@@0NM)Q%e0(S4&pS'
    'y&u|lLs?X5tbV@YOL~6!@cepsNgw9)m>%ZzFdfp?y5*92tJBoi`B3(Ck&ks&ElrsZ<2V-O(DYN@6-%*a-L19SaT@cnZ`;0^t2%Xy'
    'Rj0n}vZ=_2!SYSs*IhmSe66=v`RwIBrH7Xf|9l<p56fX%-|Bz;_2vHOtM^?ycS|<seV3}N$o)bmsVur?sI6Kge>dfAwQKdK<8Ntt'
    '`4GST`SP+pma-V?VW_5QNo_smRh?IJ-VS*`WqC7u=Sz|LJ<I;*p}M?uv7~Hn=CYsjB3rsF%lbYqo4K9+_`2w_xy#1t2OsSCWI2&x'
    'x<7czAE(2|-_pbHhll5npN4qPkAMAqRS$Nm#%U_Xs;b(tsJglFg4;UHb?3J)b;{c|E3R4f(J%MHFRxoIZJDYewOu)8Q(O3POE-@5'
    '(2PsbE?L`UDNWOL>mJ9;t1iRRW>Z<U`QrB#SwCbVLpfGcpSo&lmth*}uDt3QKfOL&Tyx5+rfKG7=*OyS{k)+so2>8hu}otss(H-X'
    'v@BPx87KK}`uueKlJ1_T<KyLD-PKi=d9s7k)J$EPQa{w?&}I&m*i}z+KX>_c&wAa#!|)|N3*71MDGiT@hff!`F?Ut9OiikrO4Lkw'
    'mCC#?s%n_VCTsG#s+zoVRb9W0$1iu&@nJb!Uf(yIny##yrpt%*T5QT9tH);O>Uk~%(n-vz%B$CpdwIV5^N(e`xc=yzWmPrTb?cI-'
    'Gf$!(dg0U!=|q;ELgs!Ru3p~>bX8tlJ55X34RtY#W=koww^KgmWj46ArlH8YxvZLO$8V2_@~`2qj}Pf3BHi87@%1I$&4=OB!}0m$'
    'FkOx|Wj~FBfS%V=ohq+ibWek;Gpn205uC?jkh1hwZ{u}-ytr`DwN0M#Vot3Oe(vMx+leb=nF}AnGCGN=ZFetxI(X;R*TgK2;7j`R'
    '<#GV3ee7)-in5lMlqoh<_o*H0+1J>oDbK`*W;@*85Awp7<CnwqLD>7_@a#tQ0e&1_=flh0`NoS|_Tm>=*J-HcVi;4BTJ*y_SAAbq'
    'UBtw^spDmMGVRT~S-;BoIPQm6x#Z<2)i&ic7jx5B-bXVJqqy03MZYX_TV^u4lu5R-+c)znoxB_==V{2hsc2*#wckF}Q_;E_d?wPp'
    'x?AdDuF4|iH}B#1^z@MK@7A|;aVLE-dLVP#OmjPy?IH(S#<^(fTt2omNnYms7R${$`7%66x92-KzN7r~*WKsCbL1))ca_D()htyv'
    'W@!>e+ElyD+@f-YytKottvsdMcXb^7OMh$xvu29QWvWNfQjXuYPVZ1=b2)Woa)QLMCjQggcky_xJcj%At9}}$m&<{zo2#y9D@kdw'
    'NKyN&uFH0syP+u@>!Ql~S;ji{H*ZN!wcH;*eSX;;Yn!%QWK`Ku)uXE=`Ofn$S01G{9?)E7YPO{v-?62wbjt&%m6}=Gms!~qU0y`i'
    'CCl<idT%f5%C0Mm`Q|N1J7&S|@P`lk?&~AEoCP>5YKeYPzj+3wa#7qL8^L!ORgFtNi9gxxkLCHrcXj!&^o~XwOONWQX>tiIy>mNx'
    'P_1&ZZEMBdJHDcq;ptP_eG4oS-fWm=*~ij2Bgu!IS8eT(wDE)*`9Yth+uzbDTYb9<#^dY5JZuCS$E0^~q~~5s2D=y<rBPEiQ>Ex_'
    's%*&B303+<d)je5m1$A$_G8nRRhjy^p0aUK4(3jBH#^1=ai%4E=Z@Ap>TXvUoND=dk-IQmj9rn2VNPS`WUF$9vMlR*T%=j=d~fOD'
    'kHgdP;fsIq^y)5`bw%JjJ)Eh8NYqo~iWr9`Rc(`oZY(@AH~L(@Z%?~#(Qc^Pp;T40&6qkE&0MK&C1A?SQSRIL;O(gTb=$c+NCH2d'
    'ZjX&ja2z`aYHo`u6NpDIYwVk;?_3t8J8eu$VY~0!+D*6o*aEa9#LoEAw@DT<MV;97MLx+zs--H2xu1T~)~4f^6(`wxV9he5vX{tL'
    'eJ)VO`|Kpm!nfTvb3QKa*{+;_&90u)AL(JEs#dc0Qyni*5h(y<o>!OUu8*Qj9W=BQ$cOjsXICVU9#(xB5W}37e(IaSjXPwGkADKl'
    '=8YGcD|6qum2a}5FNZy6yoWIl0Wg%QRCBfS1X1hraR3?E9i%Pg^H44C+t>A}k@q&p8Q~!HSO(0sWN?VQDJn-CU|iT?l`Z3Y_a#5N'
    'o1PME_vJ9$KX0G|O0KFZT(n(3O52vj!-||BA0@kaIl%x`uJ7K{o|K?;`8zoN2U;}ba8`v^1=5GylwG4h&4+d_iuY~ihU`raIWBpV'
    'H;pe$**w&X?7yv-Do;ZmAh>%lFQ)fx?D_cm1k{?2pA+1Ax}42fZ_X4&gC`RxTbctJFRMOE0HFEop-mvBcWx=N%DWvUEQCqE2J9=^'
    'T4lD3?wJDWGM7c2;GV)$mvwpdE4H%?hx^wJptq~KDGjL}vZ@{?4U<-Gt5K1r!eg4svg<Wa@^_x=moJaY;XZw>)-HektxLZt2h|xk'
    'NW^TwG9Jq)-^~J&)!8ZP=AEbe<>~eL#ZB^i`s-;68uiV~FMZ$Dm~v;j_l~q%<hf(+P-(tYbC=#z5nQpE$g;CCZ(*WEukDit9S<F^'
    'YRr6L(^!>t4~y7${hvYV^M7*rwwOz3pko0YZEN?1f<BYU*1B90Sr~2IO<lJy!~XQThP(9i<?#Hx_7E>7V`JazM?|Az>C!mEG&D<<'
    'iDNaiRqCc}n8loZKl$@9-v05p74YMNR!?+8-&RwlEn5g}(Y|zp&sjc$<9sIj);y&xmqVuxR^h`dwLj*_q5$712XKK+7I)5^m-aC4'
    '%by-x{(q#qVg7Qse3R&GNIt~Bd@Pzq_X8?1FVmp2<^Pocu1dkMvmiLHx(7_mGMBirEDEG{N>ih-uYB=PkbsXS<(e?C?<{@$CGE~J'
    'rZP{(sK{3zM%AhVq>ZX|sj1nOSuu}25PoO9_-(&u&!^PRYKy9z=Mu_aw^bDQsh2&MK4r&REv+`2+bb476{geiDc$|%dVENiYlsM~'
    'f|))?rG4BsO$%l2v#8vA&8SA5I!wz>jPBbVd^!G+)?(BZv~d;YaLHC%H5<Ef2pCsdBk7F05iZuN+FOl>e%QZ<>!QjudE!~=v(B`>'
    'N{uf4<VCZ7@TDaeP(l@$`f>mIJ3~u8FKWkbh*}$t(ssVMK-_%doe#0<gm-y&xqsnPeA)5L)j;06W^Up7Dso?8Czl>e%~kvakG%z*'
    '=zm_j^xq}y<vT<pJCpVdQrEyj+CpaEdGG-J%<IOEP!sK}IDT9~pSpe1<Ll+;;JeGGuJEVcI$DT2!%fyeiQRMh30<qv(%-O=ee0JC'
    'ib$Tz`ZPNwU$WH2_fQu8pc|kIO)<{d^+!O$zH&Ky3d7T7ENC3vq(yXD-71riSJ(D5rJ{BSli=9NH0F7{c?<iVMC<umFVplMkPT*k'
    '#WwKp2la7svrDdOdBzRf`0M5K@nIjJ8HZny0Mzk4sGm@TQr&8zRDcydCe^X$Ro(C~p3*0njzVR=``6R(__&p2O=G6~T^tIbATThO'
    '<5&-R!YcBVs|`ek;f8|&Si0PVZ5nl2V=?L6Tt#aUG`Q%t6=Q_RV5rsFB-8$-_a_8>JM=>t<dQ`*BF&i_se*1*l7qP(bs2*Kvs`f>'
    '-INvRFVvdejpy$tk63ZKozoCd;9w`XbJK**wOtLJe))&P!{h7AM{oW9%&Phz!~gKFB=H8TsfaG_Mz1caRBwGff0N8!sR&vNKm^>q'
    'cq~P|BTM>jH&*|U<{&<OyRj%e?uM6mblbquph}dcsX+=Hq`|3}e7(w&wo-fO6Q?+}JHXMOZETCQv-kocfAUz0z#3ekGd`N?qt*JX'
    'N8~X5yd9L8^|F2=H(p*+s^)A)cB<JcB18v#RExE#!)o-2;)%4wvUABdXe?soo%b+2eK|hez54eyvX;8=A-E%TT;O3-Ge!9aYQ@OQ'
    '^94;TSBwhdd-rjwJU^Vd5+9$RrvI<WBikGMe~nJ^^R1jXB~f6lndSzbDZTAFyg{!B_q3974Gla4Q11KnYzCCywtL5R-T;JkTbHxm'
    'YHSNsLM&AsjVkgGHAjU%u}FvQL-M&G9NoB?mBe{E-N>ZF^X}s_H@;VCU@AaSMRFTYSSH?@+IyI5e<Vw6cF?aj_cgvA?&lN!vlnm`'
    '**Zj^VnE={^r*5~5NO*r5D*xdc1s!j%>4bEJ7ad=JhlxUiq9^dmyj^wYeMR>=mu*tVB|DKFdp*MSMT50K^y4l?WLYc=a-QMeX0U`'
    'uG1~g@p9%ox*es4ae+^VUx;v?cl|He*@HXlUejZE((1c>%902@!lHGprFyV)(Nmirq%@+&sCl)Gk*4eS@9LEFh!Nj(XfI!?<ACJV'
    '0vElzOrV;5kaO>-IdRywPywiaH@<&s*Tk+_p5g2}`1teUchPD3BREAU)j*D}hk9-J1)t?PT|azTE7{la@$>M!!H!0nY=n8+o7Ay^'
    'CdiNmfH4Aq64!;J{V<Kc;EbKF!d>untIsJ)z;>nrfY^2`WV)nr%9>&dl3L-xW$FE!dOmzw*%1d)5S8zakFo|Vx(pS40PPBh+bv_)'
    '`53gWCW)>G247A88}_zlIy>6#U7{(7_8RhQ@9e3DRYde7sa7IlBc&Po{0lyUHzB~~?JWAoSfC(TsSRkT0}C}pqb{KF2tZoD)QxcC'
    'cHZ{z@w%&0zd!UdHZ+d`S9NYC9A!ia)U6R}0kzHBo8RKsU9A`82J0rEE97kV;UG>`K1GQ)91E^X@e)D>#O8NDpL2-64C$0bp;&U|'
    'xR6mHAguT-Vmt^zR7WfCp`BIz-o5Pj%nFQ}AoZbSv`|L8U7hw(K1|&J-JAy5sD5_)?ya2bhwneOjR=rMxwN!8C&LJ0FUzc*k^UF|'
    'R_TRBM+E@>-mP7+C7>X{M^wbusw7lnkXGe?c|pfChh{9`@$5o1IUk-vKy=<&D$-jkVg+P}>17)WUUYMoY|;%?+ICYP`Ba}lAes^;'
    '4kuUE3~hPM9=3{DRhlBC=;~H^pdg^gD}&3dtu&KjC@9;U7I63P-q~o<@6D(gszomzU8p2F>DBPa7E(3@>RcBh?|*bSU4O&FvV~ft'
    'LW3WPYlxy)?;o1zhY>ANr^#{9sTwc(M-0ySIH|>DnZy0ZJ5>E|BwBazpKbK(Eb9Q5n7(nJr4fErQ<OMeRa1_^6ffH$U0yaQhnF##'
    'eqPYd^#!^l5u&QZpjB~?p<QuiN&!zVtGv9-DdAcFexujhmt!3;%ed5SQ=kmeLbZyvQkN>Ce<GThfAFIM{z?ylihmrQUJjH~66KZY'
    '^0L7pmz~d;chF#02{}%dPkKdlq{Tt2EEeq|?XrtYt|vue?w>d5Y<biI8u|#o6OL4d&pKxyw<amvyQ!vc6a#*A$NtBHCt}Fub20?7'
    'SC<)<8o;;JW^53kocOX=4b-Q)c-r`V&*SmS-5+l4c{`;6WA<w5+NTX1f$^h$!D^NP(HhH8W;l-|vOoCDPua?x{y4;2RNp<m#Oiwz'
    'y)48DXe0qx`ruP6)=_mS^Iei7{(ClSdJbEQ&cowNXlK?4^B*gEdVfDxPc8EraicmY?l|Z&>0iSVgweLm=MHj;-M(+d=dY^jM@7Nc'
    'KfWB;is-0LS?B2LX%OuouYk~VJ7_V0GmVvUoQ4~B@c4Lm{c^WwBU7-ob(2!NwsFfuZaj<Sk(@=WM+-(_80srGvg;w>%QV_+qj*~d'
    'QM3gH6vz?skD+MBsT-&rNDZ%Ddph2`Uyi2~{!Dw^KKo@A$o)vo){j1IH%y^<0bUO#A3=&9b0^E6uiecG7~g$L8tz*yM?^0aW8Z>q'
    'zOYtBK8Ddyb*WkUs)Z!O;8bP1x3HdrUGD;=U`97v1hk-<)fKYULZeee`yXcHJ;1bz-S6W6AMZft;>*U8NVc7{0wXaauk}0U2!O3n'
    'tDUYYZm|orUdz2p&guDg-K)Ff^m>2zbJw#6tH#p$R-ltc%7ezE6xTWFEA(<)CIlwg$&Fk1^!R%B89(wqJ#WC8dWy5+k<o*8iDrLZ'
    'l@b$>P8q$m0>{qVNZBvg2U4`_9o2n<XQV|VDj<&GkT%N_ZNE86rr;t}<mA*fWtsn)4Xpsvj%IX#;dSUXO8Wh2*7>EDsHu=i6;iyy'
    '6uhglxp7x6?kCKM=fm&*@$H{3CSIx_)RexG12J+~fK089EJfzr>2}Q_i`GIYZrslaff)X}7to?cN{63avEM_g8RD<(C|erN8M^Z|'
    '3Q1z)QAPgVYT4&ys&D<QuHH{xi~`3*J5qGLS^|rPO2RXn)!;(vB>66X=qmE#{d_r2zwi3Ehc0?Jit4ru&j<P%EtNck{Go|jg0&#?'
    'U#7hapR2|3@Gx(&FIB3c3=_;)dDL-6kw6ia<|eSSTyP~qotoX>^W$MURv(wcpD%&>ui)q9xE7in37tGb?=i~apbJPR1NDF$t3hNP'
    'ZFk-Je^aJ*Un|P=A?T)>M_6Ogr&cdlB`Ogvk=|$<>^?x*bsKpKtCgqyn;>IS3Wbf1f)+$KjKI|}yCI1olF2&)RKUyLP55sOqQ(_>'
    'd=)9x94cfWSU;i=xm2Z}&L>&Ll5h#8K}mY!4o>;b?&lGT4pnZzTtvW%cztlh5jin;7Gk)vLTc%%-FN*TNB?-YS{g;Qx)GhERhjNx'
    'DFTc^Vap=rx2Uj$PD+6jtitWJ$DIrIK7NM|U8|w(Lm+{zfkW$xENh$+EYyWTakI4`!OUO(Bkhu2>A6E0;)8cxdC^NB8m9v0(754c'
    'dO7r3|6yy%Rf_gjmv88V`%qBydc=9s@2|3iF~t)g%$zz6Tz{D`l(quSKAp7A6Wl2WxZ_q7(Xm#269LIuCir`O(r!=H-o@5mdOWv-'
    '<8SXy|Ax%qen;CiKvPF|R<X0eXc1q+07$v+;o~MbYz4x{oZYgW!$UNFaW2MJzFSXskFVn!7v}PwgnXAT5EnWDzMFtOv(8=DwNy9s'
    'm0-LPH~(FG3UwR3RJwO9Z86uFmV_3e0WW~=z)}-BH=iKtdoWE|2YYS!ktNa<`}wAQBRyEs%i+uAYswvn!A?J-?4=Hl+lmCx*P-L<'
    '0}73q{C6I1+10(LquZOdLbJD!MU#HY)pv}1Jg6K?ND-nH7lJ#01w16bWe;E0cA%ET)*cEt7W4(e17MOq!t-3%&P?6Me#Bz5-*LWW'
    '4`J_P4^Q)sXOY}YWhkDwo;fMtcI+6O6P5_140A)y0Fap4TlS$f8rAsYs~-HW!=dKxRl<}8K5Z03%tk3cXAe8lF6x%JwVM8>!?A)j'
    'cc**n^krXuKbgC^Q4h*qvA4zm$w0X{ODF*tfK!~BblcYhn?F7Q0M5Jl=a>5pQk`UmyaWN!eZmk(y;J33BnSV+ycGJPXrF(<R^rbt'
    'V+Jf%npVF$t(-D`L>`M6gBXiB-ljfq?rv^w-%GGEp9hC!1HB0p6Z)NpCWR;jw&hKMZ{;&GnvSmtdPz#RY~*?P@<@~R9Q@!@Yk!Nl'
    '?;qfaDl8rc{gg&le)Xc_(L&?&hnuMgLM*u{_P>NOecn+4R8ez)jaohN*3r;k(T5lS37EPSlmkK!0~~MJ#OZiU_X@Ggd%zzHnaB(~'
    'a!d%|LcrfbenCE(<-m2kyLSI)GkqRj-efex%jUNdJYh(7aFlhIrP^>6K)0I(8P)e2CV}j3_J^~tCXZ+9C=l-F4TJz80l<~?ds=*}'
    'Xd7r(VlR-iuxau*0#fPr2eA_g_H?@($52aZrUp@Mc-%;mP(RVOrJq{v_0;Lq@Vt;3MFUk#Rg;$#@Vhq>F?{-Kx=-i4ZJK-`k-xos'
    'Uflrh({^1JI%JfDCKI|`cKV4xP-KC)eULcx0wDwW@Qe1e!`KUHgpVE(emENnv!wqM*sF>^?N!hK9}L6pmuzT0aNT>^V7wP3?2}%a'
    'M(-FlUri9LrbYO`9&)s>u9hg{e#wrW(m!9fVm>l+932skpBIzINGdr3`Jk$3-*zOogfUh7-VNO!KOG)+VJ(d|nJX~G1<mTx$%a-}'
    'vj1SqvZr)IR>66B?~b4!&!N$Hn9{DpG>4rl``YLu>Xv$AecmWk^bp5c5)lGsx6-?xl!oJ1)%4b$ydQ5zO`_%03WT~$IzB<X%p$|X'
    '?_H!6X@2jXp3{q)>Jx1DVR(H0eB9U-(Qbt+2-(%|Y{F3`-r_9Rtb$=N2SFS~`<LzN_3{2VT!xyLK;aeetVF|(R~;~5#K6N{S=8N8'
    '$LqH@#e4Vka{N6#oN2R{lPwr-uwp0m%23P32@gdhbR6=hz9e`rVteDw8=B{*K;xfMihtu_lOyQbQZ`b*pu9ly@J_q1vtt&5)7Vvo'
    'D;90#*6sKYqET`8`Q_ztS6~tn^-YVFSHY`6FsQIT5fa=lIF?+f8s4pW^WF_TPfv%(Jy*Z3*4VHMg+$cqOBz+l9}t#TsPdaTNT^7='
    'rFh4NwrQq%BzZUxs3_+`W~`D`U9(3Z(c&BFav`Fs$D2R+`S@iJr`PM_Z?Esm@j7=-2g(>M+{lSmjGV9%_Xhn{!o+4GjGf-OrTarj'
    'ZFit`%9O53RL!ICM<D~nnjyoC)Ve~d*oB%$M5=zpepEH-uw?`k4t8@5%X2}<L`d7Pui`^vB7<O7L_<*PG<)ZULe9irZdZgR?!%No'
    '@X37BFk9socoW|TQ9j($W?40?qP%rWC&tm&Z|obz+2vPPhf5h>b53RRAdRL8ZKH3m$l<*)l6k34vtPBX_$w;o4og-kiPsiRRy>?A'
    'ld%@3781x8tn+pula$<L_lx$mY}?y}Q*?qjijJWrs&JLV>|W-Lh$B`)BRTF*@7z$_synQ#8M8z<TCiTBp$>GX9nnWGPMM0HgOn8Q'
    'q5Pe@Ik6m{d~`1ukekX1ELVg>sYXS~N+&>il?Sg|wa8&EtdlrgV4A*jSLgfV^<n43(y@ih%5UB6gA%r;ZtCzv0_Oq2W9Wku*p%M7'
    'txw07V{pnP+~>V*WZQ`BA$Uy%^>r02M}$fQictZewb&xcVT|4!y#rYYK5oF4m%p)*_lAsLXx3;AYNf`i%gv{zXaXi{Z)$umw{GPA'
    'IInhAC-bPwh))$x<g|JyB>k!ZaA}~`sfo0`VY}>aB67cDFHsDgU(z{z@48CB4tZeOidR%kb3DpG<O+=luPXe>T1ArT<b4}kMbz{9'
    'rA^1pRzxId(nEv^ezrXd@D#*yj60%2MO?H(S8(XoJ)L2ZzaP`~mJGpA!I}>dk~k;{!-XZNyZW+@vKSeMI={UDu`0X0^ZVNgj#N_E'
    'FdYflPIH2@J*Vb2sJ7(ym}#iKK{mfREqORb<0#NP`gc!ki}9Pg&+z`I;3}q7s1Tfj6o!QpxF!!d6EB>b>yP7_L!QbZoY~ins7O)6'
    'hyjr_4`VV>8h<<xh-f^fn9?u-AJfe@ENC%~wVGeZ-iOqHtcI{k4*j=Cz#T`^KmLGXZ{h(}Ib>~G-m{~#HN@S^=WyM-yd7r1S@bC^'
    'D_IPewBGu<ewe1w^TLjyXuLT!I+tYXAkh)waGP`x+Fai{_C3t1mvB=sI6CCsX8sW2adFVpxcMGiZ_;_+-BGyNwFQ{9am<&$$`ygs'
    'TJpNtthIE$n4OTl+`gCfjwkKd`?V7#R&sprMpal%un+#@L?0?^T2CDe`G<KQ%{zDW$Cn)jAK@JWbuswKfF3w?Cx^z=Zbr7!F>Ym+'
    'SP#?9dC(tSB(8r1nzohRmszlf`hcv<7<*yqF6<%QSy5f{msTeA!#j48{tUi+G^}^qj#|8L`!IMI@rGvPlBf<1-Ep(}R|yp+W_Rz|'
    ')M0%(Y42m|bMoyeT#*rLP+P(S595kOTonc}Fpw~0Df{>B=(wXEGwvs{vS99-L}KO<UJt;GiXe=N@XaG4wzor`v6Gj;7>-XHl*1~L'
    '^)g%?TI6lsnPiXRb4v2oA}YfrB!KVO$C(T`ZRris>@bV@l)>;>2C?v+G=JE~m2;S)_~a>R$Ml}9e7&bcz>Pd-QZX~8gm6H4$yl0<'
    'X%62?fzT;Y)w|7o;=f`u+ucC`Sg3{Q)qT}%ATZjMRIA`0AOn40;t7(*cWfr)g&W!_p)BMt;jYKluP(!EZ;DB9Qf2HI3E04cV4U8w'
    'i<fZgybBW7CKja}j+UrqwRB2CYCpQh!X3meh>{>P70-KO@7Ek6;e^omZ<syt*I>10tQIbMuVLt!cx##}RVC9Ap#9NubDH&c?s>O1'
    'HaCR)T(Id8LGQ?Auv0H8=00g#C^?;Epij8d-*QQMFrk@%rJOjn8{#*uH|~Q~3`HEniw)Bl{^W}EE#v7xoMl-1bF0UDRy=P82kYN&'
    '_O@k`Lzq*{@+Q!w)?gjpXrqd%m)K>|5MyDypYniDdXm6?-=BB`QFa@&;CO2!VctPgsut@KoQcJR4#%Q}Mz_#tsIP!4ezLE%MA*G6'
    'GWaQ87HeSck)*^ryR1A|!xmv=r{UatfNgd2uFlPqz59_0gD6L`1)YKT&NbgK6L9niD_v5W83ujj`OW+JmPNUDQ<A<IHyYIwin6Xj'
    'cnpR#JwAHfFsMB{n=8_-A8soCv;BKoTi-YU<lX4w5>vn-%qxq~NTM!MXF)B`Zr#)LG(3N13;A$-8MgJ`U?tp{J~R|8JK(2C<YE6h'
    'V~4315O5WI#TERxf7{I&v)Dfz$Qz46rRKkx{ug0D7FrOA^IqX)4$-U>TQ|pm?_sB%n+jW@8GC}D4(~rErLn}%%u+(@W+f_9CP^OV'
    '`F)#;YIwI@AD@+SIhh7Zj>8z-m_C+1nIgFj96WSGWpnF}z9K2RH^kVr7$?HhI>o&jW1KPr(&U09h?s=_b6N7u?=2qA@T}W?MSN86'
    '7P3RNa2<XI#+6FH^h@QbHG_V&x_hO+bw}s&Q$F?jDTW1XK=Du}Tz0ds!o7qA4RZ1lqj<|`d^M^q5-UQ<=H1&lwR4X9uQ$E7aNTs6'
    ';7&_ib7oD3c2cziDumf3T$C}rb7yOBVDFw{)?gh9FTFWJ2N{{x3d(|Nv<g66CfT(=9M^Nzo}NFyzC^;f|2_eo3P^d_wW4;FT$VI@'
    '+`NcGR8Wcynh(Y6?tPs%vL5Z{w}?5tu13-?cneav!{y|}?UleR>L7#6tj#qP-GuN~-x>H)E#V#4_wU)!ar{lvq)HVwaf=`34I_*&'
    'RHAdGM`O;9`xbs<LODEa4h<~vvAgA(gy{!+`tFZ5Q%e&?y{Rrt>^T`R$bhtPTEdrPRI|GMdWtBl`*)Psey0!7ikD0NdwzKtjZy)j'
    'P-Z}d(DBGemIw)uu@3k>#`VX#<A;_jKikZ?-+g{E=YKla^Ov_0`nknjW*(KPb3q|B0<>bvA_2j`(SJs*y@KxildWu~{w@dz3ublb'
    'eALNCd~2d2<_8PB2%j~K{c8Vr^)ieg$}_=u{re#IK5sBvV|)a!MNgv%XFN1Kh}aT@00v<=K-$VNP3b+m*m@Eoia7+~Hs@#(*QFSj'
    'R>YtZ29eBOQ4{&(Wc$<T)6sl5#0N}I2YtIA{#r@b8yd6V5yt>-hH`aKdR5E~+zB~B2@QC!)$Ui2p-%fC<r|*PR(B^A$yR+#?uCFE'
    'Q3Rl|gd+@08v#mlAAb(rJ2ORUxo#V*x$mBa$O7*^#b3Aj=wW(GQ8P!X%&dt}0&&gAdr`#D0R0(bs%1aj^}F!jKW|vEg||o>a{+L6'
    '0T-AdW55)BTs8Q!WWPEML(^Qh_~{kIG1&DUuqxn;Oz4mnS)1@C)sDgf$7AH69@<<(2&*gfac7xT=x5F~-L{qoDVETf88-IoXj&$w'
    'x3>5saZ%^`Q|xyH!g{=J6KB}-?I3J8&?&T2AirVsY;?#Hv^)hjUzwm=0i|&V^6tv>sPDw-X`eJOkLf70RvgM5&n$H;0(BWpUfwg_'
    'QA>?(U|70t2M8s@I&pG8KY-X68Bl2UMTViG-n+Y<NJX5C0TYb<e`q>)aT}{7Wm^g|=Al2}VnL|W#5I9{tfm&cVIZXuAG|N;rM~ht'
    'oI~_Ck6@RD8ZV11w4q&0){XFJMB6GXgL$BA20t1XX}t1{=xL2YWqhF<%hQ0P^0WSm3JXXF=rHq3hjt1|joXyz1-Gv2mVZ6S^j=;z'
    '4kIm_U&k{(?n^M3eo;;j%DDoCB}lzf0Cwek_1e$>I&5{PV?u6_K$QidjAaiIjNO>Zq|#$H0{YHF3%z^oaHl`fn!bc}Nz5%s;~vkc'
    'ipf%e`5NfD1O~ue>COznc?1lx+|FZ$LS4LbC!5+Jlhl|1bOi=(c#w0_jft=*L&ip}-dmJpOEq4<jadE6_1a0TFyyDFkfLsk3C|!K'
    '&UfyMFiHpuurlyv$kP=sCnP~1g2(;Wcc}!Qyd-+95c4J<j^Cf}ql-<&|H^3Qm?Va(E0FqX@SG@ho9gym{dPR8x{6ifaktzLpEhin'
    'qxGys9_*nxlmg+F6c>F?B`o&}I~YT-iraT|(uHDsD04q;P03-Yx5Qv&E`LH6WQnKP5(=0gee0^lOa^1$``fpJwRof;KEFM)7nUc~'
    'h7Bl3M=xCR$})5&e8hD3Tz2NLbulg@RID{`lC6R%1;D<JY8te!{@fT7#k-=609uj<wLDh55o8W$20aIwl*NqIVha{cf2tGLUi>Z#'
    '!cb-h&bW4*SswD37GSe>ShH=*3b4?Ra`&n}i;Zl;S2&MT9utt}P%xHZfu9F2%3bO!RWkGK-zwG5EvA1n>f+Y<`<9{264cm8B{&~K'
    '2~aT$z7n$`nuG<|8D?0cJ>@&sKcUSV27xhMRbvYX*8@hv-CjMz8)}YDg~v`}m9k~$if4tuo0@h{ugx?B8G%cR&V*SYty$Sb_DFXY'
    'U7M*``%Rm<^xF=OPh=ZVzs;#*Z44GrP{+LFn7v6oiThr!LIo~D#!(r8yP2_lUG`t6bnz%n+OjL>L8qf>^n^(PI<K7Q#$ekAb3kV?'
    'N!X0M#eChlG)D$s(%+9hn3~7SFP-y27euHS_dSIaq6`x}N)cEmrU`UPQ9WO`fmO(}G3*M}2{(dI%Mb%W0!XdGb#4xi!W=umQ1l|('
    '`^eXc%Ns;gI!5JK47LIT3Q~MGW9XPZiY?ScA*Q}=iW&~bKujZ0|M@uGy}Ukbd8>u$#+?PNMJy-dN-?C9M%s4RmdA)G>Y!;;_8RN1'
    '$XYzz?QwE4{Cbs0gfe1@kreV#Xw?)_b#x)-w=uma+q3Fl4-?VBEOhO(rwKkC0^o!lr6TKMqPF$4uHs`>7PV}*3(4`0#m|1KCwqds'
    'ZS!$AkQ+gtXNZZ_MId7+zCIxxynI0e)QSnA#-62ty31eJ{c@|+fu3e29=SZgQ;Q^z@42~M)Sv6?Z>mjuk>Aq8@9fP#V%5N5TpJrc'
    'd1hu9VG(nn(2r6KqMahc=R<(tGMl04L*A4$y)Am06CNWY$Ka$bhff=2e;reGz=5dcFdrfhIe_#dQtb$x<P0n~rk$(5*_Xe~n3f8C'
    'N*hm|_x|eYNbR~lV!B{x7~kwV+#R8G;wQCWzjF&Kk@IlT*cKqm*B-$h>39f2mq<pPp{l^YOHN)E#mT1p@NLC&t8>@O=FF(kL!=g?'
    'p<#TUcM4boHHPgF%RSbnKXiZo`N~(m@tpQS#tGmeELhgDs93#jilL57rCIO-Ik$AzY+=VUr>x*=;2@_p$8=@TIVk{wy~?7hGQ)cc'
    'zrT%TzZfSr>^4tRDSEZ8#fm?Hzu{z9&{N5Xbh^T-QxA2~G~HVCIKPIi$m`<|mA~Kq%wEip;>omF$LXD!0lWkkE0RHkX&lR#HN9Ce'
    'pH_TcEux=y)uoIzHKU5a%QPB{Mac1ZTJIT`2D!*c>FCL}<KBfIL&<AI!-mpX(;%1vee^Y&a2-ODlnFS<F;RoKh|p)qH(3^6mt8yI'
    'n}TotHBfs!1LP&ql0q%eI?0F%rX2#BApcIAoba!!u4I>8elhIfaP-?08YYUEr41)$>{SFw_72(zY*=}R)jL;?vf{AKt!}~}!5{TF'
    'g(xe9OfS+QCcoi}=@aJqo9F%BMOPlpo7jfBE#yF(&s_GUR+HJW0K>U7hXZ?#Vw;*%QQdNFP($XMM7p<4oar-a$1R0z6~Lcc681{K'
    'LaeECu6^G`FW;c!`1y*-`nq*jJXW#%xS{Utv}AC+*e-SvyTcmD0b>^1h8QYbVkBtu&b8lEg;KK1%en}S9E!=MdX|2D@J>RjLgHu~'
    'A6-UH7&do1mtF4v+HlM=_YkHHV;7L2dvctHrLy+Fq<5r3CC-Hv>|E|JuNF+h?-v8*0#Mh+kD=LF;1PN(U6iODVAs<g!fsXyxc4}n'
    '8ZHm%Rk?UMqlc$M!@!u@zba;af8m!*y=_c3?u?Q`iro);7yj+_%jGjvhpl1EzNS*oLyN#~lAyPVyfzFNd6C8ZmS*RAry*o_&tD)A'
    '7ay=L&Jfbi&^wk4of`9i`w%xtiE~g~#0@FHvUlA#`tA0s&5`T^2w-F>SUN<MF|ZaDj0hRDbyn?WTufK5yfaeyWOYuk4w4^TNio8x'
    'wAB7K(g@R*oSUj~+4RHyy8iL_`$ivgZPvQrS<&~QzZr?9`D(DK#S9D1uhAaW-Y60C);APUKALbyCdhX25v%dpa|3|GMG7gb>KyO7'
    '+PmKC{mWsUQ+l~9G<qpKXoHp)0$#9MA1(ZtzX^<I+^k(w>^@I#gFlzS^81vZ0BxZug)ekK$}tKGlfWz$E_=MWU=XTiu+PpNeB+S3'
    'YkA|0q&K{H5PrF-h97Mpc)&cjUkVgPPs}8Soy(tnkvXg1zkJ?6148V<la`|*os6y|t0eWQ_^c1db-zYrCso<G@bd&-+5nYc_U_sl'
    '33CcBRGybrzz)g-3@jCDgw3|RW<k$*^TWkEhz=L_B13)Oj#iuDO+$G53tJ?0a5mRrzkA(aQo-_e0MuZ^Q0pp(LD6j>5aBc|f^n!I'
    'gQCW^^w{i;(qG++zA>V@{L`r+rlyTq9zJC!nNS}(4mx$l9d*ta;RL()4nASFK=Qxv9Dm=)-~~f|Wx>q?J;b~!Ii-2!iy&h=!JFj&'
    'us4@J_hZ)lDs9MKt1uLldo<zrr(vb`4m;PCph-k1iYge>-je0i<i7k{JyZ6e3)dkNk<^@lQyar61@Leq-v9vB&3x60cQ`W_??VVI'
    'Uque)F`d`Q3YUfDF=dOW{F&)B8h7Mn*R6WWcn;6U9eQ3vf~dd!#3H0qZ7_PGFVL%?Tqcp3xSEG@_wQz1c3S^(=EMC?3CN|4^wS5m'
    'epRc0gT7DW))6;7bJ`n5ULRK|@%1qXEgKyH#B7h1J#jekNpfmmwpu~|BYGr|)Fooe-kaj&p}DVQ@RgeDRicrt+2xE3&1ho|I!m|}'
    'l?LB&vh4SkD<{LqFcN(lcDQSsjub3n=Qw5wtVD5la}%>kLWGg8w9I)cGoT85`19%XhCkl<D{J$+4bn^>+&%4Pdc~%NHZXH#<JHDU'
    'mME9hFw}$jH4DE@sydGxxqQ^>u<GVZ=cd9x_j4fu;dM~OAd4!-gNx%uan<@~r~ZA`^<k3b$%pt3lT3%RHKQk}uX#)tm6uKQ+4-hh'
    '-*-DWBNF%FW&Xta1zND-(aHCwBQDbrVSR@ujYt(oB9GBMn8FaZvDxG%e7A>P3wzAk`(uD@v^9E8s9HYkXtC-MaSRHZ<8rF5UO4{k'
    '4QdEu4S1%E1&dLM%!CxAt35>;!2&1<hUVgI-65y>F}sdhSm&7by8udkN=_Uh5gDp_C-vdE-C#clb$w&S$HOBb%2pz#bPCL6jH!`T'
    '3@BL3f5S24B_pb0w2`-Mj(#+@^4kk4cq3E^nx@rImch=L!{kxNTs17i24I4wH=6)~0$(|q5ELA|Y)mI;Ar?lM0ZsAA#$1UYEu(&o'
    'n;*@|yJ7uSR${=Z-?X9Yfl9LCRx8Rn{d(i*&3+KWa36(eAiYSLZ~6^CYf*n0z7Ayk@b<I6+Wzexnn>F{ghfJ(_Nrp6Efj>4OkpBq'
    'j3B6Ia+YzM4ZCMUdxk1fFmq@npi|9L6SXn4LER@Uh9~nUiSY#ZGR3>Lv+t0MhDDjlOpJy@63u;x8|_{mvXs)M;*Kddb=H@6vW|az'
    '91a`v2=m#bF^&ExM2m<7Y6BeZWM-%NI6+0j{o3@6Id28N9<}ct-&}(S%{|}(&7;<kN0$jfQx*ur7}_edWpSt;rhN;)MCD6tZzx4P'
    'h0W4L+jk6~;2}i+TGCyJ{z>#qW^pw8kT%Ti?zLA5?&)ezPfzP83eCbT3sW}O2ty-64SSU!cZ6!1xtc220|z`yx~O5V*u<3-rXI-5'
    'ejw&eD$WA!X3dpF<x&R(jqk>^b9>&xw>$XlH8QI`Kfg$ZrdFX~4d*M&2mC(gK9K)8^pMdpH%;K0#jiMhn!tUqidGJ2lrUMypnZbj'
    'wFfKJEers+yJGe0jvyJTAf#|0CSn>{@@IrXc_<2+7<WAZ6^#noy5;fEm%DEU#_u0Ygq07jEkg*7R_2YzgdRPoj7Gf=AqS!W7;w6F'
    '1LqWT*DO?Egt^C4Xx}E35Q)BNWnE+jxIeu<l*+x>9E|m|E$p91<pXHLrbZF10U|-bX@l;{zQ&lMP_1J~@@u!Te-`T!s(bOq|D{$8'
    '(;)~ih>W^xj_wS%pE`Opx9#AKrE|I5F>?zo0^?57NjhZ|ZQx|+ZB!EMY|7{W51VMse{5l2_me_^)k!fXEKcK3U4VdJ5VVCM&{~s0'
    'P|i1{<o~|<_Y}v~0A(ZfhMI&!k4d9|U_=ouGP!>=kV3};zjG&6)4R5@gK3EimG_fsTQ02G?(L&35o_}X%wvd#3B};rE`QfPc8_K?'
    'UPblQ2X@5*fx}Y~2I+mI(3*H`!qmk}*<HPvn9zE+Z{$~84t(0oOs3uHK;xpeSjlQr>$XxIg(sIg`|3R)_B^Cd+u}=jt>+(VwjzvY'
    '3@<TFO&*U7%OHYQz3c!(n<R)IZs0k*?6&R;UHC|ms4g`^`tU;zdP@qESk{#$yKwz$v-#Q(@itv^*Azj^bgM`r3$xy|(ofczO%OMF'
    'mL}An)77W)Z40}n)nc+O$o5reY1EBvy<X$$p0I?DF}nJ`F>mL_eS94ZyUXDm7uYDIrHC=wMY!>dkxt4fkbrcVao%DGXfa&7nNv?+'
    'dNJW7-Nm%3r;QF_D|J!KK)wOZuur|gDI@?{jB_3a6k3VZt^0`K4i9UF<)YdgKdRT>#%#km&%)?T9lBc6Hch0sOS^X8r_KKGPxf-k'
    'u<ht!hXM~LYf;rGEW!cbt5JF3Tu>w;KB8ebNicynzilgf7~~ubrx=3B@17T)Yfcq9g@HNhi+R0sOxFf0UK_d~^qjr6Iw6Q#xZ}DY'
    'Skw}F^<0EXtrr)a?m4QF+N++fjT+yJ7VdTdKO^Bhh8nyO%a~wAcZA0^`ClF1D{8p_4)v<9+{!+~EVqLxG4!Yysd_Y&<9+0|Vf#zH'
    '@7tN1y1X{mUhWT{K06Dq=L_`<X6S~X0si6?*3niq`T&MV`IbY5+F)dx7@?sNgyCzmtWN><J%kl%B)@mdlh5_Aspb$Qb(%Gr!Rjqj'
    'F<6W!R!9Ryu_Ee`*<Y{SiYSiQFg(0IIwor^cswo}bKLY1bd#i6$VbSd$l5*(?o`+w8FGm}X*tc;J`^)*AAWR|eAmZ9^{c~r6)Ne`'
    '<2LANF_q(a4(HY;4t{#EiSqvY(%&>U))#V(8FUuY<U+z9BTX2w>f}-Spzqcs{CaBQI*-lq+D{gN{5s}1R;Pp~%N0H`G^9k>i}7jh'
    'e7Z%fCSfD!F!k;G*d&da&*6WJd1vATg)V~hx`dC531(`M;6$R0U44(l7OqlEl;QIXd1vsP#~=fqw4P2-LMeC01l+|aQytx~k1G@u'
    '7J<lc8w*^l!evKzHlrvLIlG7@)$0C}O*iafr<OtQNk3U0Ol7DAVc4$!qfG6iWMw*FIuY-WtE;q=#P9Ab`P(YdaG-kPeKji7PB@(n'
    '+Y0V8nz<GQNn~Cp1jcLka2*L-A<T0{wD4uRSyA6eEwdpw!cB}MLIHO;u6_`r!|En<Zjo+JS>%X^c?~mxAj*WPJOa#COdHM++078%'
    'a94jI*G!t9q7{Yd7+y+(0}dKEnNksRTcI2ihpT$HI{iKGz&9Epbl1>pjbh?7v~(>>{1VZedzVQblyYHnHmlmSU5eW_@_1ZBx|{7V'
    '{l4Kk0l+}3jZ+%3Id4FL3hBn`QZ&WP`6Wm&-EA9Lc?x@8OeU%1`;cVf9F$`A+enkp#mNj#PJ+6})WvI~#Y3zg*kUj?$Orf#KX0H1'
    'I*VCM4a8b>ciDhOI{y*lD)P|n2F-80`cpagRj+GkQ(qy7C{`!vYP4{JYL9hoUrmfA#dwqv<;`t-xwf^<C=ukG2iY)VLqKw;4ML`t'
    '!V<$b-Gr}q(T=z6=ESAhwGo^!q$HObE;vl1T0!7-u38&D+ImxY@Zqn1MXTuaoS*L$pF$TDiZPuu#w%l*j!hk0NX+rU&C7$!(`m+Q'
    'Q^Ci>bo{!L?XVhNk<u{h1i_Y=jlS9g%7gb?hE#!<tGRB&ExS0qmrv=)LT8H{YLGGB3xgAbH~1!Da)pu%;U@Uy@{dr`Z4a6F;Wp0U'
    'gnLJfayUF}VJ_zCxLY-(q(W1uCEPa-uF*eaNa!KN9NKvKO^@X5TfTxEqgTPRgN|a!Vo;fQs(7mM@HonsRN$azu=A_)_H{eokZ5;9'
    'q&RPiNkz3BNYhLkZ*m_RF5&W}y|lk6Y=>^z&YPpT68qC0*;E@8grIJ#=V~kfBU1zv<$hG)Fd`jpt-ax<Z|KbM-TPefn20iD4D=`='
    'v@>1DAfPz}k&0l4CTxAP<=RX6@B1et1N(3~R)XqTdkOnMPz(`DOo*ht4$BPOIzTRF)wOw}w=<>{%Z@tFSm@1SBCZ~Q5EcwC9$b)#'
    'D;ePvDmKzH?+COnV|BXf`i;!IM87@^uj<obbsE@Y|M+6+m{!n*2pxaYTSJ(oUj<6&4NjpzYny8~<iDJe=QUk0z=K2*13&tZNIS7H'
    '!(crQjNvJ!X)?qSZ?4_Qe&TS9#2)m0gL*H_aqPu^L#tV>k`OLy2{tvtwNVaEcXpYdOmiPh1=!d{gb`nH0P2Jugcm@Xu-T}PTFEgZ'
    '_|uMGxr+<b-tWpxH%%Y6Y#o5UW=9(}Mz1wrhSfDuV7R#~*M2Bb-}*da66Mxp2Ac61c}c`bVLlp@GWgxc*f*A&QW7)7G4r}>5s)*>'
    '_U<fw4fmgo(gtbUS?t0e3qn~10TE{<kHOq904B=OD(<h`##zPxwwq0Yjvhjew^modHw-?8JB49_3}v9M)+hvQ!_&*_x4}U-^xg8q'
    'Q=N4=Y!S9$?Zqrf)YtH4$DnCqfW2=PdkH@0qiwGJI8Qv}$Fva|Mq}7@`@$3}Gha*G#06&m)W$96U4ZZOW#{Uq)%UTWy8uj0h%MwD'
    ';iSkiqZJGE%%PLIp!U~E;jeuUt8LlIqGS)09ps$FLFD|ycgD;*8G9d_QtK5l^%MO(Xd7F*xGo}%VF7HCLh^=(n5#?`OhsAY%%~2K'
    '*p#;TDqE|5_0ITuNuB2lZHzn`f^ARK&o*k%Rnp7SlFso{LJ~%NKgHcW?p}R|OPr4zBM67GHE0>M7cZWK#?wa%Z`f!^td_LN&iUIc'
    'WPkKCSF=HN$XMx1l3Jga%)i#?#%Se7Qv@HoO`A5q=P>iLd-pr<2owImHZ$s-xi5tqmH=#u3GtfBbgY!=y3b9wZ^hk#jSV6vY)vtJ'
    '7+yy%o0$)uQ5gy@m;DsvSz&kchpyl7z8tVb=Qg6Ht12^adqih?pmhp|^NW0DI9!;x^}AM#n6*zyK;Vv7<`x-Y>9S2pUt=W(u`wbF'
    'o1xHtsW-*Q-z>W)QWyY}!tb$(K|bme9>IpB#<7L~k-THnKs`3CCcjw~Cpr4i8}w(F;t=HdJS-&*ZF8LHp2UbO=EAU6GP`H9X8mT>'
    'oi_wcN?!348p0<_hnXy(1_x8tvspLd0GeUM$|f%S9}Dl8;e@NpUWSwG)WxLL273r4V}KOY3gyllpzQ}B{A}q{E&k!#g#E+I*1UOn'
    'u`DP?bTX=d92GH>8;&)_HNb~koUV11e|jUTDVO8Zm*^Rig$(z9{f`a(5tzUnd4*gi^6OT{V0)9UQ62IK8mseL^K&cPZ`V7sCIbQ4'
    'GV$jc8Y&Y${v9xz=boq__mzf7l6eb9y}fW{yJFch-oL$ebR^AXO!4W^5o*7LZGUYxGl#Mz!J6&D!Mb+sH*kB$7T_Fs;%IoPAbqc}'
    'NHs|_+!6?~QwTFsOsf9rsaEy8#2!8<4;N!;|LeEs<HLnt4FAN(#WafHBm{kZ_{<YA2JH;+MMt>ciT*UlvC3~q86Va*CzS2S$N1a3'
    'CtE^Ig<WN!6-cRC?*x-K46H-3qIN3-BK<ihKjwg*r)xidh~b<6_44P-r5Qs-4>8l?ojpNf1SPk0x(PEw{$O-PB1iFaDVq@Z;q6EM'
    'Sdj6ZAw&@_^%}R0pCJ<0k*@XO2rh+#3Bj7Rj8cDTwcu07KYduS_KmI-tvHegyJ_`;PNf-$XnQILZNeJY9mc>V{-<@*v%Km9K1cKx'
    '&V{Q#xjX;K-B;6s%jruU1B_8x*kAGzF`f;_!3;*ZOK=@PF!(tBv!89^>+gMvzU<R>Af&EV5p;m_JOn<H6~1|d`<0;<YW5+_s0`Tq'
    '(Fux{>&J2U-8udGw;Mq>9OVs<RRO4m1|m$7{T8E%3&te!=OM)Hs~u~dhHJk3-^c$e-LLWB{~TUEZ(y)4R{VSkw?Zhe*fGA!c~}SH'
    '1wig?w?8gOPpfN^OrJlT*%`!$$H&dGkHai8NOU&M8jJ*b4NTNNTCPEsXVU0$3lMhan&-c6FzUqi7-(m5lR@(VbW@=j#~9Jx6iXUg'
    'V9XEm!f%&6W%(ah2HnQ=ZBtWm=3H<^_#6>84w4pBF<PbYHz7#DIi2^dH%o#qAJ}sJI#i0h+R)Rq?|A~!aMO8`jq&Zzg8K18O4<+B'
    '`}As#;>PnV`yslb@J83AOppu>>rD5L#Dd9%*nm6R?^};S+RN6^(I!SEG5qs`j5ZhjJl`185wUO_!@4#G!cIT^B&WlNlhMKR$Ipj_'
    'xjEeKG`H>XxDgFF!I7l$Rb(4Wr3~{9KR6)?CJ$4@R2Gz=6+4!WwYE7CM%$YS$GAKEL0NThSOm(D=4xJ*LnxS-rPe>xPyNS&Pb-kT'
    'WsDu-!U_2}3*QoE%G9`MxWur`VHIvzvF?^KOFLG4ecWW`D-BBobf9M+R2OYIalMMxzD@8@U`wWw>V}`KHm5MyMsNO0g6r#l4!5q&'
    'Z?X#aFER+JkC~`|m4-mYy@Kjpht!+`*qhC-TGiNu!$!?ChAX>{1j(o+-5N^pGHf(rHWOZlNpf|brK^_RyuhZA@#|Y5Rj1&tFi;o-'
    '+OSmuw6?*Fi>V#?HH)5V@yoXfwNb$S;pS^Ngbx;nMa2k7BRrP);;rg)W<OgNZ|KANd3^ZiE0|+BoCY-Sc)3H^DMxV_)O|Tv&L|TX'
    'Au0)_I5{FHk)uI*?aF&-B7_TEZA1idmgOF92;&!NVECkj;)U%p_p0LRU;TM2FvZvh79hq=u(p|lc8k647I3_2??|E{cc^8{wF~c<'
    'TPv3rI|=v|N_BW;7?wm|$$bYCqjj<)<!^szCVg7^`S~?{K!B0GtoDtMFT<8xp+<Oig50SxCM2yQ90VL~58Mr2b3x0(`?%k==Jp+@'
    'U4Twq4J~5^!hj(r?*z)BW_7iKbP5-cTzJ=Vd#*T;D?X+PE~c$7>~zH|-xB?Uz6m5?)F*1W3UxadeA&u8QTwQ4dHhr3gsZ<<sGcRq'
    'wfKrXO?|`wV}F_yoiT<}j=du%vUj(N3&tJ3gbg`!6Cj5&U;Nj_#Sc+wRJ)dYbbTuZH-;+|tKJVyi%j0A-f+0c{Ij`HjKCxO=3$)M'
    '?OO3i?f~D#d2?Pmzrd+C9uSC+h##?s*;Tl=P$DjYDUZ7rJB<R`AVHBz^)alO>2rfg0nLWtt8Jr1WDB5+;=KO!YdFXCx4-V0>ldVH'
    '8jHYE`{2yF#C0gd87QlwEbv}?8M>b@DgQY{JpHg9m*+S0kPWMtyo=VhH>WM(n0SbOxc|jKn5!&|V;tS~>Q%SLVW@-Ju>L`@*TE#;'
    '4hf@riG@el<{NEVGc8Hu^-F8&&&OrilF@T&<%KI#kp4wGOrL)UYI~=ZJdpE+asRx3buz(!JqP9R@pXd(YRH&Ki`d6oy5e^=s|vkd'
    '#6Jm|YlR5J$nyOwZ-)nC&IECqw}!_SKn(lXxJd8UaAJfdtg$iNnXdS?lXd>N#g~Jk7weMdSG&7nrU!yaVo`v33dirl94EVW(X(v)'
    'd7~>sZb-MHBg28Q3}ID72@N8j641weO1n|_`xlRlVdoezR80mr>_vmQlT$#-h{5<CG?hAfkM598bbiGvhCS*Gy$mN|*PoZ8*SNY~'
    'W%~aJMUdXmE%~x(y69-SwE>MP*Vp@(e|Y>7D?gi^x-rX+;m?r8=(Zr@8P*jnv@vWF-3w@N+6+!1=zIU#=iBHct=p17AfXs$8^c`8'
    'NQ$dIrmn>BF4NQ9`toLQ!Lonx`18B33HxD-J6i`9AeBOc@p%Ucvu4l0nX-t2kN+BZU0$dC>xVz(axbvF1-B0?OY`G7#J&CL$CEhs'
    '<2hY8oW-h#eQh=a{^a%vxeLw7FK}v7%(yBMZF$2bZU^3I-Tv?2_TLTXom+39%`~piJRA#E${0{0j7G-;UzuBnlF21j?%4Xt1@kAt'
    '^gA1Q8KZt~4)KoH%Y(_p6WR`v^U(Lkz$?C2-JT;JDkD10wd1fI#fub9+Y!Y%)k}%|c&(O!8qHbvoiXw)d}e!M+HSB-zrtOV8KW!l'
    '3bSkFM2usL`Xi6|AE9wJ9PMXo#thD60K*1q3A9WQHc1uFBY;5&h7eR+92JDNDX6@_#GlsjCpV!FV-Q1zr#-)mSE)`Tq;lv0v5FkI'
    'W%S0{nD7jF3NpS9%1`t2=ciBO-PX@)Vn}+hK8&V``=^KmJ=3&t{{jECm>D>v@~0nG2(CVy!1cr&_v3t6*5QdShm8)WV6V%hY^CuD'
    'he-)d7=y7>4G6(-R|y^%y4bt$W-_PaR|lUL2@lbW3Q!Bk6DDsVvy$bRVHhW-+PmO)HS^^<WQwuVouAe-E64pH=SVSnDZp=c4jz<+'
    'r)KZUoA8e>TfEUs<vM})5w~0)+)yJkV(^gAuisGjKMgtST5py!ABVMhvf)ySx23i+pe?xcMMyHhv?<VGQHNZeVnaUj^TYc6l49#y'
    'ck%Khnv9x(aY7ebEuRNZM=#MWuD#iY-?4nAF0*}$epMh}{whg2vzTHI@8&EMB<wJ)l)3=J^YxJNOlXIFYwmzrVjNijOEE#w$J&I7'
    '!w4x3jvhGX^ALkZtDiTBzF#m9=r0lNE`OYJ7*m)8N9#`&NF5o4pW+fP&;ymBgt^Vq?Ob!^5$|cd=?$81?eH*hqebXLRId#+#>)l4'
    'hzfn2=lZ&JHwGur7{vT0Cpb~C13WmAbkyX|4>gTOMz4-<u3HjE`LNNkiBUq(*)}o)bW|-Os5eG=sLmoSHW*UrbLFycS<MC+R&Zw%'
    '<)I?5XiSB90TB~bmvPD{3ei2Eik&BF6Br@;c8=IzmC?%xHDwW%#~edZ<O5TLL=)+DueM1T0ua!!=Ar9_M1u*NN%n{ohVK#luNZb?'
    'Zg6$gia(m%^F8FwUOWc%7%NDeR^s$!!QE8E8I_D`r@d*+Oulc?XX)p7ygZ{)p=xMg7xc0?z-t=;w>qfJC}DBWNQs7ixoX9`P1KoS'
    'NB~lhgCC5C(!!w(;gllHWuXJg1IzY59#Xln>@K#d;)ulpe-!B$9+pmPJ46OUHDnr9jGSirUKRay%deV?4HlYu11bPW)M)@E!eEwg'
    '8r3ovtl9`t{<OJn-IJnW3xq1-!<0jdPikglLtZB|Qfj!EcpcB9_<4r*Zws$!C=TaYk8~M<;t`++C=v$>GN4}Qo~7W1SBzbwiH(9b'
    'O*@y~jQ%)o=rT}zpjXV%VayABqufBO@llZ|Xx7#LsRjRE|HuCWjK>;m'
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
            'protected-producer-original-default-required-context-v1',
            'protected-producer-optional-parent-source-v1'}
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
            'protected-producer-original-default-required-context-v1',
            'protected-producer-optional-parent-source-v1'}]
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
                'protected-producer-optional-parent-source-v1':'7b0703d88d404f38c1b3dec92f77f03586c9144c',
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
            'protected-producer-original-default-required-context-v1',
            'protected-producer-optional-parent-source-v1'}
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
            if path=='.github/workflows/parent-qualification.yml':
                # Whole historical recipes retain their real Parent bytes when
                # the separately preregistered optional successor is installed.
                parent=('987d8f0d198e40211ab0f33286a55852e286c174'
                    if installed['name']=='protected-producer-optional-parent-source-v1'
                    else '9bfc6f8723b1f59426f913472b78206844a7f201')
                expected=dict(mode='100644',type='blob',sha=parent)
            elif installed['name'] in prior_callers and path=='.github/workflows/repository-checks.yml':
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
                ('protected-producer-original-default-required-context-v1','7b0703d88d404f38c1b3dec92f77f03586c9144c'),
                ('protected-producer-optional-parent-source-v1','7b0703d88d404f38c1b3dec92f77f03586c9144c')):
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
