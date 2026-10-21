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
# ad8889ec4240f031c064c3a7be6877bf69fd1569 / tree 678c452ff403adabe5022543f2fb338134a28c07.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = 'bedf9b2a10a3e04bc99961f0a5f4c9ae33477f054d12b6075093c772583e620c'
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
    (
    (
    (
    (
    (
    (
    (
    (
    'c-qa~+makdvL)E}`HXsQ9QggxUokQ=?<syU2ZBswWaWiLbW8vHEcJ*4!73o!BN9C`NBSI+V0D>=ySbX`*1fm>&wu>ar^CzV*YV@<'
    'Fh3m+^M~WV9@5i?m#5+3c}Y+I_1p9D;UE9~fBxgkaZdmE@BhfNtf{Jh{I`ERe;)i}QDnLQsq><n^2y(2dAlsB9OtQSvZ>3LtX$?i'
    '_y6JL>tp;EjQ7X!AOGvWeOq?4(DeDk<MIA5ecf1X983RQO=|i!n};-YP1{am%Ca_F%4VFirERJq>wdo4<1qa`d`chwb$t4Lxj+8v'
    '!>8oe4ljq}!}G@Cb8q2cF7hQ$W81Y|(=2{(R*gknH)U5=sVLjL`T62c>GAk{csV|O{V;t_)9+g=)>G9Mi|5+r-7?R8N~vG!YRRg('
    '_e1+`D2pnM)z4RaNzX4Io?j0y>BF2J)5Dw|rbF6XcOI*`nT9cImZHeVs>v%qb{yuao@+04D2l!qiaqOYt<{dxn2&wi_KpAc)GbqA'
    'Pkq^CQ;`qDQ1(sU*IhmSe66=v`RwIBrH7Xf|9l<p56fX%-|ByT{c`{F)%&iUyCs|RzDreB<hkFxlx5L1Lv7U}`MW7^t6i%<9e+#H'
    '%ZK>w&zF~7s<x?@q4Ak4X-;)MEzR8K`CL>(Ul&t7XDKT$9i_jP{m(;nap|I1QZ_ep+0S{AEnSvneV><>pZ)l{=(4%X#_9(j?D%9k'
    'kzu+&c*-BA!^hv!!|#WO=Z~L;c+Zbtf4-^*J5}Q}6=PLZ?O0Tu^Ht<+o#wi$>U^nF-nLnB&8m-nxfgzU-D+veR1K-^$}yYT!jD_J'
    'ah!){T#9zd+Ad3Jnyy>-I9^_L8J0Gi%Bs!1-MYy7Arl$Ov6}kSRa3hR(@=NiRnPe8_2J^0Q+%S$ybS$Vb*-N_^ktLvT|Sm+Ohq-1'
    'S(}#Ssx{*z-%X#Nj$hK<^K^W?{HwdV$}&%OaGIK_OH=BHx*Xcfp%T05Y3}DPzwTMDJ9rqrq-TLU-94q@@$m5J;x^{4s+OrqbyJC&'
    'DX&tQ_eE6=)7WH9URM##TvgX^<MGSgbbMG2m)CEHJT+ZeH;p*CUW-jxWcAn#T|Li5W^-arRbIV*+{^RbpMNal#q~$$EUT)yu3MKx'
    'op}=V&<m$-NGG!N6f*boaP|65psVuY+G$$KZm5g7_TiO6dpqT0US@+^YZ{8Yo6D-ncKr5;DE}J1etbwT5$W!pj;}B2Zaxg39*)m1'
    'hv{;(Df?+01oXU~>Qs6CqI()#omt(~j^I2NgOsJedK<6v<Hd!Gu5I#^7jtTT@N*we-%ea1%Ut*nmeEN}ZM%En)4@Bhz9wdI1Ygph'
    'FP8&Q?PG7#P?WX2q)f4?x=-!sVyTNhO?f6hG~40!evlWw9KRf<55nFbhi5mc5AfsgIv-x{&Np7%vKPO|x=uqi7sHrRxrm1IT=jib'
    'brBQurjD24$+S1`X8kJT<G3GQ<&u}9RNIu(T+B^hc^}O@$ZndxEBa-b+cJ~UrA)Gw-M*Pu>Ez`|IZs30O+_Q~sQvb#o{HAh;4_i#'
    ')!kA{w8|poH}B#1^z@MK@7A|;aVLE-dLVP#OmjPy?IH(S#<^(fTt2omNnYms7R${$`7%66x92-KzN7r~_3rcGIdYYYyUOC?YL==S'
    'vor}KZK_>nZc({HUfN;SR-V%ByE=~kLw{@pvu29QWvWNfQjXuYPVZ1=b2)Woa)QLMCjRa1yLdcT9>e|mRX+{W%jLk<%~e;lm87&-'
    'q^NyX*JV4+-Ov<{bx~#gEMpz}o3|vVTJ8^@KELdawM|<tGOBE->e1DbeCK(WE00ne4`?nkHQUmT@7U5-y5#}XO3ke8%dBjQE-xbM'
    'Y9qfcdT%f5%C0Mm`Q|N1J7&S|@P`lk?%N}}oCP>5YKeYPzj+3wa#7qL8^L!ORgFtNi9gxxkLCHrcXj!&^o~XwOONWQX>tiIy>mNx'
    'P_1&ZZR@hH-|-c_3{RiZ?pt7y@Mgm_%RZLI8A(3uylQKQq>U%k$PfA~-TszN+3MR>FdknY=3yhyI3~S=BR%(8GT6n?D2<xBnJQ&('
    'Q)NT0PN>o^+S88fsZ5J{w;!9ntjg4@wzF}W0V_^&H#^1=ai%4E=Z@Ap>TXvUoND=dk-IQmj9rn2VNPS`WUF$9vMlR*T%=j=d~fOD'
    'kHgdP;fw#^>D65>>x#g6dN@-#j$=JFu847HlCnAt-B@^LZuGf)-=22gqTNunL#e80n=y4Tnz>TlO2CwtqujUg!P`;w>$Y=ukOY1@'
    '-5wj6;5c>;)Z7+RCJ>Ka*4Q^w-?=PGciNbi!gk-cwVQ7Fu?1*Jh@J7JZ<8!!iaN3Di+qxcR7+J3b3gr}txd--D^9ZYz?x-9WiOGh'
    '`dpxl_t{CBg>SoU=6qb-vt2p=nq57oKhncSRjp+0AwpiDB2oazJg+XxT^~i6I%sGqkPq+M&#p)yJ*@gNAci?D{nR&u8+XVWAO8f9'
    '%^NQ?SLVKRE8k^BUk-cDcn@P90$?apspe|usjbI89|w?u-Ic|V@_DG1_wDQY)W~}q<cx5TdMpFxS~569-V~K14lpk4u*#P4z59|M'
    '-Azw$#D|x|aR0o44k)>*s&LVE{U~i)77r_Of_#+h=H&zfRJp!;PkT~=(&g{q_#bG|ki%IOUKL0ma#MDV0yQ7nxhUSZnH#b<IpnzH'
    'P2M!VFlF;lFS7r(UaC9|xhtn|59Y=6zKuN}U!Q<l)A4hHTThp>IqS`tqG<4B0%c2cK;vcAM+pElpFOk*#PrTBMOJyYqlASp$=85='
    'MO&-PmeD;^Kwajts1w{%c<Qn)uYSdLmf>*!x&icdRX3#})k9X*!=z!-%54WZ%T#zwQ(1Ps21@?UbN%w=aXH+lZ`Io6&%br)H|3x@'
    '0|$wi4Oqrw8RffKK(abJMcusfbiX{kKEJq0eotSYwxChpy!_JlU5zPsrhD&5yG5Qm<_?wSOEq`tJr%(fn~5x2kE4Z&7QMDl8kRx~'
    'uc|Tgg-v5s);%m@-}Qe6sn7rB@@+Af&_KrmI@;Fm3k7{9ldbcymdL_r>u&10eHr$r*EQUwr!R-+=e37;F&P{CUOyrl9ZQ$S8K$9G'
    's!SZKp{-IkWy37y?EA@|kMZ`8$E|=L7qoh!8~V1IDs9<9Xp8ox8+^|4864*`*|+8?ZMhse^L{FPc%}Bo99b0LJLLc_u*u@ine);f'
    '=6(6ogUkPqbT`aj4wr8doejx{_?M4G)98LcCFW%sbhiAz62Mg{7<Lu}=T-NBiCN|nSC&PA)J|z?6!w)b9tslh(WG1x2KJq$@4uwo'
    'ImT4xsTdXc>cgm7b%3-{wJtR^yD}^0u?NEMtQWuU_w4zU+F5N;mGfLe`Rlfd0zdV#=hCO_SgWPgW^;SR;-|uNIzFYl-&~Im>2eJb'
    'p;a)`=cu%g+ooxu%zYM>d#@SQs8fe&*@@A8zk@HwKhj!^x`H;Y!W=HyYO7{rR}KN=N^2yYaW}%ndR2R?@z4+Z_i$ZQnI=y>D}C0P'
    ')>o;~Rgd{n>Yn@3k_#xI3QYaDfBl`IC7&0yV>d*t4M%A^UtAz=KJm_nSarg?yt~}L@F~9Rc;;##?_D#uaD5fIudtI#kEP~n;l>3J'
    'gHH56uU-1D687>PqLH0Rdj_d%U?FWGv+q23fPUt6=Wr4U*>d~x=WgHh_<H#{`0nzlEBvXqjuxWMaFaDqV)vYWLf2}v^fzo|-}>cJ'
    'YjWnYKFv<amn?PhJ(Pt%=mzLQQ;c(V{SlC`uUrnF!tit%3mQi^X%Sskx5^~s)wMlMsi+;oBsg|5jd>n#-om~o(R%*Y%QU?QWP{mX'
    'u?;-@L4BOu?2@Zmo^iuAzP@}uKI{WD<M1mIfI7Yh^%IIvs#{Hz3b3Nbq&oJzsv920Q~CtcQK-y!|9To8AGflsY0Q+ri$ft41P11E'
    '9P2?(SVf+4wSmYm+;A`eOP8Cl4Qh>^-U!;B<|<l?put7Atr#Oj21BjZCYkmxy+0x7+o2!IAeStf5oylcNELLek{rzSsLL1>nB|K5'
    '=%%bdf1%d&ZajZKdBlp-?ZoGDT@QAGJ2y>DxuY67{qhfohsW2KkKX$InN{^chX3JTN#YGwQxRR<jb2?;sowf}{wA5dQW3NkfC#vI'
    '@mPv_N0#)r-B|rYnuGZC{l=p7xEo&L(QN}qgDO#)rUof+kOrq>^7Sf9+Dh%APn_b^?f^%Bwy`bJ&f*J*{K;b}0&8%E&iH7mk5=om'
    '9;ZbB>vm9P*30^h+<19OshYDH*{No)h!7p{Q7zV{4y(~8iYL+z%g!a=ps|RRcizMB^yT<;_v$~lk+sx?55XO&;{p$xunpympjM2$'
    'JYUena>b}HzIPv|%JajSEAjF9Y5M<~JhHv9|JUdwKi|rUQxXN%nrUv}nbO;?!yEL9a8D~K*U-Q-0Oh`4&t^dRZM%1D=M6wuw{<z|'
    't;V)MC7dQPRY>*ysyQnBiA6eWACk`n;poQAtR&9U=|(0Uo_8Ogx$(V915*KtDw5kcxSigb+IyI5e<Vw6cF?aj_cgvA?&lN!vlnm`'
    '**Zj^V(2k|^r*5~5NO*r5D*xdc1s!j%>4bEJ7ad=J+=)Viq9^dmyj^wYeMR>=mu*tVB|DKFdp*MSMT50K^y4l?WLYc=a-QMeX0U`'
    'uG1~g@p9%ox*es4ae+^VUx;v?cl|He*@HXlUejZE((1c>%902@!lHGprFyV)(Nmirq%@+&sCl)Gk*4eS@9LEFh!Nj)XfI!?<ACJV'
    '0vElzOrV;5kaO>-IdRywPywiaH@<&s*Tk+_p5g2}`1teUchPD3BREAU)j*D}hk9-J1)t?PT|azTE7{la@$>M!!H!0nY=n8+o7Ay^'
    'CdiNmfH4Aq64!;J{V<Kc;EbKF!d>untIsJ)z;>nrfY^2`WV)nr%9>&dl3L-xW$FE!dOmzw*%1d)5S8zakFo|Vx(pS40BxEC`0?0v'
    'J_fC;Nuuk4!B^A&hP|zs&W^TwmuL#2y@veSJA0~O6%qYNs+EY?NNI*X|ALR;O$cy#JB$7?7AQzoY6BYTz(P&Ys0;c!4?tSK)QxcC'
    'cHZ{z@w%&0zd!UdHZ+d`S9NYC9A!ia)U6R}0kzHBo8RKMU9A`82J0rEE97kV;UG>`K1GQ)91E^H7G($(5S!oqe9j^MGNe-$g<{E-'
    '<3dJ-fUx4Ti18o<Q5~(khjv!=d-t;AGb=D^g4BnS(Lx#Vc6HiE`7m_@baNVHqx#wHySH+#AO8NaZA5@9%B7{%IT=O}ds${JB@NOl'
    '4AcvYjtT($y<59tOF%(@kEn>RRY|DEAg#*(@`8?O4$WA=<JpC3ay~qTfatulRHV07#0tm`)5|s%yy)gE*`yn)wC$!o@~J+9Kr|&x'
    '98RvR8QSuiJ!}=Rsx(DN(bcW;KtVu}R|c0^TWKc6P*AoxE#U6oy|dAz-<wf0R1|6nU8p2F>DBPa7HL(g<+>1g|D(g{`WqgWEz}|v'
    '8vICHLlnh&|IkD~jA)5EO^$<3)p*fAVsOsKNi8nR9PU5fq3VAp(YlL&x6!Y&tOHzP`o?{hM)*}tQQ~w}1Y^MzFWVtqUN$I)mob@s'
    'UeM0<1-c{=qN>E8RdJ7@U2$eg0Z%Whyu8dQ;aUHFqu1M)V;wNdxYTV^pbXMNwTiY<mnx!vBAS_h@S_6$N)LgGe;l4(4wO?8<(293'
    'vcVyjozIwe&|p^yIZl>OdPQ}l#X+kqLW8GWc5%t|q)5#D^Cq1wk6J)OAK`bxk;?E{=M3c5B!zo7)%1;Gz>n_O|5)%u47q$xhCue}'
    'GQ&~>__o@N4FZ%CU-qhj`cxNB8^7;)Jbt<R!>v7Ur!-*9UQJ#5w1Fcqe$+2m%`zZbV;RZ}=aEGA2cP*VTba`zhj@$XyT_MUeNUp7'
    'g*X9?Bmheve2T?7sxD=|OLD}2&t^@}VQbNOczg-%%o<_-V?|HzujlHiWnLq0R0qW!2VExpYgmFX+P3-JK~AyT_pSK+O;!D<DERir'
    'mjhc79n~r899=yPq8;QF5PEJ0Ee3F=u~LrHaN`ah9}llz?)GeC3bwXxQfk*WZkfo9sZ{Go&LY;M1*0$w^_3gh^$_r78tt`Fysd&L'
    '+5!U#<Ouo4P&DJz4b%>#hS#n=9q-*Q$5RS_raf+-{jv(=exzpWN1wJErqH|quLqNlAVrV4ljYCX?q&sy?>;3B_pO#Aq8Ey>Z$UR-'
    'SgRr*!)U0w)GU3~LXu%{s<Pc%SkJ+(cY#tcqnj-PT2RgE3fXF*(J7++4>R%}U|PlQck%y^cc63eWn)Ps+fG`6k(iO!`kiwGz*eZ$'
    'PFEGT*acdz<=!Rd^!&T-)!lJ=y+8c9>)C@<V`+UW&`BfZLE}-1>zwozdO0o=0+a0I#w~n$e7*aOA9<giH(*UY#aZ#l=s~+gvp=s&'
    'i3v!jjNV#-W9Mz8>=*0<Dcbdp>b}7<(xMR+5XW#xn`Mc%-y9`Va1knUa_XA0%zw>>R)A?oGdjTVI&>T5v=q~<^GhvJQz4Toq<DoX'
    'cvod}<E~uXPnZ$Uhu{6<+do}Qyi`G`DSageVl1!#nOYrLip;sw?V3Xtt%XqBxStaOF?_uj(4t04ho4=se}_~v#9!G_wlthGbmwan'
    'lElWNiu}FRvd_y@-}+fyy`Q`o1&)b!r09CJ1QrdIgl9IZ!G+XG@?HMWRpiI}`Es0o-}P}1UG#7i)h(|FTpj!!S6T@9Lld<GYeD9}'
    'OnVnTSBvA}Vcue2s#HT6CYVh*UAi-h1d6aUH-Vkyf-4c~)a?GA9}m;9`nVkad<oQl1wSvxwb1NH=;RT4k5Lu}T|hb+s0ZX&4I=Ak'
    'yX)5fi!!zQT2ZDCK{wSr!WxS{wR*WKQHgMg^hVoY_W{bT+sIQ`tvv1D1R0Z3C~R~Tv>>`+1g?hJ4M_}<Ox_Wo0$%oR!hdTJHLkeh'
    't4OKlP$2`s`Voc5r7Hb&KFKPUgiA0DO41v5aLRXfKaWs!sB#15A_7*#>w_bX$ceeL5W|%fQcG9uzU%)u`p3J~(kQCcjp!t;%5?8a'
    '5nv1oTNWw5MTI4FQVN`46>hIR?p(0<@jG<rS`BR<0tsvl99maoS>u#op)L%Ho2>;2X1@N9v`c!W=MH6v58id<MK675oC=sj<A#^%'
    '<<M*Whpi=7DcW0IzM&KDLqXB&5$8$2zseHE6i<LKbLup3{bj;X+6p-PbkaIcaHkyLj$2Vg$6EDG1SD&j;P3TGyFFEV7h8Yn@!SrM'
    'zr8#CCu9cqJKC-RnmW3(ik%Hci}-@nQ7YFxeB305tw8vgvs<=vc!<U?&c*o3ckAiy@pXLT!d%{ykni#Z;zB3DcN4H@*17Atmg<JS'
    '5{x(E=D%xCp>Cs>O82g%E#?~2lF%YF;04efSZYG&<`YDH52h*WV6R~pziU6=wQr;cOL{qcxqMBz12Nd?N0hzP!EsxW0Qx#~e0@Nn'
    'F_Zt!!!5hI_jGi7(^hEq7P4s4Pr3Szk&g$JV+kojwBkZ=2e5#L<hShM%i0dqlGxfq0mp*AKzIO5(noln3)`8g``C|IjP^Uux9lP8'
    'eeB_B-tjDwo2d-N6W22*1>BAugLA?Xfs|ox$Qb|<Q+vxkv__*Ee|*)0-*q_D+`USe(!i&UVu;x&<>%~SN7_Z*61P^<-*h-uu;%V`'
    'Z=JsE%kL+1H#h1**(>(e7$6xa7iS4200VG}Q<HA{dSLU%Cjh{CH~;){zd@>#%#fELAi7T&0;zW@{$Hvzq$MHWZK`OWf5BGb&n{yI'
    'ELNIUzdEg)GJZrJix`6#i#gt=K5*`CZf@U8uri+qhh+o32^16horflcC<M0UO@VLaGcuZvuL*idO1Es}dHC{3llC0^;8SaVi@5I}'
    ';E5_M9tZuD#zMBgsCcx{#u_OQquQZKH^u&!P^Qm2Du60#4zN+HC*C?5`YZYn10VrYw}Ns&=wX24Et@zUkLg|^c6kr@V<8inVMmS$'
    '0bB_9TgWfSN3$Hbj(6AY|7@nu!^@kDW_a2BR)QxC$qtUP?y^)Ht^(+Gvmm4Teo2=V?c@G%_RZw+Y#jx{{k(w?AS3{|l73H%Zxw9='
    '?Mmzgk`^{i9!Eeb-TokUBEg<+m*W^}NzK$Cstu1DNfPQO+P3sl%bm-lP7TissZlgg#Z)zUNddomBN4-=uhV@x=WWyE3yJ*g<@4$W'
    'aG$p8vd|%;Bs7`O<+9UH1cD+9#O;H`p%(}l$cJCFrya&#NF#joi15SNP?#nCpTJ&K{AsU(2KZnYcE4mp^MUK$%Le1UAYq^M(lmO<'
    'u=#3&Xf-Xu2lkMog>|(=8TU(e^pyVjx)t-0nd9h)aQwWOJVsK<5y%HsMf<iRxh0IL+V^hg{`l$eunTKxw8>n7DK2PMmrgdcx|00|'
    'Tb4bg8?p+{%X@bO{df+I#>13$9VX~TAh>HEQMc3^>+?pTqK7!nl86v6yOrMkq%<7AsiwE~<o$R%Y7#A{Rv^@6((wu6WfmD8e(xfs'
    'Nb`I5^qgMYRG(nG55wd0=i|n%h;}PnLCCItXA_Pp@fK&fW)%#JISAq?+P`d9uaEb~;WE^`1PZT!XC;cw%Lha$f|#=)KI=pWQjgG7'
    'HN|`P^m6<?J)CK?my<0RZm?n}^~zAo#t9EaBXk_{r@kb3FJgP+%^RBMr$FPMQi}h?!zM@2wWVyNenEMG=HZ=oVQ0rI1gEj93Rf)J'
    '%B|b+FQQR#_xa`JaaUjx67@}sl~=*5K`^MWJ`ob!FF2N5s2bj_dGp>4Jx@=E$30iSuGZMF3x!0~>Ps3`$sZ7wSE%xvJ4mQVm7MR`'
    '&^FCfk0cKV0u|+4$c$C8s%!QLBwBnUT`oja^?36KKOesg;`Dlb{N?q1IbP?^=|CBSg&R51ijfmm;@+UYN|@M8gt5~*w{(99sqGH5'
    'PMOkGiK=-N{wQRiSTkgpky=+s6}wRLh)C71*pI3v9kz^s!ohB?VR<eHnFwhc_EmgnOk@zuif9OGoo4UcP{^71%k7HL#C@0&2tJu_'
    '8fL590&n8`Aj*e(+AOPvRg|}G>BKnt_Kkg~IJ^An>ToIJYtE@`9;DGUp>6c-6*;^&MlvteY4)qO6@Nu#++oQoCGpzA$%=;)W-`{|'
    ')ItLJf_2_5WRjA*?0(U{mTh~RaEeY4N6|5~L=~=bnBB{~5pl#yXe7t|>75&jTXlz(HDi_tM+?>~G}M9av?KcH#VJ$KbC8mvJ(Rz5'
    'Hz$_klaKBN19DSYf#r&DDAlMaS?L5wukzq^s}?!Tg>@2#3ry2@?&^GhyguxFSUR?FS^2HIeNe*I)J+|pNZ>pmcnp1T0-MrXxAp1x'
    'atuzng!{a=jcgl{Jp`|*puVnx<%m#;Krt!+v=&=LIgHVpqjw++!N(2Q^71z}^4^f~3(Xp>L9NtSb-DS}6ivWn?M;pE<<^bdALrH1'
    '>SP{u8S$yYiJVpsg`{6K04@!*IyI5DH*A;vO+@Z@>?Mk!^GiC1?_F03*dY&0Tk(pjX^ux3h+Lr&;Z=n{S*u7=oxE>jtB87DzqIMN'
    '*@}n+O?rqh!Oylw0iJ?bj&Vm+sECVJ=n4+qx~DTN^4DY9-jX30D%iXoLJ|ihVYsjabyr{3Q5GZPQ0KQ7AXa6!cYc36!I4S|8>S-x'
    '+i6a4w&&E`2Gy4Q9y1NqH^}BUrzH=^XdDHaNB{1LZ83gx_Zi;*6kNr$3KfD=kixKV0@vgrXX1r(bNz8#bI4OUgfsiP5fv$F7%?D{'
    '=3z`GO5=|Q0uhbJ6jK@|;A6V^h6OFgu~zd7+53<hkkt@Y$)W!i3Ap2E`o|wo>`gqNDu=91%X@ZowuZQS`5dl$m$$<VIEy}oWhIN@'
    'lGa;a*ALS)dS2Ku6pc5hM(2`D9V9v;9Bz{iLYwPb$G(SI^%8Ch21ke7+sq##JT4BJ8aLl#>rFcEyE_UuyS4zcHjer7SGgjPT1#Fx'
    'o3)nC7qb(xm)rNU-tnXzd%t#~#7d6u-KYwy3HHH%oajSkP3x(HA^$M%qj~3!{`j)P;3K?4pe_bK8PEf#?&Q#z+ReyTI>xQc66;~Q'
    'IS=}yi^TPhK-0F;`!WmmP#=(W8DlRj-Gx1*J1eSd{?f{%et5@D(x1VXkB0Sb+fj@6Z65{?Bi_)AToToxp*wC?|4~APiP_zIHg#B^'
    'PTKpJ`kZ`w3Rh&r8q}8Xz{9v=5m$vl3=AX;S<3!>J38*D$Bg@ltSp$jCXtwVgx3Qwqap~SB7F0Ri0$o=XYAx9FoxsP2Ia7dWW5Ym'
    'hZcF8cP81R_?(iwwTQ}a2?^jk_HiZyPFs3IG&{^<K4ma`mO(6hC(R%BapfGQC_Z^g+A+OnE8p%Z5pW~VnN-Y-DIpwCUNV*@W17Ra'
    'QXq6nRP}CipZKrX%yxGW02XQ?dUaoQ8wiYcCDkhU2gpF*mw1At@g189dEth3N+=8YOStQ?^{dM;+nZt%oKzV*MglhQAQ-3j?BXTd'
    'I`4wSwTVS3hodE`SuLHCklK%~v2X{m3!)^*OvUq_*!wMqNH`%h{u^db{54qZ8LNeh-fI|oCf=H+N>#~p1ZaP>+?;0pm3!W;jm-@q'
    'KNoCzM9@2O8SK=Hin&kP7D`Sh8R!%4^tW7+9!zK^U@0e#?S}YG>y7(h6+;on@M6O>hCjI?eam<{5N8?I{@m*Eo)yoV!NL0Xo4swB'
    '<Phc*v%Cp(sWn)KH`=J8>LqqrG{jgK@25QAlb$57fA3GcfhfBTT5!BIk}&U}DOHPg3C_e~LWg6~LZe$~G}KqX6+hY6S|aS;6&d^#'
    'FN-xW_efG=on2NQtYM2VveR(xJ;1iQc~|G=$=>})g+Y`f*@DhMeCL{Pm<c%ggq1ES%?yLS^8Duge9xlXyD3Ruj2n&W2}N1gAUp;`'
    'njRm$ZWz>_oy`^L)(<xo|8D=D*48%;0C_k1xWp822=mG!G?J)`)LBr=vs?ExJq^#F*+M=XUxsb{H&_XGrVkAT%MSP{5_#Ca&e&n<'
    '1q56LUvULL?%#HE#w_*^2lB>ZP^tNErvF74kcAp@DPK2GRI3RQ*Jy=XxAS+{Y3HWGR%phaAgIIpk4b4P@iViO(7IWP%9Kfxhk1VA'
    'rlK0&ZP&+VrCd&?fs*4e1~;aUrB9|vZUYAo-B8)wx}$GM%I*y@b}hz<@U%{Guf`as%z!kxAPFKSp?@z+zWKey!x^4+yRV3k>fJ(i'
    's1~ln&%n4+>6d<~Jhf)fuU2=j^tbNlTz<-@UO&aKfDI@f%7n{q_Eor-u%JOsUSbq)8I7+-wMAk@DA~MwJEwNeasTzE_ZF_34insI'
    'iEGZR$<R)!c0h$NyM&7}rg!da?G5bRQ_LEyL*b=2N9Z6U(^^4UP>ogrh|46q_J`wouG-V{=hv4=828^Npi==U54%>>u9C}=W{;Z}'
    'afk{^u|e~pc-_6P^G4RA{rna&r`Od;`UP)63U|1ioVdLbm_;3AkeRi)hN7Dg-s(F8U#ca%<NE$RJ35ZPNt#rt!X|F<!@OaH5r#^1'
    'uJmZk`ElREZ%inMhs~jZB|dhyT$3>UU{8Phqs`RPL{V?53ln=zMhr3_Eu5C{B^lMMZoi%)3hVwICAQz`L$u=MlK-AxUPhx-Kq!<M'
    'P$6_Y@{uJ%0%WWMevfhevF`Yx<;u@CbMAMapUnB6&h`A|t%QDVahI7#W$Ii|NR0rkn6gMfFmUvrQERWDJO5-Wo2kDG0>Xk>9XcO%'
    'vJu~!sEGN&0x!a64P(FB|6RQdBZ%@$Fkb&Y$i2@S%+?qm!E4deXu=r}4G$u=1R;Py7!HuOa!gZt&n~u}got7eLAcF1n#6S}#-$Z8'
    'sDwczvsctaJ~`R`H2QQj9}e*W)6+rU?uV}{>3TzB7Chn@z|Byu4oa_zxq&+&Cn%u-@3q?f3NqAbAEbQ4)7k3oq$1g>kIB6dFe8cp'
    'G?s9LfoUT^Y3}3CH8FC&?U(De!J7N-X^1TF?o<4AtB)S0w-hyVq{_^i2qh5LmMrjELj&|@jH#CWbl2~~fB(E;#TMQoZOjG0*#%r+'
    'hKvDI^l{bT&yxM>Gz?91-QuTL5XWHGd%&uIGcut=T4Zg)n^Zdr3mlJ;gL-Il4I!+q(8rx+R-vCc*L2%j9;8@8V`kXcucK+1nBLmr'
    'lf*@x>rb)Y5eVz?x=oy6&$olH;XtR*PJ#S}(X-JZOVIKZ+<aw%ZUvOa9mu;Y&!fH*r>A|=z&xg-%vy0McRaJyu?W;<G<kW?ct<TY'
    'x`AQox*Z^t4C}<n{rmu8V`M;~*%ujxihA$vb|MvVG6qaA_Wz;j+{JCIl9X*J$e4%zfQtp8P7~Jz0<xM~@P>huMttzToR|8_*KiKe'
    '-#vm|7HYgKve1ThF<CdlqY-VZungvbvKjnnT%_^JH=?IC3YGDNZY)m&j>^yaD=I7?9iYR^FCE$`C^c?VrWf40u3P@~Ak%w!**J`}'
    'Y<?Zj__!~@VERQlJt*f26qX?MP661J^VMrV|Ld^TosJ2)K>}44gff;rL@;(^Dw9f&*$C)64=wcWwZonML~HsI)+I5wAdP!Grz$2('
    '1?Fp@>k=3MccnWs1m_Vj#Bw{2847jr&Yf&(gG^Fm0?-v0xZy$0NjE0Kq6`@uwR&$+k}cJE{WfCtGuLY;wZf2}o<fScF(y2NY&hS!'
    'FTyAxEWpaZmmyDAyqu5(eFz@+*T1C_eDad$wL;9Bd^mo8zK<?875^)vnPZX|s;)rltHE=k)NQKUclF!xu<9ySjmO<`KYZG-WscUf'
    '7J0CT=1>ZRTT)!~IhC;7E9_tl!76Uw(McDI?V-&5v^6D%rQQ;QmAU*0S&${3VoNAsg7mGc7Bd-)eeZAI4%Xt4g82OQ%wAZYP#ZR&'
    '938!I$t%myneY+Q-E-NQ!`8*Pj8L)Gyh*kSrW64CI;v^VzWQ@xOcd{mG6HBx9@O$!@kWq2oEh{SXi^q4R*NlIH2tYgTzm1mEC@rH'
    '9XR9Kab|hQV_JaC+F{MMEi1r6Kg!*!`YblG318tnPI*i~nnS@@h6R2eyeN06uT;s*w|}ctKew3v&8Ul8=kHsFHcL=rBbDHM2qi$p'
    'Eci;yhG-HNU}u<NjrNr9T>peNZx{r|bXAQlAY2a^33q$-3~#78Iu#x}iB-y$ohzOd0&i;CJ-s&55M%@{DLNBofwX326WJr(S#)it'
    'V(m9==F)FFI6jeWK>aqSj<qpZKtUbzl4JHJ^(5|ly$Th$2pLCZ1ny?W_HEgJozlglG-=DOoClqbrqL571?aqTq8o#4AIt%r#Ux=f'
    '@)q-T=h7S*d`W*j`e14vFTZro2VD@MV%+x>Qiw84@F+!KotP%jDMj^s-3C@6&&IGTR43dBJ}pBG1PLIu3fH+gJPLE{07KD>Z0{pq'
    'CoXRgQRx_!V=>qY3@AwP-Hf4Q`Y5(g6NQ-ix+!Wn90M_pK>g?AbocW5u;r~5svCC}v=*_Pj4Q>EP8w<3VOt&}rl^CaP1$R#yCQ4x'
    'bhpRJ$?)q{A`!}nB}P)nN1;_yNY&AWnBT_qqHNEqUmqr-gIVa>X-^Y;It0K8J4!{?#YAoEX<fy~tSoBTZWof{9gCm+R8RH<ciZOU'
    'ZXh>;KF<&ntBXL!P<(wtI(Yel2B;MiLXAC319g|L*Zp#<)PbI6CLXywz*CDPkMFs;UDTiJ>u;(}dy(JL!|&|PKVsFuVO$#<K6z$l'
    '7-11}pwN#}45FPP!{<YQ;4+(`=|kR>G`%f)niC!)Bgf#REr(AVWq%!0b-;nB<uD&24>^GJBU0@Mo#YHGH>RDdzuA|+&6t)7eM%co'
    'o%jCg>PYRnK4Q9HXc*t@I@}$hbmAwqV83$<E0ObX(byIs%hw*k9_e@pLYGKJouR70ze`SD7RAY?{P1nXbE|XL%jV3e(L<ybqoHAZ'
    'o_7jZ12u;25X(K*rayFl{`tyRzVV#)LB<K-A}m<ev8Y(RZi=CfOr=@y0y(#I*KA?OGpDTJYTzKJHOF*i&^ajpg1yS3sxrfS3ctUN'
    'Wxp6FHtaS}Qz?42uEmN!fxqEoSkP0+h;+Kbs#6bj(KOv!^f<qUt;p-+50$^)|IA*@kmAX-SjXv|nE|{67b}uMglQbhm^HmwF`rg^'
    'UM-@Zch#kgH8rD(z{@lmj77-tcv|lnmj=1WNa^Uww&UJ~A4AD&M8k&CS<@hx0)6x~ns6OLl9UNJ$T3laxQNha$TwLQ-<DlF;hTbQ'
    '{xwj0Jp<$=(UL+f&^pP83Z@+bnjrs9o1E}(tFC01U4Aj_;c)cZ6dERqn57LTX6#i2N%juf2y9q+ht)e*j<Vvg&8=?2AHg5>IE5%H'
    'g-kEfAtt}!i|G^Q`kUwd-bGg)&70VUx-H~Do6lVKrB;*Ku>ixlG=~Fwj$)gdQ&HV=ZBRqzn?$;|O`Pd7YR4^wZ56<uTN3t4z(TC4'
    'bFO{gL@(c<<M{cC$@;o=S3Fj+{J5d+?X+ZYyx1;w5xc`0$N^&(+lCk_Tw)|>^Uk&3RE1Kq%gee5jU0-}rFxcreeg~~t3u*v93Ndq'
    'P8c?KJC|MVziv2YnR^J+hOrCC&^<X$!%|uMU(!2Lp%Ul93U)4cm{$v?;rEMyasjAo<HykKEbs_DmM%)v4zTNK4`DYe1>Ad_P7Rlb'
    '^r~FEoYBM6p<!T5?Ozo$zrXNHrrtIt8+S%YA;s>8y$k>L`sMN&s>9YWW?xgO=b=U5H%ZXjL|z*PjJ(KVeoM1+z0(k~yXP+uh>H(c'
    '7iS3RXXqVEhE9!nz<r3Dq{KNWF5-q1VA;Fw8~t|s)#gZc0R%9z6f7Mg${1LS3Pyws+B&OtGcKm9SKb+^e6l(xSO>|EuA~@YR9b3('
    '8)<}TOU_NzxNQ1ie_Q`}{C%U3xi)KE@T}<j(BF(i(|k49)MADO=htYDYHyT?dFvaBC?8EYBok!2_=wf`?70EJ;Ua|;R&|bdUF}`('
    '_5S6s&MCcI78<=29<)Kr3jr@!t&bLd%-;mYGj7(dDR!Tyx51ywVEKK@Pk^@2l)@J}AmtbZg-KwR3YR_JTrdb#GuUV64!(0p-nG1O'
    'M$#KzJP5zsRKt%p5IkU>+b;zQqbFt(!_MW;zQ~-_?_WM|paCKF;7Q9-kxoWel2wxWRD9Nl<GNoXvXiRpT=;ncFKvKIFnf3HjD$Ib'
    '7b?%oDqsiY0S1-|HNs|FUbCQQy!qkc9Ylu<dy%2OZ%3=m@TMWW{e>-(Iyjr_u;0CIFsWd9I{<31VW@SL!=UIk5QuOZ7Qr}FkU>#n'
    'TY7BvM(J<vMc)}wUH<9R5L45}EDxWulT4@&9S5B{<BmFKjBtY8dk3E|TOj#YJjdTRGI+s|Us-UoKo2pmN=|8B`69^JPVgrAKkUt='
    '&;6J+ze*dj*D4GJ<sMBq{%KgLy~ECRC1?^6ilPd}w6|nAHMuYUR?n0@=)!f#L?kt5;MB%&N&!6F$Tt8$bu(YJ;vLS+#rqHf%U6+u'
    'c}(XuvchFyc}&?NDt~5rjm8~$*>$U)GM>ZpafhDQkRa-BKd}huR2z(*=nM2JD3?iOCa&h8-2J;*mz~zXocVCSQvz}+BmMM2tzXqD'
    ';Gpl*xOK!$&z$y#k=Mr+N_>3`Ld!-+05RKRWltPVe3G2nm#tRN|A-z5Bz1|{viGJqd1&q{8GNPYdX;EoYj!y!Lo?c#gU%9eMWw-a'
    'oGkmj<;ux0GK@r@h8^zOrXvN5*g1|_0xMD6-Q2`%k`Q6!D=l;0$_%IiAO3tgz2T2{{>s|?Zi6(_2X{}qnO?DJp$*Jj*?6@vk|oL|'
    'H4OD&e$B#fld8@mM=l?=I;^_+(z&Vd&;49TKzJQgG038d@!;ZkQCzkD*{Oe@b$ys*dGaB?!z9z;Y|ZEi>T4d;Mdf7^eRjU-*7vs^'
    'oDqrp@G^g5{Q@o6@aW`w(-D_xh_JrHlSZV9Baz4G9!z0~+t_S!6aKb`T?>26+WTXGZL~FdPN-Tw>}av-5pfI(o8xk-u3k9)(;L(f'
    '#v1TU84DJp5}64pNLPD`G=c?C5Dd-5*}6kc^J8`$wXn`H?RNo``jnhFLLxF$^-k);bGyNQ4(j^GijRj!LX@pUOz9Mu%NSE5s~AwQ'
    'mj8xh$V*04#b_gM+Z_F9Y~}YCRPaWq5;RS#p)7-)F^9>cj=5@Bh7G_3O>Z^<0tLQuG9f59c-fdv&_XPXFaw(6la09&L0U%r8aF?h'
    'lXt`Vt*pd=Q@?3L*8`Pg#jRG9b^7(j(VP7shT%R6(Lj2UGT-zYe%7M?GJG4z_~Gqmf3yADJv5QFdkBk!80}TXSX(FvCz--T$QVIT'
    '&*UuQHXC-&hV~3qq+sUIN<gQYrzUD+XoI>>S`1I-PZHw^@MVg3ZD-#h84ZgvlbIL|ha{T&5I5SrJY*@QO~oBkZtAQr?_?eS_&6Lk'
    '<`L$zNn;xQQHT~13DgES+{w&N^KpWThWoYY8*|<Yd_8L4J-)dH51M<x1)4{#A&)K-f~G7GhB35NXv^YIJxu!+eu>JL*xpczcnX`P'
    'iMH<;KEXqX{<WmL5dD+rnatv7_91PU+udug65P|(o}Ql8Q52emTNb8lun~qvgc|lLLGB3EG;=joum=u!mUL0WUa^TQDNH?(nf*Y_'
    'n^c?y+Rd6Pi^`=A2pZpwY3KI5h3|Lp+iPT2dwzbA3{9;<!5Yq2m=E}U&V3;NbLb(XV{V$jHH%+y`ZR(2U=^(#&?sTDkU{$d!)p&#'
    's#_QUZg<7%*BwDJR6$7LKup9mvgFSQh4N4oG%@aa0xB96v~|nlp)Yse4UFGEm<TH$Tw8_^9Ieb7j|n|`P8p4QA3_d90Wjcn?FP;%'
    '=B`<&zzB1Xr_jDlC?OJk)5^NY3~+yXeJGWCu{jv)XIt1mkIDzohE0tkS_4FafYS!um3@sdMWI^9kmT2HWB)AHB~<s~jsHun7^XuI'
    'UJw~|*Bsp$Za;POXl~oV8%yVMxnt%QS_H<Oq?2^YDB8fu(A%ga*x8iP0UkEdn*Z3szV0W50IQQ?Ojw-8pSl16zaVG}L!h-LgP@#m'
    'O3D9y^}kabR|Axd)EjCN4m~D~0)i1mw8-TC(Lf3v5B$!ZSWWNR#tx<>E>zx6s%^QjX1lkKwnVJW8!(R{8YUEjYrFhi``A62)p!-v'
    'S0C6F3j_{NMHr;_kwR<Yu?bTbFJ*W2W@19?-M*1uaXIj5Gc%cXs{@UT+F~WEO|9EXbrhal?(D1gfY|epK5dIH;kBNBsM(4zo-w?{'
    'G&OlVGAx4#TJ^F63~iDiez<|>@Uq*wFLdD}MWVXY2<gKQIp{4ZOk!DAn(V^$ug&IbL&V#3&0SLjEz_+ci7d=|(@H;CXEs6H=vkUj'
    'e@<7Q%C{}-o>q&=wjkSAp`}qbw)J|At9!x{I>zYg`^LPT8~5>TFzhaeb6jAfkd`9GXcyteGe$Zor$7SIWyX1nA)v)@?Pg9red)!7'
    'lXMr;s-8AFgss#?F$4JqG{Zji2B(k!WHHWp7*J>>R=4gWhC4j08J3G`bNr}YdmFP2=R6CeGj-@{P1`h);x6sleV;b_!#~-}DZ{p-'
    'haCz$oUBDvqp%1Ee6L33g>ylXi1>(x;UvKX+WfYy>|u~|Fq~otBENfHc&<5B=oAL#s4wRA&M{pZtaxqcg3xpJ+UkTLZsCsWf?!cg'
    '=+$!(Dz#o*bh_uLMryBmx;AS3U9@nw3-}oc=P}gag;>S}E4m{*uF3!E_+C-V1#qZWedSj68D_a1Oo^dK#Yokop&aicw+-80>V4nN'
    '+|=c@x%P5@`1ILXcs*aJUob;A1P$;Pr?8H;s?i59M9Q}uGSmhm+r$VBjUWtPn`M0pu<s$PP$T)hTb_KbhfOtyAgR-=(F|5^nTo+;'
    'M6p5|D2f$PkIeph?N&r_#D?MF_0cg|Yr*4j*_h*|kD!|*%|bpx9!1vnVQ{Cy_Q;S+^hwKUzV@M*QTy<ttK@HeEL6WbtXH9u9zAY@'
    'o)%L%p676GZQ|gk7n>;Wzc2k=b7OrW*O)<PF-<Nc{4vsm5vxufr4RaUO~S9ICa&|?9IyRk5y-D&j$?I7c(PpK6GKBvguNJ_=FX>E'
    '#A*^Yf(}#PzK>1PnE4$3$C!5}PEhC~NUuxyxR_w3770!y+St|iNNnLM#Y7oC&yaTp&v^_o;7RN01SOPmcTB)tj55{H4g0u4L17Vy'
    '47ahs#VTBOgl98~GLf^3SW>O-KiPD{E_P}e^q%yS<-t^jS`dcq`ajClK1x=m1Ev%4{<ykIJ4yWR&XT{a5)B8cC*D`1LhXdp*|4qP'
    'KBJjyQIJIDbwXggb`RH)uoc2QS40b6rkfS@jnpz5f+O6-NFo$)hvVu8Av&yXLgyCg_LN1Ac$n8P69}SAn93u-Y{j(U43XUo;SG27'
    '2Xf7%`6*gan2zD4Bsk!pfs-i}F}D@UF>$!6hpW@y^A3EY5khwjz1AouPD4xAqQox|&AE4(<UuJHHfOV{P1~ioZ6lAzHKe=Q4%6=&'
    't`h(ZwAwhOA)E6C6sVAHtS&`U%$#3>1k>HNk(H;g=fz}_O1=+CCeA@AX1|Rz30<7b;N&EzdrV!tHd;Ky`hhJ5V}pEvAM*1CdZ4qI'
    '#neEoMR%7CXr%KWF|HyH-EPqQ#;ZS-b6@qkhBoyTf{0>ug04mjH>mbl*Y?%KXi|(v8ByNcwwG&L+l&%H&UugxGd2VyciJFiYAGx+'
    'eA7+%dKc|@+ip%=nq3>g2}4S9so{ddG^!N@UgxT{;iIiLl?NaG>Q}UiPS5%IPVp&pL7^DaNn^Y+rs>$!!G**eAKbh=xICR^yfzhl'
    'JWR)LJJ}Aa;T0(jvrZ6fiP`9@J)k^zzhy`jc)6PEHr%p{(|h@pjx2Px$e{)q<GnCAF?fS-5++wD$q;UWUoQU$CEfOri63s`98S1*'
    '#3+Zu!xrXZu8zA^LrN+%g<8UW<KP<oLxzMNLd>C!m*4bA-oE84$T4~qJUi$pmMjL9iKmLEDi4pNd`SfkdImecI&WXM^BswHH$;l_'
    'rkGSz%Yih_wDBhQq2UrPU)oFio5FVJrtQ2rnk%tC?U7BjK|u)WwtB9{0x&W~KvC{T1r8(9;nvz4Zu*AK4Bx%aC69?HL&iXl5<)xE'
    'bqoTULlCJ5c4)%ZH(Rc~l>fSaLNc%qr(-3kp0$^-4+O;!p~Qqp+Uu~)z^w!1Vpd(7H+nl`TCwb?^NfYwEGFXW0SIBi@Z!M*nYfY>'
    'KA~bGJ@bx0`!ZIitFGV3%uDp!!|<v;9ag7-P4<s3rjBU^U5L=}C%rX<S^8C=gx=s33beMlc0>Nl8F^mQ1p_=tBr))#4~euB8#4^n'
    '<G>i6VwxsH9P#GbjqE25$4Kl!-#4iD!W_q5{5Q0k)hY?$vX)>|BU~Hh;B;q~`N=f*!Bl{aT|^l16$hYB=s|b^qzRji3aOPGGlD<u'
    '_?5f3K<)iondzqK<Cd)h(AVr}qsHj9=F70UCJGEUm*v_ICF)zBM@*vJn#@2mJ|i!Q7%9w0V^Rjc`xyJia#KoThB#(kcP#>PX4&4I'
    'rLW=svr*b0Z99uy_+vpRs~{latmHA68wS8cIa<a2mD@P0_}_N3Nzl<l$nn<dD)@%M$8e`GOpu`r)YTe=fNgksdHpsx=!U*qet4?0'
    'E{83`HmtpvC5ieP-s~7OO$@O2&0;UX=X|uywIAn+hy0i}Lc?ebyKY~YVrAxQiJQ2<?4R1W<-7~<oxbc`-L(2X7IYVYsR^-#yd#_x'
    'S!T3ifu1>ZQWw<zIw}0M?_sqqJ6V+MfwF^~vp9&HfB4RrStn!fV^eCqBBp+#p9gJYYZuo=q%kajO;SkS@DOvAse-8}E1VhC0TP?i'
    '7GGs+)o<Pz-!7^1e4&kzM?<jfiTc?_4Z2EtSz6LLeo9Efi0`MkyT{$D?{JCpabpDGP__mwgZARZlhAnjNZ}0|4T;r~HrY9UnT70+'
    'e&%X6s16w`eMwU5^OE`38r>MJ{Ah~cW4CG3=Jy<Ces=Hv%{#(`Kd{Y=dS~uS;f5sun_@z|rZOEXWxDQj)9qVvcVJ_K$O&6hOdp2V'
    'k;`W0gJ)ERg3Dz;1$kE3-Ta~JH@q(gEYZ1*Xz8lT4BQ^knI34J!r}ZPpBWApCT{(%6(eTtQxXuk<CVEZMp(LRQ_|O1i9u|Ph{9$l'
    'v|s8?G4glI?uirzz@+edY+{g)`h-WYA*pe!AwVSW7&TCjO{>Z8R>et<KJ*6t*`+uHc|H$INkiKlC%PvwB8#~&td-2}*{oT=TXp9R'
    'L6eeKJcWkv$<kpa3#h@tl=W=ZjW~d27_qX63;)N$J7zfH>av&NBs+C6X|=%~Ldh5)1+_xC^9E@90SG@^`c#X5_&#C(@Uk^;US2E<'
    'iV>ZRDj-Ki%;bh+O>qtI;TETBUFDzNh-%8^`1B=uhGZeb{n!7op+5o>m?N){%S3+N${1{K(lx3>9zkPuertYiW&8blXVzpOAX_H>'
    'Tth=;!pFY@X7k(=7399s5J@s`;i$J4u54E<d&c{>*N%>)xr`}39Xdkom$2=x&1U9Mwj@}yT{u|RuKfmX@7MyI15X?cPZgx^6&9%`'
    'X@*+@L3RpZMv6(*KRwl|o|o9e2j$^nEbV{&_I!M}@QdM}__&xxF`R^;uMeMjBF3Pd0lw%67d+9Q<~UaQ4JqTp+UA6^{rDJvfA?fd'
    'sHw244736%RqLH#@`izRC|1;NWk94q=j6v6(DQWd=MOP_^S@sHe7Q7ZsOTYPTD-F-NQ|K5mQFWeX2>6mu1Mr4elBGb0zbU{$R7(b'
    '{$>bKgiF1~ZR2N%#C4==eK>+k;b20rW-X)CUs^5r)bURrR;+!aD@7}g<iT!Qy`WQR1|r&?%0Zj3#&w4=aEbqE-SjN4`hd?7y@hk('
    '>QC;@e{%QDwBU03QpW&elos}vyhMy=!*MW!QSK642M`QCj(_*FO?>;kPtlis+75)&)hdDxaGr<2N3y~<k8r;-)I!ZZgc+3qdp|ls'
    '(Q^Gb4!=96-~M(Z=!T=b;jt<J)zCnMNwVK!G;zV0ME*R4xP7%_t<!MLm;d|tf2I319{iuf%jXRY*2RjSFX2`Q1r|HTS2+*sK)e9R'
    'z3ukL1?g#ZO_J&Jhci2a81eYHS@v<5Wd@1PrdflLK(B#`+DFSZ$ns1YU2Xxw?p*Wy*9}IU*d7DzOl~r0K7ej2G~*Z}+M8lYV+)M='
    'VP5$ClBX>H<I14hn7(alD$bk>t_Yta;>JPJf+|L<6#gazDLAL|zV&8F@Z|$ru3v{rkyjgfn)W?UKpJj3PqHz-{aH{yen?6C!Fr!w'
    '%~9NVo@GBoR}|jpx|9i$p<$ir{*hQPxeyz0XZwBYF-Uva8amp<s3eAeevr}TqMzp*V>%)hj$>HY#z5HVr=R3>_;4~hc>ehLurN1='
    '+nwgNJsvlr0Vg<;RKALAW2uy3-r)x)B*EliikQlR60~B+(y`VyC&FlZGvOF_hd(H*4i1Yz8PZ(Mt8xeh6SLI%hx)1iSnz2DlDCYp'
    'LtHo^A7|lP!c3VO7Y&yfmN~4#4J+2&Qf6t#im#8G%zUL`iGU9D?1So}Ehny5(b~5O9tv#9R8rmWv(@Gl2HWV(UnRJ{{^xM(+WaP~'
    'aQ`BMkouU33Rr0fRNO15-gQXLDS*A%{Hj%rO*m}SOk=pR>qwA{TGFkd1TVuzBW5$<b(kbq=UKXH+06@V3K_q?6;gEy?g|5iL7)v='
    'B|vK%%($4^kzcdusTRL{n@}4C>>qBvhC}#ZaadH0kTk+$i7(!&K4<o`W$}hSte?k+f4+h_mcwa4^NyE0gq?B}he6$!gXN4eaS@`D'
    'P>Pcyf)Y6zl-I7jhbBU}z|}@X5NBEL;f64Nkp_lON+@2~E_1IcuKv}Zw*nI=X<Q8(us>p0Qz*>T%6KzP8NXK+ifh+T*DkzcZY{(('
    'N>nilX^CRMg9mn0;dCdJVH_&o4~qCtmwtYJO&<_oWG}0I<KxS)C0D2so}D0fs*DLqs|W`HN81B;gV$WpvhY6ccdfa7$7vU!Q&&UF'
    'n1L{0h{-#Fa;RBdtstGk1tb^VwcMU74&;iDX@ZMs>kB(w@yfSE|DbOI2^jT>TCPIf&IMn#GEXm#I+n*jHBPwtn}zCGa$JkA*wfTU'
    '3^4YmNzoZ&IOW(oaw2<otGHm?;Y-+%GdBTpDD%aCU0nPSl}5E|xkuNxVsK-)Lb2-o=J*J>T+HEck@;tHqZoll_|3yOx7)SikK6(N'
    '7U#`*>HGpTY~ule_=xxsdzf8?dkZDv5}5M1Yq8TPpbZifsZ<}snwdT~m=w@#7{1yzN<_8*x+u=;Prrt9Tz~uPp1FQOnx?S`EVU2L'
    'tV>*ng7pHFRZ$jrue}W2&zF?{93q~6SdYu|n|a8FRZQMRYulUCmT*iwL_ggBVj#>_7RE7-ZhQ5rJH}zqba3csVlV=*-b3avpie-|'
    '2VfY2JS;E#AqQh)X-)n4xGY;TdQPppaAgY8zi5Z)^AAC7@3fK!a=tL`pZBj$Cit)Cpd3EFZg4;i853y{`*=%N{H|tIq1WrGk)UY^'
    '5rG(4zJKNI@L<fDAWrkv@Yn)~VILb8>HQi`jIe|?HikRX6~A_}&Oh%r9x+%70A>_q8LkQIj6HnYpels-r1=0)_O7~i(X(uPW5_AC'
    'pj?U1rJgGv8dK)@<*q{!gbLt(%w=w}E1q&>3_Hh&34mB&p^XQy8nrGfbG`HkrQszXvx`E;J`DR8hdt^Hy$mN|*Pk0ua{yya+}g;*'
    'F?6ykInuE1m9-(B!<_U7^X`h}A0EHN%Fkw}Zp^Y{_%mcNx-E!!hIIuCZ48@4_W~N6HiJ_L`rg0x`8GO9>$W5iNGOKc#xNH%lH#h5'
    'sVgzO%k*@&zT*cjSoSX-e}4BZVLxnfXY0TMq*7=wRXl1_N7ysS*@`Im_^*-I<#pP>e)v-^_X5jXaQm>bG(Vn0+}odiJc)BZp3{ZH'
    'S*&{4*Jd-|Pl}l&vuI9!0UBD08CNBuEpNEQ?Z6wY+yDLB{;T1<bL$PXnZ^~Ghhw2i83Rg$(dc;KD|73RNxQ_#9a}%SVE!bS{>?^S'
    '#^|!jA>Q$Nc`%uHLfb)d9{S!Gc*XZ>S6mB~5uN7RaoCRHMGB|wh~k{;r9^(bR?9$*=B)e982J`Hvwp|IyTLa73U^UvjIP8h%&wIa'
    'F^)|p7Jh-Or&Czm{uCOD8Jx)gh7HsbXqg~vk}94@0D}+=A*i-EDhO>;P<dqoKaE%?H=z$>5JQHiJ->@rsZJxLa_9iDiX6FR^v2ql'
    '@C<nhGQJMVPxJHVr%&VE*3W8UNP4h7jHcm=FA7M|Gff+=LBM~v5Cex){`A8N!PSQoxSp8few+`>Iy~{^u+ia^xau--L8I{rhe-)d'
    '7=y7>4G6(-R|y^%y4bt$W->>hNf=v2<H`A~Vp1eZ0C+7}y_AXiQh`bBUhr=<^X1EKim}t3pVl)g$NeDZNHKaTz;AaB9+aaxHG5ay'
    'Zsd|X;-LaQ_<T^?1v^2%u?W}YIVRVJ3b0&$y5PFjo8`>MVQrplxRkog)m8?y1(&`ENd}lU1v)J1kgHQ{@Lwu+E-ALYbr&yBqRFTk'
    '7$<b0)$)1pbYvvp7T4Zv!|zz)SeMzpMZYPKFMpLJomosVhj(+92@-agR>Jy$;XKGfQwePv_N}=CYMISWmxjjxI$&&ACAtOyiDuz~'
    '_ss8>vB=TqeG3Kx{UxH^<u&IprZ5SP)}JbnIx-4B#U);#2P#7ebDO2xx#r3v-qU!~8#LeA;bG!Ni_nLtUK?tRmkWXs6}W?TOMTtC'
    '8-o*Q3}Swh6Pzg60UjJlI%;y~hnhwsqgTf_*DZ;oeApm(!0u=rncBiDr?w1f9iJe^l-%HX2_hhpK4w=g`<B&gkYNRPHc=ib0*l5}'
    'm=_Q+QFR%ojG_?T^Qoxzt-T41kbOHxz{xUt8KI_x;Vt2(s{vQXJTw%veB8a-CSeFbK*O4ct``ywCTu3zBT^W?NASO5*p0ct)m1D0'
    'XmZcrA$RuTF{sB_LE^L$r!Nccrs<+aC8OGDZyGa`?_2a)`Z*pi&!`0185-CHy(|v!+D5>w4r((>SllyGqM=`|TJdfZbtV`x8c9J8'
    'elQ+N3x_fU04>dBp##bT%l1DWQn|70F1D)TsEJZJ(lI<NmpLFt217Mu8dZ#(X8K<Jykq_2<yXzc1`AES0S=Ht=rn*5VK7TLjcS<-'
    'R&4|+f7)EP?n%+G5&xGWK1?~Z_+%;)vLUY%8YwkgOuUZgQT#kZ`?rPHG!%#PtVi0Q3emkrkD-mBek8Y~ds*mznKT7sDTz@uFgx$M'
    '&FC)<LIt4sK(Cmi!<d(_l5zvF#z#e>pjlV{rxyHw{U84ilb;;a'
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
            'protected-producer-optional-parent-source-v1',
            'protected-producer-optional-leaf-common-v1'}
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
            'protected-producer-optional-parent-source-v1',
            'protected-producer-optional-leaf-common-v1'}]
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
                'protected-producer-optional-leaf-common-v1':'b29e0558dc69bc9dd6fc6b47bd6024382be4079d',
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
            'protected-producer-optional-parent-source-v1',
            'protected-producer-optional-leaf-common-v1'}
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
        if installed['name']=='protected-producer-optional-leaf-common-v1':
            self.assertEqual(future['.github/workflows/project-tests.yml'],
                dict(mode='100644',type='blob',sha='f4765fa63bdfede51cf6d711d24a952c5d0e0316'))
            templates['.github/workflows/project-tests.yml']='tools/repository-checks/workflows/producers/protected-project-tests-optional-leaf.yml'
        self.assertEqual(set(historical),set(templates))
        if future is not None:self.assertEqual(set(future),set(templates))
        for path,template in templates.items():
            prior_callers={'protected-producer-original-default-v1':'81bcf1933edc435826e2de411a777cccd4dec7c7',
                'protected-producer-original-default-boolean-v1':'15d1b9ca9d4b58831cd5f8226efcd47681dd3e8a'}
            if path=='.github/workflows/parent-qualification.yml':
                # Whole historical recipes retain their real Parent bytes when
                # the separately preregistered optional successor is installed.
                parent=('987d8f0d198e40211ab0f33286a55852e286c174'
                    if installed['name'] in {'protected-producer-optional-parent-source-v1',
                        'protected-producer-optional-leaf-common-v1'}
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
                ('protected-producer-optional-parent-source-v1','7b0703d88d404f38c1b3dec92f77f03586c9144c'),
                ('protected-producer-optional-leaf-common-v1','b29e0558dc69bc9dd6fc6b47bd6024382be4079d')):
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
