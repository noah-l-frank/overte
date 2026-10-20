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
# db744553ba43f7e1f1aca237759805df897dd229 / tree 87a5cfdb6c4671f6ae52804180155435f532bcd0.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = 'a20f0db1684f862f995d39abfa25516306f4ce295e15a379ce2e7c2542565517'
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
    'c-qaq+jd+>k|p>)pOMeaq~9<76|-i|JC?b-IT<2=Kn4Pm*uDDSXYUgMiYx(fP6X65lT}$FL6*#pU(EJ4x6A+h*T28)j$dEeXL%fl'
    '{ce2P|M94YPsf8iK2JUT`?u%)<G=p<|NPg(e(1mc`@gI)DTIIhw|_l<75vsYWAUG8UFo*tSH|W!)wj`OGQHSo{2bQe|Ka%kiT{Fj'
    'zi<EgU;pig*akuU>!+vv{jPssk=B~Wzbk2~*$mNMQqH}pG1*L?+AuSxAf~)8?MeDK`J$ix*dM;l`~4rEz9_y{j=TNi^NR3MAy|g9'
    '(`w5lmy{;H*M#O`OuqP_&S#t67k<#E{qyd)KYahxziR)sCNcJq-Nd?PTjm&5RqKplnlLIpv=;F$XbbO4JnHlD)AP&jsGo*D>EqDH'
    'zSC8?qlJ;WG?S)twuNK^KDNmSaYSsYI9HvxEppdn<<^^RHRqb}Z`U$=jlKF}y0aqUYqB+#*xr}*x|Pq^+=D(IKmF%L?ss$7mtFn$'
    '_lNuUrPq>2nP%8pG#F<szIl4@N|FevPVuX5bJ!&Pu>Vc_@e{xO`LbAC7VjjAgx;s-*ldV444cK)ZfqLZ^Xas15&QQ;by>8VYDOBq'
    '4(rS;#+X{IPa_X}e00T(Vp@3P!nOm%!7}vw9ai~s-+lf~AHVG$pFe*Q?(@_4_oZTCduYA87DC9)g@W_tY>ql&!MD$-HfQ6mk@|!$'
    '$A({)8)o(zM04@Y^z86)v$QrOwdwLSxfs>nuamoPm!(db*>oSWo%lXysu)-X-$JiiLeEpW#Nw}7<HO72MVXyfG>s{>g_7}kQhhSD'
    '*ygpV3!|B=b6zErC;6^_J?tO!?z!)uE`N22!5FNp;54OPv}={<B^w+n*sj<|9mQU^){6#@@}SQ!+<JFVdD=aGxv0h{A<UjMrU0v{'
    'HmJANg&@5plWYvMW^h&4tMT-3*Y}TecUeB}u%_Z;O0biQTTI@W*pieuhBHtOHYfP2<<l>ZyFY)Q?V|jKb7n#qF=jZ4Xs{AdD$FT7'
    'Bu=EqDj4`@xmrF>AYA1|+1jTs65W6`n;xb;ciXHt0<YD@*)n`cX2ZABqWmG>KR@b`mhSGbe>v*i*vXg2{qu3xFIyX5dlMLR8++7%'
    '?T2+&f$KCeMI6D=oB*=atJQcJPZtHdl9N^IhGty&QMvli1TJI_hl?;9PNL?#S@7xLoux0pj7RXOe;zLzpoq(!Rh*B&C0?miteRUK'
    'xQ$i2HLwq9-Q3;_aN%+Pu<M^-_I}?z!=vH?ewLT9JKmi=9=+_v8yTZY7*3k1pRk5wgjz!=w23xFZU$B+->l7YD|tEY<po&svX#oo'
    '_u)pW0sE1L0NtcoT%B`dZ-D630Bo7tm3aZ2ylg2)7hAeZKpqj_F0s1|*MMsRxEITe09xLuy;+BEdU(|PyJeRyYEoUpf{dK{$j#>o'
    '3^dztDO%vMnH0DT=hw}fHF=On!0mAdjE|#y_<r|w_e`vEQ7c2om1Zc-Xonfe8sW^~MS&HphlVBxtkUgT?Hm5m?<>YEbuyP88>}TT'
    'e$F_(;?3~Ac*O~V9ZUSv+qHN)GY`36ZuLR>@v>nnBNUedK&hL6sMW;ib00;L!?AY3)B(iW>dh(vQ_cI`m#@dowl-xyfvAjx*x*_e'
    '_uLi>dZd{PG`s<4o4I{Jr8T&P1&E-UCRcBKa>Y8LE}$$dNyYA&;!E*v+^hm%$AGch{f>)$_hX4JqX3*0aEUs>->?QAbP;yHB^ck?'
    'z#6CRus`PZWqCg0UR^#c6-OgebOWF29ZqOgoZF6t%Ak`uM_=OyZqZQ=Uv#q<m;k&+`T+Wv31>ucv2Dl^ha_`_67WGadiyS&(CVuz'
    'X#1DPAuEOk$E4!m0G?x8j5Ssgs8Nck2hiRWj9Bo5p#P9g8{CuE3BFrfsy=wFVB4lm&_RonTn3IYEl!{2gBmS9>TZ)6>=F3gSvX8M'
    '#^O|DXe&6`U^(KwkFia_tPk#+KK{Nt>>nTS7f)MvnbtYRdFoW}TWhf=xQHf6LryBCIjk8x`tTpqX|oqC60&%(ikzAjt#bshTL3W7'
    '%LeS5aN(g*_~+EQ+W`cAIeCv2B-mQPfg0I$14G=fS*@mC3!H_APis0I)cu%hH+lJ%t1197&iJfZfkHZYVyVt{V39C`mr?saq*~uU'
    'EOC;x1xr)ZR{;4?Ees|1vj8;1d_&tbY@6`2#gBhRt7rXPA6Hm4C~NJJ8we5!17NUT#aOrx=e5`bLkgPxF?}{!0>HyiJwpsbXYDl!'
    'Jg%68%in7@Heo|8XzmA9`3V(0?6#coI*k_w7`%FLt~`2<t=cBi720_xYKMgRF}<#bM%Xt2X6#yH^9*xM<3g~>1sw6@i-U&2%=S^e'
    'fRFC_K?nZoPVS#qq645@AvieNQX62~oLDSk0^0y~t?v!cY19wvv;`7)IDZ@*{HG`=k;R<{s?NCw3&@s0P_5+Q+{cu;0lfi3wrP`1'
    '2{#P1S>gox&v6E;V&QTe{GfIHV~RcRUk)8xxBsdKh2^{)S`j-8NReP=7-iGJ(6|qk6kzr`uxMRM{Gduim3JE`tO)^lZHTxW!OUiZ'
    'pK-m(@Gfe$6XvOyV#7b7&XnE#%SxcPgwj<siV0DA&o%?w3NTA|Sf=iMsbf_8!E=3lc$&L={lV5QU;hlJpS*ybX?C!fX-0!(X~4UN'
    'A=%lji|K=>`*?VHKEjiH)9;71&?xRa@FnhdXlik$EB2_@2%Ot24waS}M$wNjf-96E$~NBSfeT*C#O_T88y-S4xM95oAM0#moBKZp'
    'sn36M*;@=>l*gjxlq38F2)zN4jkZMq**Hcly_9VT`^(E>?)31mdwyQt5HEtUR_n~34;`~;8$N-EP0+*^BnK_s$bik+_Q_xO-2MH2'
    '&EV5PgHIHxIrK1kbTDmvzJv!K#*Qk4_S<BhV9RCGX=``5c;1IRh@x78`|U3KUM76bupT;$ZTRUC&i{A4lku>->`4@E40l~%w_QpC'
    'KH%q=U8?o?Uq3(>Ko~X>g0s{u!9-)=#6inQkaE|aK<oo<d>D@5qYk<TGqCL}{d|))V~p;tx(1RDen{4u2FM4WE~mj|H*U1r^H#q2'
    '^Lx*htCR=0Met*I+ic8%1YaxAv&U7&u?Ck0Hyim1;U{9+_XoZE4es$#FLMZ*Rv5FKVn_q*FJ&jK8Z!543{JhN(&xq)-On04?0?sV'
    'jKT%2xI!zS2hL5?iWi1)0c!v{=^INk6|6l+6RT|3;X13*J67CyTx(N8@Ik;6?DSRyH%;MyG=V_Wwq5>4(_+U2cPv7#?QqNrZX6?S'
    'xZ(vDF%+10;BLQN@X5YxSaWb7?E5Ij!F@T4TUdaln-4uZc-#i&Hlk1FTG4+|*vmeo<IVy02%sxtA=v@h7cBfV(O|o6ao|K78OPfU'
    '`t;h@pI$Dn1MZ#e#o?#e^)M=U20U3R4h!IA!p>Kawi^`LCg0C!0o;N53IK%|pwx-`;2nNYBx_5q4Riew0AOEoIdB!^a5)y#8a%1v'
    'D=WN8hslc(I(2mshfrZ03y{Vb?Pe9WtwhH9L!MEbid_7_KeHQHd;vdJcy@rR2%K?)8sCp!_mA5Gnmqg<2~8*N1Nc)dz{FWQc!HMP'
    'E7&pCE8MUc2mP`Gwgb()`{N)_PirWvHv{@RaVTI47z2ZIY*BLSVB~7S4PY7MhJ*2Z++Ti#O$j_LK^WlN2z**>lBUC*Xf%<`P>Vx1'
    'lDBgL!d5^~vsCd+E}7MXV;gv+FoC=P4n}OQPNu-jEBw(-sKA;TYb^=uk56th^R=@JLxBQK%m777eghjiefg)|<I~IWGj{#{oK^J+'
    '2>;U`3gEqecmgB3s7)x7EET)HoWBla52{$3G9WT-omdtZH=v|nw1M<bI+*zMvtpzkcXH&?tp|<-ED<mb9K;3K44jIN+Y4Hf1Gq=>'
    '@SZre8-k<nDYllhGjRimpRg>Bu?D!%G0Ft{$jxYMeZqj14Jk8=vwlr(yetw>4QG?+G#Ceqz!&faE|#^lTyRCFPg&+hk*}dK+R8iZ'
    'gB%|Ahr1X2y%p3F9WDZVq$DhU?WvRgX&JR-YiA3=f{en9Z`I?(JU^XtB|bkN`v2F-BkPL&zm`t&zAC4j5)!NhX|BXG0dGqg)?teZ'
    'PA(vqq|%Z#8TS`!Bgp^;en6eq0K%fyWz-v5b^+F;!=}Qd;{Jkj1UKUZ9EKhMpVO9cqcTep=jn9I{Z5`YAD@wMUjYNvi3v{Ojr&Xk'
    'y9VwpBjQIuiD^Un)v8|YWp_VL@t>^$S6H@UV|7xyH35chzzF1=83E~@&n=$$nfBw#onv-CE!#>S3a%a33nrm!0B^5`ufe@C$2vJ?'
    'JXo#a<BIJbp7w{=O+6=_UydxaTwQmwL|^TIwYGfi@KpgRLRJfeXKbnefM$>IS@-t<I)`t1xO~bK7P?s#od!^^i-q;faH+$$9N^@8'
    '2QP^&eq5^)=z)#+>4o;PQ*Gj>$+H^loq?emxR9gbsNuvF!{p=OYiS=>?Hb!PfHQFRaqwf9u-~o-um{{bOlgaquO8rQ@(*0gGhE+2'
    'EKK&LJ$;qumF(#0OM;n)dL2BL(F7nQnKfx8#f8I}!0_!KIAbSQxG8*{y$i4s!`tp+1vFSfrc+xt$#o{FIV_yfk1O@O`?6$5?AihR'
    'X3M3F1qcn47ev=<hyV?<m4eIQ^5_7%Sg@i^|2OEiAe{}*?nQ^Kd|vYg*ulbWVsDKm&@oWN;+>9^<3Df-UJC&(t25)snrz4e(8gO}'
    '2#^$)zzb@$3`n<X;Sp|B=T(Q#*SX5v3+rc~&}a--6?i6}!YsImsfEg79-D98#UENNj&ddIhM}wB=nn;UD&Q&tcw5i7ZgZZ63ckpP'
    '*XL~FFNbuzb0AA_IdI6%_ELj`G4Eo4AxulD)D%OAAJt{UHFHS=lln?^xp%+=*l^!~hcoV&xGq4W!KVCSRnGk3*UPqI0SxKV%t5lW'
    'Y>f9N4~=Q!Z+UDOUsQ@WA64xNm1=ixR9M9cS_44Un6wJ~XPt-)){HScZZ5FNu{*GU=&YGKeSL~p0<zMN>#^V|175d>(m`!Yuf$W;'
    '%$k!AMskXvHIn@`I;@dcur!bmS7HV|03pb|dFC>YR7U_Xhx4*AZU63#4^5@3u^!0ZIc+|BpHc;f*BW)HRI|>*?!I+6;r`@tu0<`>'
    'S;r(UAt~0(Xd*tW<3?5wjN{-2vC(g3aE^Tk7YE9e`_Fg!=kcc!tvmkN%6lEe;sE<l9Q~QL*&rW#>0C&@F;m=U(aU0)a(Fo=Q^$<('
    '=pb|oAT(fzJD-0WYgce)JPe+h)?XHL0zAvFSKfN7Z;@e^He*gMwiy7TLE8K%i}hElX}s}K41eh(qvD_CaNJE?g1g<4>2h4jAqP4i'
    'G1(X+T#3g4v|WK32#c9k>1Kc;X<QV!oD=|a{C+i^&5{dP7v1cAOfgB^Faq<bAnv8dnrH*w^09vtcuEYpd`^Usz35G~%nHd7%NjdR'
    'ysuyb@x+V!%J)6D{lnew@Y-V?(u7$nICaF;*1#CQ7gMsGlBdkrfDA_)^{vP26IvPi`;NN^e)n{w^esTousESuMuIvnyi!;xQ$h3L'
    'B%6uRjNp>22_5ouWbMpiVg4o&tM}KsV$}?`u{BfLge7UCs0B>`9i2JbQF`(v>o$qcKdP#qKni~R__AShd{OPD;OKhbwibP<O~8XI'
    '=sSE`fdOw_Zq(rEY4`GQw?&c8Y;7N{=H(gJt9UnH%L&eC>s@ifCy7@ovS|^V&Lm<Q>}_D8Xs$-xunG7>Txz|DgFh2{t?a(Phkx0h'
    'ApAM)asBN3z{q{e9he?h8y?050BD)a<ns<zX%?XTajiB>!1(Tq?jLmR$uZO@fHlSD&V=GXJQm>Qil$jZo?fzJ>Ck2smUFOaFUA~0'
    'ho3NLOf`$4gfdNHazUvAYA<~Gbes3${~vqM_YV&%B8>%vOeugLbsO-Vg9b3e)b@&#8M6W01N7V~a_IB7<NoPx-(T)`e{Nd)XbMG7'
    'QwrE4Adl1xDjuh)L4kN-8sY#txlx5LPcL_0RmQzOuY@&c(*g1rt+RR5o^9{|CI*m%Z)+~uj@?l659o3CO!xk%_bYiu5d;x7xvK}d'
    'os-XggOrK62th&FO!MCUGYTyMrVWqL42DP6ZTLQ29}yl4q-3g{>Xlol%)9dGMy=qu4@dp?^X?md`}(_!zzZzMIT#3FpbBVWUCB|('
    'h;fvmeXuOr1$8&-bBaL7_j?#LawOfo=VE^ishSwzN{pE)M!wF+S)8gdf%rYU2Ij5t)@yaOKGroDj-C@Je+8E)0WcL*rVVg#nA8sN'
    '?ceMw^0qz?`~Gdy<(9%X9FXel+4Dh732<pF<Y!IPWYz+Z|Lj`@pV?yDJ&v{POE6VdhQXM1TO!YBFz~EpB*xAxjBAw9)8_m9wCnru'
    'dG7u^GU~qsKQG%g*6aY#0Y}8tNsE~-06590hp7o11gImI>*W8HGPT*QfTj!6O`S>#hVRti%fUAv0yL18ncbIix=xV;Tdf?nE8$xM'
    '6=EA55LziJ&9%s8Hyzhhn=Ju9sGC;<|5heyT;bybA=O|NvNNN$XcL?&;3v*!_d2yC=>kf6qXs9uvw1yO(E*mrFjpuIBz|HMdIBak'
    '({~GU9J7|N+1LNR$8YbJmPTZ&E7l3H$~X`lSb)Y9Hbck{p)gC<*Wx>~3fE<~jRGq!KMvghn28M+qILn&lNd$-(A6mk4rAzC6Zk0i'
    '-~WehD!odB!3|z`xGQY*tgLZzK9mFx52R;@t+TEk`lS@@m6xy730GE7RNKXBfP*%gdmK*K%&GJi@Q+?{Uo$w{>ZB|1Kor{yFbinP'
    'unz27Eyzpg(P%u?ZuhWN*z%?O^K&qNd3X97KnC|4o?RI<#nByL?4e6;8rc8{bRCP|1V9=nGPhxFQD^tahu{6-uD#3&lk@b_UUOkC'
    '>jaYz=j*!ESTwsnVSvQXQnIt+GQ)Un4EG_OSlxESTHV7ft!1tStWAw68ByzS&9rv`(HQER1Nn^1UX!<4B3+@+PtP}i2UCx`hs$mX'
    'J}}f~y9ezxR_LvUZMYq_R9qm|m;wI|xkamctj_%%nBR(N#x58>(sv7f=U^2~uwxXEkk$<g?s_+FMth4656g3)+~2S1;96qzrHxvB'
    '1$?ZY`F%Juu~Hw{;)aD8x9Gt3KG5MXHmrrhGkI1#X$v?hqlyKN>}-i(uqernnk4poiyr%zBiZ=V%l-Yf!vW4+!G!%BxY`1omLed('
    'Egc%EFJ;nerFzrhSb{ZoC%<*N*_Zdnz&9uGL7>-^r7=j>G({5|h`VW>r$%qPJqPXk!+<kCY4e|l`<0|RfSHm@#7POIPY=EmtQD}d'
    ';WA7<yeUZg_y<(s&o0LdQkf~6<aEg?YdvFGU}KW2#=#*~#<|N#x9h^J%xA%2S&7~-is?eLtV!{Jydv1C=s|%z5KSoow6Ut*qR6v6'
    'Jl!jU#*gFlw7-_PkKZ)t9KFTy?AjdA{siOk@IukJ-avw;(VJ}lk(KFV0|N-;9C5<ah-Ms(f(3#lO%`;^g_^UQVJ2y}C~-O-{T@W@'
    'vJM$0)HHCfS#V4gr==-=Ra(v_<Wa5hdF1Warhk>=YZ;9kSMLh*geL$PP<D|3sNJ*ey}+|b<Wmfr1iIO_o3kHH9?z|#y7aFr5dw`Y'
    'xz(sX8~EH_r-<mV*|`x||IUy~*>1#6Nw6pHvTv-G{9}J$qMAIdfTRkamcWDNXfF2BU_!7g&hP;hHWi%Q$F}{h(uVi%{a(+wt#{lI'
    ';<w}1r5nJ#uJbb1A^QYZ1Jea(XDeTIbWD1m;`tWXy;%8&blT9^D`oc4^JB8JA<S$BU!4Pd2tTc0&`Gk>Uj7k<#_st^jw>1OPJ-z('
    '<S=7no3F$~t3F{q0sspz0!%Jx+&`kxLI3lzX7fXfJUXy&Bl|WTL8S$|k0bE;wz!x){7?R<LihVGyT?tjmQ*qrt5rJa2oF$Ta3ui!'
    'Gg~%$g@+8xdHJYDPoTQ2(Rl2-=`amxjNmTsh%SMVg=!OsiUqhE01+%;hFALVN<AI+KdPqJbi)2%cfd&oP#g?lug*7N;-w+N3l4s2'
    'dL19t=~<8PR9~L&o*(7u`Rjf~tL$^oZoR@f=EROF+{FQ`8JJ-)m>}+a{>QX>dAi@r<xulv6dnY=ORU`%@Bs0e&FpYlY8k2b!-eEN'
    's?%}*O&`x`vzNhEamuXN4!$B0Xk3)mC<L$FRIe^Ls@HB-Xp94+@ds7@jmOm-LAWi@#x`LxC4@dwC~RkEym;G7aB#8N-E1oH2Yjfw'
    '`+7V+Z8A(Si7mi7Gp`~5<(M3j+Sm&Gi|x*cNwo!=KB~}jKkS~ixc+Q<OU*YQdj!8Uu>$;6!H=<WTH8`Z3d;Ebh1SzdN5mSy_<&Ik'
    '2V@K;3wGTUZq~)9a4y57*lxb?WB(wq(~JA~tJn8sdu?$}rPkr2BPLp6<Q`tdG5r;QNh6bj<bx{R?^tTPAzBBTQi4{K8q8lAHQO+T'
    '1#s2k02K?Xd0>&kKcNp;jqcVO0kMPKh}CvD2q2NJ!~4XGmM!=>w$LSKLopvzh~-Rr+-9MRgUf1~gTbBlmUPQB$suN$?4CA&sy)uw'
    'tty=|j(*&+pDNBSZ(U@UvJh3h9|9Pi9XxB`(@H70e!1cAJM&Me#eW_TFB@920+L|c*vTq`k2d3gu5*p0mQb*}9(2@IU;ZJz=6ZV@'
    'c8b>42CO4%iGmH8&F+D`n<=oBy|r9Y|DZzjsvBBack5`5W(Fa1JkZ5gU-=dXn(F*WBlCI4eo&iJmg51J?zlVXYGp+>W^@Cn5nN-P'
    'K*CNjuN!PJS<BW*GQ5nBYIXJ>FOM4+OKTRbz_;-20ty>blac{*dtwN_c-7{8zIp4u?2miqlml>|bz4E(7KAp{psohypLQ5YKf&oi'
    '0L0XsQ*?T}^=4#&`M3;QUcO_k)egiD(_C_7YUM20FN>=N(qtvaT;eSARz>djV`*n~Y94ht;uF}3TvE~0>rw*%r%`MGC+a!5mITZi'
    'miq&`kPMwS>1@6?xss^fGNujkYGX9nct+%$_=&Azf3ggc1a|T<#g-!KvD~!2Uww)oKm$CiAdW_>)7+U@-ntmvK9~3ux&()A)#)4-'
    '`D>ZhRZ6yk!P+b=iOVSs?<P}swXh--Hj;<h-cCRuRqkK+Z)0#I0K&5A2*Y+6787gIa%QUS3`qu4eVJ^2Gc0-B^WlimyxsE-E4G&L'
    'YvIpq4xPD*x)drfr$E`Tu!jUS11G86&Oi1GhCI=s-{t;g#VR(C>DgRtmW|0^rHk#1K=9#FIi;cJ*7ar&`=5t<9&2!ZnCxwlnq-Qw'
    'RWj?pVF?=iM=$(A6W>$SfJ2sbeng{lYlyq!S9aaItd0?O#V8YE0T$UMtwMh9aAL|gFDa(gb~7|OQ!?-%SjYSO4M_*A&Ba~sa8_kj'
    '0Pc}0j*f%vwAe|Y$sB9F*^e!rbZqk-4xZijq7(L!_!U?&jb3N14wl;+8FAp!o7;6+eEi|%aqDf5VDiBD*c-6I(A`K$piBg_&JzTM'
    'J@c!?^g)e&f7sCAgS|sW=in!&E<0C%p=XoSoGl!;G61Zl-;9HPF9fc?Gn%#r@4aF6P-V#4bL<5~7q*9l&my}X(Sasa`G6++C-dd`'
    'V7<BRD1_Hs+2Em-&_?nLJ8X{QmGD<BY*DoBBTDU-)zPiXRBcJFvn%p2AZNlJc)dCA0ndaJ5E>h@`1&!8_8a(EhD`w~W9F_8oO$Fe'
    'h_sKm>L8GUKZHfhw}(8b$&oRJ{b42LFc7SJc6G>k`iA8x0rpuHxYdyvPL=?EK#y}WU|*{@%p)4*z=e>5RJZ}#ht1OrKiCunS6&+@'
    '2z@}6AASlJa0TadFy=Vn5XSUCJS~~#s*VCfh*JVq4{weu{!b{g{yNy~WVKKVxIry50yACC9Y!x_=Uc35BJkG-lwo<{O6?R(8OvYT'
    'T`!gxJ)7-yPJ#neF4&uC#D>uNN3=MyTjw2<xK?9Ppu>C;^_A~C0Hn~z0Lb{PZZJ_YIx?P**xnx)Lgg^_f2_pnQi5R-DFK)~)!GWy'
    '1iPjl<PS&(1{yz_H^Z#Iu;<<Ku(?vmpCQt@XnpV4FW@WX+@}#7C?`&GDuvzYZ*h`X7}iW2@6I{4E5&a%8dqB2P{hVwY{kSO6)qBY'
    '*@6it3xu^DTRq(iDCRjeW%>2$+cuD-usOv5ZZfH<!2MK_21Zo@><k~od`;U^9u7KAC9uD~PrL?EHaBP~FmW(#u9?w8_5ze{V-0b}'
    '9!9pt$r$m9aK$@%Efit1R>qXh&C0{X5Nn5>i7khQL&HXPvxSNU%;9FO&W|Ts^#K&_;0IHE&YAbzSRk&V#u%62q^8jVLTYc;=jSZS'
    'tx5s(aoi}`Q*ALOvWCpkbYA+}8MO~4Ujet?REmGLU8m*g+Y8IPgQ)<f)elp=p=mT;VW|yM%gwDi^@BWry_3hs{ZZEIzk?MQYGn;Y'
    'ZMn`En`isiQCtFF(9CwE?uz`l|Dw$~X0d%Z5O$1%N@onC4w?a=P!|MvJ*6qxm;kbMvkmw)?6grSwiOy-<_hTE8z-gtW=%D*nCdL9'
    'Un_pd7#~xLY<P3KzHW`5r>21b$7~Gl;Wwr;Ajz3=aMlg^bgM=`A}N~{n($(+M-N9zzsfOAW`g7lwSdq;@#jFvH}4x4N1mVcc!hlg'
    '-*rHT;KGsp4DzsmUoBYR)Yv3~tHZC<TQxe<PvEJSFB}%I5{eI?5Y?va*}cST$l&H2#q0U-mB6;jh&_h%VRcT=Is5JIZ8~;+j5tiT'
    '>!h12!LxP}Y)6~)WYh=S^n;o$Zv$I(;;g~Q3a^%3uh_2QX12wGjRpq9fh0?Qb6n3=Iz4}VITA2#_a_Yq#c|jK&UH<GX0?%?H~S{D'
    'fNb~%EV~^%o)uY+_VcU7>@Q0r>El5a5N>xFoWOf&$_+dy0ku`D16#>D>z3FsK1}wGtMwxq?b~kvO<<`on|JNyajZ1LU_+%UZp_p}'
    '&@tI>45r)(jXSPE$nY)K0H!x|`sGKf(9(i(D2@#NM+#0l%=i%S#pJ8YOSfOFV)NT0na|n*sXy^49$50f;>*j?C@>(6##C5Kn^=WC'
    'X%bukS?h2xaDSz{H(Rc}r_A}i`@Aye-<|pVWmQ-|H{r_!25ESvkc#u61_1!6UMrT%g)7pX-%({1`olqFQ?(4%`G6<)#z$1af_Oj^'
    '_F2oph3)t1DD7U)TAY5(<lg6%%vO$%h%;d|5<BCil4od>2?63*VpWpiG^LMdv9=PhD0579o5RuURh8q?90!#|b!D(Y$sEaShta2_'
    '`MBc+9(Q~=x|i=u()CJ>8S{uafO~)mGNl)cIZY3M&#}?9Y6N$`A{pwW$M15K!@1SnsfuKcA1Bzgm}o_EfV~}#ZADT@Ef?o=;>h`2'
    '=XGlIr<c2f5Cz_S;Xl{j(b@FYm^=uT+hk?C1H>|n*H&YE>Z4eopK`qx`1g;MR&4Aok~tT^gK-XtaEc65RJxj|u&I1$kd&?ye%b;a'
    'gH8L8%+R3T>2$tZ81&ErxNsgS-5b{CT40zf>f_F3R;-^nbGr3fo@{-wV3OKHX<kGCc7yEzF5tQNX@Y)9V!KX>bJ+9sAgpwt1JPDS'
    'e%a{RHrP(SX}V})WV+Q*=Nz!fmFMw4FM9aCu{6+fI?8B?$%+P;1DZ_h`N%tQE`w%|d+LH-r@=vwvP_)Zo*&RWv|#ZuZX_Ejwr1el'
    'n=i1F955kvzS(r{q8dv{%6chCv#dYR920hfZlc04d4chcE&HUoH@2&~avRPj`llt>)Iu$}WLO(oI9ZqGF_^g&mIauI9GD;7TWeSD'
    '$Z`MFU@Cb-SHwr_Muj<YWLRUE7Nfvm``(#S18<tEvDREC{$&TGcRa2f#xlWY?36}->9GC^j9#)=rm!%nw=-bp$JMf*|Jbd)PIE#o'
    'lR!ZWSQ+cxV8$+|GJ)yY045qOYoRyGW_S8iTGIntmvC-@wk<uULN4GZ-ZHul0ONtWUB{wW%YNjoI?EXf(S1;p)!HEMK;A%`%5>~O'
    'KH)0~;o|hEF1@#;@`>+yH7Na@>$Nepq6S}Q!F^yxOb9;Dfg6(9D1j}&Jmbq&uE^3^N`gKykNf*CP~r)o4%TZ4F|X#srOF_7p;G)W'
    '5Y6BuvEm~PDQ?XWFgTmS?OOe|-z{|&OO40fyq7O4ZJGJ>JaAvYw+AZ)*e!{U-g^Af4Yq@sqqy5OI@N_fKM82=m$fN5n%J;2N$o)3'
    'V6@rb^soYkN#7OJ(tFMAig(w)sdLbW{ZU_c@0)&~2YFcWHGI)ympt!TXCl3hGU4pv@P*?tSj8F*{LYG2$^iQ^s!5KA-JdICq6GGw'
    '2Gj=_P_Y&}lHuc}G|TC;hBH>(T3A&71W#Pv;y1M*WMwwvjLVC21Wm<Pd-xDp&^E-vzz*yDW~sOqD`*0@aI|hY0co&;(X$1<WnL6~'
    'DQ+n!v-q$^)z42%|D{n^JM6!$HME&bjU|*YpuPeeZJdcX_eEV5XG;Sm%*}3;e~LD*GzjE$)hfwrs8TDt+k?-<ItO1Wu<Si&HFKlH'
    'bA`ZbHSLzSHtRAF0i4v#Q5ukf^NHxO*T`3!?w0qaRV@9g!T!*{GU~TFbu4qR00=ebC3E&>E!ngjmqG;*8;VrhRuS6|v45Q4;vO(*'
    'tzCJsdBDIqP6`kyy|XilY0MmG1GEBITABH}QS_4>aFhO8dS+_wFK>DWJ7Xdg$9;E}LU=a8>u?6aC&!8rkm_-r0!ty!%CM^d$7i#o'
    'C>#jFKx$yuxxpTV)<B0jo!PqN%f#iCMAQ-k=oklE#RNdkzMC96mViG*V!$#7yIRz++cRQHL;dGdzdOD>uJu-9)eU@B%T54%1;~61'
    'H~NG+Iyljk)j@r=?3Hqt$QoC7eViN+eq2f<SQ#-nk^*=%3{Hm8*qckfae9&2BK7-YzneN>x;D0_VLn|2&P$f{=!FxtAuol>%M4nS'
    '6Yd$n@dn}NeyXST1b6Gr$KiqC5hSy1gTM&|R=+1)p^8H_qwmf&7HVt}t%u$Ge%+TtN@VoZ)S2KsB3Lj$p0hCCto~fKKZVuyBERY5'
    'x839O=lgw^`#ZRel|FgK7MUCwT%%FtAlgoZALkt2jsVJ&+-gbFtI*S&aE^>@%t@QOFDtY^a;i?Ap?fw$>)8PV0Dcf^({w7x-qgNP'
    '`fL00*BR4*LSJ-c)m_R<S4Zb%S>kBt%s`HuG~eMd3+!hLtDOg4Rag=^cNZJmW>Z6ekMLcKFrf>UtN}f{U}IC9JVSD_T7LK{@%+@e'
    'X|q$DCdAYWM?)tdgY1-HjRfa0Z3U+l|7Q2+_a$Gs<5p4u;><(+l(~#W73<(BBoe8lS-`Wwb+1uj!<xI6d@VT0x?oJW42>QHfZ3~Q'
    '&M<uK?Dw}K_Cd!^HaAZLQ^eN7Ee2;he$ipq3f#mT!4|gajDWv>thp)t%U{@5<mKtj%HN+qv%+Qo;sI$5SQFnIgfSP3V6fKit>vug'
    'RmOah_`I};e%{1Or`poRF<usoCiur1V#YpqSPw89nS7JYZL8oXR`NdM{;mX&O=PA(<-0~=*P-07+8qa(6E&Q+S*+OAEQ=pvmzVI>'
    'g6|fZ6TTUY5MeD{^^Dd5jDW#pVQ50L(bb&rA5xcOmrea*W-YebtgK-&T4!b_=HbDmI8-N1U(Foi<3`D(6}$D^>csvC_)*OfHx*c<'
    '55l2>gA6x?D{Q^9wr&-=<k7qq+uXe@{TWx+9Ow&N4am-RuW(Zhe6h8XydNOdxdfbRv8#!6uS%TLXTTlTDr^G-fAEq8G<nR7!{o5R'
    'lK7TCLgwd#OvdZvF7a59<)@YE-cl=byi%TpwwtYiaKJ`j^*R8U_6~qHHp+gjDg-3EEEbN?yTHk%&If!w^G;Z+5=SlyaNn&KIL3`)'
    '=l%DUj#<(;V^AS+6v0J?hYD&Oa9Fa<OxJR2aqAu4jim*Xe7k5UXKk!);m~Zucti~FiJ+*Zbj4~5+sy(3Zaq$?2bV{E0bRU|=zYTl'
    'Ev~bF92m1^=3hnAhE%p10;K@NuCi6|Z!Zs*&roDrL(abL##q)OIO{^jH!{H+vI6ds*VV47ukubq$nKsW_TTj40xMVvOFvof=uOh('
    '4eVr36_D7*;AuAi0p?b@uj#kzTWhCb(RmM=U@UQnqJ%6S3<egGY3m~ttE&aff0w+`QsK%@i6s`rM+ZO*HY)XTrZJgm8@)4={T#N+'
    '-|xSzykjnpwQ%qO2!r)E&AMuPX|>eMLi{v}4_mDS=dG_)MB&n~LvnT&j!y&o?7;&>SV2Pw3w9pyCtKyc+#h$#oYKp*(3!>_v`oum'
    '0dF%Lu^k)dZ+fjJ`v@4h`8>T2{+t5w+bTb6nJ`VtzR(OQa}-o{J%TGV_U2L_z?yU1Y8HR$ki1E}0K(cFd!7caf3P1dBY0IDyq_`('
    'V{!;aHi|#@MgFRCfBd=<4PdcHbO5T>dpL%fvj;zgeV)cR1IOH~?OV^+bJxd}oOvLs0be^N3<i6lHrE2f4xk6EfcqPo&Frrch&5il'
    'xW+JeXe;d0<lU(e-XIHm`@?Kii7sG)Tiq;|nN&LNHUy|!bF9_{9j+s0Mj+T}7#2*xzehINKy*u6t@MxXML#v7y8P*-U~w~NdEhGJ'
    'Bs)NNsi|Wb*b_H7!%nbUeefw}`*bhgo2-=fbQ;4JmAP5Pbk3^+rmO-^<`wENZ*sV~6-%GrV-|d+D`l^N4F!Qc5<C74SHZp6&UH!9'
    'Y(Bz@f-ve<%5r+-zWl9NQxnRZHiQwuIT@!`gU=&5CEmz!#5Aswc&F~NCr%?ZaD-twoi}5T8xGS@m~S%w45L;C%ge5ldO|$A=lzCy'
    'UUjpo$0s_LPGx5F@LiySLBW|2nZPxR-~8SB=UM(`<WqA81)P9d_@(saRxJe_1un6A9C6oy>NiS#d0Ik=FHcNpS$PpCCSX}@V?8B7'
    'PQ=XySIAlUMiNGvv@Kgb#i@tpHp+loI%D>=>VhsuozB!en9jm(Mcx_^)mXREl~cn=HWEF^hVI&>Hf9my9CMbyk|++}oH(0=MHqHT'
    '%N%RSVE?3#e;!Ud{P_<5+#T=kR+45abN76dYC)D1*27N&%gvE2q)Xs1ttNYo;MYl2=aD0qk6L7_?x1i|t=EaqwSDPz5ID#pa6CBd'
    'xN}#@KX>Zi*1Dcevas?jzMBplqh*J!2MD#CE(%=M)n&Wdt?w5N&Jl@w_A)>0kNdt~NwKsBUl}4GQZzodq{Rr2gyrZS52FOXnpSfY'
    'e$io*U@Y_Ou`$?|MjIyi0(av1#A>q?U)ko^_i(jf{_U025F2}$i~;2#pvc{eXqzENGlv%@7|y=xLr(K!HXSv#&S|mF1a_VWPF$|V'
    'Hnz0T%AVV)N6*yt6^T!~C%xaT0WnY~##|bwMg|TjSm?ivU>u?K(D;nJ-sb47v6VkNDCUi%$Vby4-ZML6u*svJ7Hk*@JJo8du08@V'
    '3Vh{c!kP{9vTeb^VHO6P0d-zk&Xr)&vU9nuUYb+yhUKm-i2<kgrj@!LvE5qST9EUOuaCj`iQib;989zc?80SN`wc($ulgWA1~Ptn'
    '{p=rY|27XzbQLQRtL12~z_GRo$N;FXdCL(5aZKRv^=#NJ3T+vxI7-RU2JHMa4(yIY8^HSji#;reF5?NBukJ(YY&#^a7+ftITIqqU'
    'esZ6qjAB`q;-M6Mj9;y@zO2bI{_#n6EAt5LP?JR#BI;-fzzt$jRjbl6Q_-xr)xI%jRSx=0?z^RLu2oPFHj+1?1()DVbOyr+Lt|~#'
    'EFE?zO5Y~<Nap(}_jk$!gLP^WD^sRI78d=N!l{eEkU-I3WVp91Z5Vm8?4<<v<l6OcSVmFoewVctrY?4GOly9WIhfqRs%a@1EEo$e'
    ')&O*=)GL&@GKHzS=_Rm{atAqMwA%>>P=*;9f>yYHP{^LI(BQWhBC9Q*?=;pFSi#E9S7M-u!?|bVf3O~sFXpaXCH#uhR}^N_YglqX'
    'Nns4jpm7D+Yp++apy@NN7P0&+{kkLA3WJv*4&LFyiSKZ*6Z;-PXgKb=+cCSWHpqY0`+4`%!1(QhiAwXSt7jp&6=r8}LQj}thQY=t'
    'Yj};Zt0B$5DR73En`WT~h;g|2ZTRlH0njh_Um}AHd+de<b9bwQvEEZ*`#dUKfXp^EAkp0@0K!mk#|iY+I7J~WV@T|^YHXjyI$3oO'
    'dxQU5{9x0e66(Yy2(U!tnH~g8R;N<Eqrq#I&Skn2vxYfMR)EfAd?`zutW;J>1b`^M0LyB$=5H!&d;QEB8=P{}K6|okzc+nM(jd6v'
    'e1yRSWxHBR{$Hj4n&P-LKv{v_6Gp)?m_B@rT0<!b*q;wbtm7%Q!Y79QAvHE+TKWcb+QGJgg)3B=SPPBVfW(ZgWJ_kaw%8Bpv3WGB'
    '0#t(EGj>%ihnG1vNUwy@A*JdHc=7b*YGpW~^={k9FFFV7IPTlJR+<7fdDzP70C{}?J7P~R`0T57IOyG@epxTR%s3A?oNyYBjb~<<'
    'p(NmVKU$c+DlSZ~ZZ!$wO$DCW%WlnI_)5MF`@p_UmHm*J-lA+0+l7-|st4N{*P4je>6)9S2trI*iX;r1_3Dy-vdnC9t-6c@kzvfQ'
    'K9#R3Y@Sv-LA{4+U@Z-JV~&d(2k&7^XpYgHK{;>dMm>HEhTYWRyc*mCKOM(tJ9gt~gp<G&qxb2WRSsDkPOeqv^rjDZ(ZAuJoK|&M'
    'c_GYzE+8{@0#U|XBn@Wa17&lZv&gIg!0J{#INafJL0E89tK&yw3YoJFhc#?;1|GV!rcH?ucjo2wy|2CxzoW|uVMC+G4HbA1tOBeC'
    '#DX30u{B^`9+%cL@i7d8ljNt(_BK_vWRPd)I)@;-$X<AGb6}yJ4a@_sOM$cHxMwlfnl5!P9LKenkg3IWW~tk50O-NzXev!|aCFI='
    '5DmCj?AKb2UyBy*HU)lKQE!X0I&`Go_{eHfNs8;sJgyO7z{~9MN>#Qs%z}5Y4vaQ*SgMfQ0PO^}W!qmT8Fy!-=&!}v^M3c`E6&2p'
    '*`Yqj;mb-vgJg?S82PMfI;YwB0&9-nG9x>O<UQvR%C#u#3xj=+Y=uhjdp8fbuDjK04j9RpM{Bs7CL3o{6Id|^7ziuo$VUeLd95n2'
    ';{9Ib@#P7}WZ{DQ{al&jrmzje17>OO4lZs~T#Tt+QZ?S$S;3FSwTtpq4v%lSl3(7jBAhl`uSygweW}^QX2q68OJt)U=BK;WDDQt2'
    '{nO*dvLV+rgEpKd#}a;yG;t#hH$(QOX-wHgAh9&8%y#XS-R+;R%N)0H0`M3M;=`dKKH0?aY4G{3F{=q?gXu8wc0E>;##}b|kM}mK'
    'uPHeuy-xOV5s)Qexhyb<UhPMy!c`R$o_(H&mjE`%K?V-?G)|_3dht!wm1ZW`(G7ZBQ9%JATH(PH<6>dD>hl;0d>xpJwj?awe@wqY'
    'i;cAmA#tEQaIh<!DA6Onx`U=xQdTo`b|aFnW@)Dqzq@nE-x@`WMQdv0sKtO2#v!3I_qj!>I2SmvQB9xM>Tq2WHi&RCa2p;s6P{HQ'
    'Xmc~d9O1-~L}Bo7T)hym4of$o^AqX%ltl@~L|8C3Xa*8Cm5?uiOee8KH^Sa<S6`58Ce3#~Ma94>u?piby;YN~Vdgf7GA9m)C|ASZ'
    'vj(`MG@+Y@UYmjyXKDL%%rAj8Hw9*bm2zxzHo)4N4tJX(Py5BB!?W%Bx0S9F9hNdqo>G?0VFy4^O@@ajY2wWJ$t0L^n<7h|!j_FO'
    '0F?m_6-a!x&e?A*%~^OdnUkX?G)`T-)>=GLK4Xi_*tmOs*&SCNT>v;^H=G(cN`UWz0uzKehE&wDZkK6(?dq#?epkKjLEGgpD=<y%'
    '-3~tCGSy!2HzXyFCT%7G5!rN`F4sP7yTF%Z%Vb02hi@I;EsYAFs_?OKB=+@ox!tDCDVJuGA|q%?4o+>(nQ{wD5O|rZmf1%;_i33A'
    'fAtnEMW<(czOndJI*B5ulXARr&9JADxsWcX!1H>WusW$-3k9Eceg8v~b+gJ|k$_>4!vx!ASYM3=vdsJSELHG{bKT??El&ILMfVSS'
    'TuTm3t~%i1sX5nNrvp`rb_ReDQ#|koE9usUOuVVa*_^!W?l{U}_qY~w$(e1PVkQ*otd@Yk!NF~wV^Ym@$*{|iy=h5a@A4JNF%?u%'
    '+Jr4J98?B-3i1>zdmP!R&S*3~)T?p(qRvlAw3|bu$-(S5kZNF{F+g&q!yg7GaK0WuArUOac#}G>9nC?pzicU+%1l9E>NfaXOfmM@'
    'VNgK#$-tAfzPhGWZn{I~4BxHmVmT2-Of;q!e1C>JP6cpD8MWg`bGG$0^IE6;m;YhOz_vJ@6h;l93)=@qu)Sb7A##jmXsiiy!0@TN'
    '7B^ydnl7<y^1S|4R>=fiPfs-puCh3sn+gaQjJRf^R%O~(hhGfWD>7dCUt<}uRbO^Xr-9Y%AKaM8X$6Hv=mR*iaRf=7EE6wQIxEm}'
    'x>h0l%MY;sSG<C0V98ANk?)Y+Pb%gC*}BwHJEv(*Ffey*tnP}$VUEO>J|k1_Vdf^#f^}Bx(kdy!B?4dv8?Uu;&p558F7sU;o@DoB'
    'Egg$y1h<$0^;*2EwgI|o(O^QZjSnut&TFm7h1A|(XeK;OrI(Ei=m$7Ia*R4^^lWwAY-Kl>dF@3Zzs2?7B+9kP3^ke&V}Qj_HXr4r'
    'jA%H3Ds`ae3irp%ymD;><eX)DcP@Qp_n#GNQvp{?F6@sLv;`(0W{?{W=2jpS=lE1yuT<k)#s8|!YJ!ey)~d(NV7?*qG2l}oplUTT'
    'ZEXNcV1RA4a^Vd%j=QD48~E_Vvo4#hHkh@?S&{*szJOLWuuM*L4Y(<z4_?}I?d3e>AwTJgX=q|40su(`-&TR$j0uJm4!^SNxRc0t'
    '*%5A%zAX#7Fkm{hIp7X<Qgj2D!^SWfolIbyFqVMu*Y3m8w(QiRWJ@TU$vG1TaazzPxU&w#Ua1tgp5xR{*9+4&*0i|JA~m)EPT<ej'
    'Vc}fm1fJhau-Je;Tj`*-cFZ-YKYC~Ua8l>_LMtPWgxU6^RbRa56v0kdYiBYn3Da3SeRta|eM6TxT<(ljOfh%(gPytZS-_h^9VxZg'
    '0Ia62X6O9XEM&X&>!7097UKdzQpWWH@{dmJh$(a!of3N1)i%FpGxMI`{iS!r9AH*DN~=|agNLmGr`uwV)%y;o>wGn-Y?HXzuvIvc'
    ')T8hnX5zm!kD}8Ub`OEG?@XSB*<Jn6<qmJdfPM^H;6FpK-d61`cwMG&;QYE#NB3;vRyRqc&DvH;5S<%^Y`&Rpfi?m95+udBjEE|*'
    'Uj{aOwHWy)v0E&~Ff6FVE#V*^@Dm?hX^b`40WtvBF-uCa+G_GAsfU+GzC*91Kf@^sljkj4N~Xr+<YR-4Fq{h`u;4YUa@L=uZuAh-'
    '85?Hd)QOh!bRH;06gC>@NfYc>7YT7SF8nva8)i7g!A7p#mR>k%HJNF<81dOf5aog$&?Ymz%W_U!{L{~X{nK%6-aK$IP!LCS*2>6{'
    '<4kTzsnZR3U`H8IjCt21f>X}@;el_4p9Np|{eP^~A1VHYfIo0Au>2AJCvgsFHvy&tMq}yxmfmk=`?I`r)+8e!Yfb!%iL5eFhmRAJ'
    'gjNCA7cc}MSv!j~;CHOMLhL!-zb>0El4*cE<LbC#no+jxk44y_Y-+010tf3_*{{Lv4Jy=Lv@#73ENEtBi&RO<ZV9dNSof%$RQ>L$'
    '2J1Oehfkn~b9b-*{_T1Hc;Snak3O@qhr>z2(8@mZwJFoiG9XSGGuHRZ+aTpP?Z;2cGpBsfw~z79zQ;^fQ{~}};}b?$d_u~;!bXGS'
    'H0v26eLp9kb3o72wVyw6_~yTle;zN*7;?3P%z@`(1*dhO+<?=G%?twoe*?$_-+Gr?!32JK{m8cqGJa_Y;n<~KV@mi8SmH>yR@o68'
    '5UyhLvX!b@FG*uQHGlVMiM6l1N=3;{*=`zq!FmZWd-$Xv13*1wz~<K4`^g^9z*V2_WqDgT6IcA??);OxA59A`!<Wbb#&Lqesey+D'
    'QSilhVi)E*%mFYr@MrHS@#A|Be3w0}8^U2Zg13wsEDL-9Rum^R+92?{aSEGJ3EaRN0{P_nxyd)2(;vTFF}mz1U$ue(fDOsSae=#;'
    '_@CN4EWc$TZVek`orY^3|L^_(rT2?H_&??NbtMK1$131I6DD35i*3A>LzaPf43J~D^V@{<B>ezW^!3v@JL9vA{nIM#n}*Y6f^TX?'
    '!0`$*Q7fNZnJix_bI2Kl-6-??&y|ci*me%IQ;((PpwnIfe(PfGGq$yRTjHCz@Mn=Hl>d3jpj(-~Z4!)uhl6wMb0o<LKuamjx~0EK'
    'Z8*knCS1HBZvX^eKCphd9bk&SvoHDxJ-8qS2Nz%oRG*`hM|v|Q?G1TfUgWUSJH+@Zd=<45?5P6@N}bZ<z{!<n@Y~2j#=1@3?h)K^'
    'W$0+)sH7evJ}B7=>xcE_m=4;)*4Vn117Z8SSF-Ouof;iHfBw3gyF141PIKFy_AAyvQpr|l1P-gtRNo5w!NDXs{1k8-{6ZP6*dUs+'
    ')^j3i<xIGWdoi)9nFBy7cvO&@)e9?_YB%xC`l-JOJS>6awZ_;iF6<>`!@eaW8Y`SRo&wl$1aXTvwKaL88zjCwt!Czf8v5j?#dk2('
    'Wlo$~6Zo_bCEPSkGniD7_oNMFgKd56-vMxO`=8mZYxPbBcK;G!99$MZW&uNtaHAs#C&<=VDj3DIS4lnSaks*m8oRP*1MChw53tG7'
    'B+oV)oXylG5Uz>V=v87@9av`>|4?gkQRc1$*dG{LwpD6zWM;;3YKOf>=!uJ8_9hejWY7pPev)uuvt}^HC^*3xz}GpxbDH<W?)J~0'
    'mh189KQ97ousaQC-mtmCcFH7&Ox*_tv!<}CFPQ|W_)s%)i0#ct+C|A*(nMk}1r&VXa=I3pQ~)sr3}l}aR=lJ>gQ~mwtG})prWA8q'
    '8a7O+9M;4NGjQeZvGn|2pipB??biz4Ft;|sC=3pV1T-^R8W!FGF0s=cpp2;jc%Lca?}~nYe$h|6$0N|o(!TNOC~M^ku|S4%@Tovd'
    'HiE1=-*B|C;PBwFJ8#(gxNefU?&D$%p#mFZ89@WPCxaYv1|=wk;KEi12Lvp<N!%6}rwwNYc$3rCr?X6A!ClIZ8Ij$VR%gi0yxET9'
    'ErG{1<cW=&!OU#DT6XoH!nI5}@fKq>U1pdkzYB`aF@_Vy-hhdqJG=@U41D-x8}d|rhKCu%EE&XNl4*oZ;-28XK?YZbE4ZcJZ}1XG'
    '4}%>p41Vt*HYb{2%f`87lf<{W1N>s=E4Bt-U^2%8+87*A1H*uUxs<F#oQx^AO~Ov2fL4;AstuLHnp?Ih>8PU_Kf!HD5i5@8j5x3F'
    '-iEVXfBol{xqeKVZap)WTA4EoCoYja<nkyWWsLVi7b)+H1pe94o_<=6%kyjVkd;<3w(w~iJD02Cm|zj{;rMUv@ZN@vV{mly)l%2T'
    'VMMma2>^XbiQuP5;$u}N8Z%O)1JvVww(CWI#V_`Au9eY8%U-xZ3J}QWFgrkflh&fGi>;lF`^R?a?XdsjnJI@)FDp5q3S;Cn3>@7U'
    'is=Ka5Zen^1AwNkPc7E>?UL8cgRu@q-1w3-Fd#N6X8~h>Yvs(XiZx(&rYpX-L(YHhSC%+**rGJOdUj1%X6&_;n5w|ulLL1;l@hKM'
    'dM+DZ8FK1@seun%u$4WBJ0Siz4Ml*dNTqTvb23+~G7-bZF=C_U(pvyn01TgF#6F|Lg$7dO3}_PzR%DF1UHF3@Wyn!Zg<XHHgqj%`'
    'OZ3{KI1ZgG-s5)Ru61mBmE2ky_I(QQckz!;50w1;@~}3`uHiNtj&5TjUJ8a;XpL<W;TJ4O&a^m%&R((UXK!>Wty?RB@Ds=-bC^r;'
    'm9CysS2(;Yl?Jbm;}>xtw+rXb?|uOG-CFK!WGnzsN<FVPlQ5$x0?g(}_=X>5;z;Or`Rq?Q?_pS8joYUsOY`&D#J&FX^Qk!Z^BFGe'
    '&c&*`ZO?2mvmLww%%;jOXh36}apeP`U!Ix;oNC7WzhCXY9-KF-p0e0hBv(+s4wljwN>sQ?6B9nb7$9jlF~33eQy0v4jOj0J<bfD<'
    'BwGMsvAq+n$^c3Zn+)rFIq)jCw8^fq%IK&|A=m~h?v$OjX~l<!mo)fzby<qZIP17)3S5M1RyPRV9BhjUYTu2U1;C5Vu0ba_jtxkR'
    '{Q|pTjdSwvhK4wUQx9KsC2Hw|QyW;a9X)H;SuoT?%NZa642G$^LFc;`>(ou?Q)6O?9JYLyg~N9>^eRP#>FvOld>hN0@T}7_8DFw{'
    '7oR^LzO=iw&q^GU&a4j~I7Jdx007;L<V&#%K3(dZM*X`Niv?GoPQi730h}DWxeQM{?p9tn0bF~wZLr3N9VP*2*cfcUI!62+ULjPO'
    '#cdV53g%phWg2)IOCK9;VB;nnMz(^$zDi^7LCJHgz+X7?WoOqpcDmrxs?O49@5w4hFERKHpVJ%JdQV#=uZDlbiT0WRWwODgE5OHg'
    '^gMIUrP+xKu@p_ed;J$#uPtXj%kp@#(xnv69NfxR&s=)Pl8j{WwW1SNC(hO)XJ)*ASbr4>+xq&tczF_y39$ZwH@^Y2WD8hfGQ7AS'
    'C9~f#fMfJ#o6sK>$d_+rZN+ek`IKJbU=lVDPV+#-)4I%>N;9%-ler<(GGrLQa1NmJv9eVn++dRK3&VSMIv^Hc^s!AKBhU}Dc9&%i'
    'Hm0y;c+Jz*tU}@ka%rN&f&!tixy>vaWiENdTOQs7sN3RehD$AUTUk`^gEnq%fX^z>#g;eIR4>R~8Jy69<@_d`V4W%DoGLhMZy?r9'
    'Y>q%_;PL4?k$3X6yS&1DbWe`8WHZ7c!z|=9?NGp8n0NS?QaFn7O0ln~W+fRG#(lPcMHToE@7TPc4%{RxMIX4r0_x>9nupcEh|3k{'
    'NZ_3LmceRDr!v`3H&)<*PLt?t+bnH0VW<V{C8SJ0yH+<{>OhZTQxOL5l*4YErf`+Sw<h=e8gkcWIjBcN?XZL+fx5x3Onf#@G3@UU'
    'pWhF;|0?tu@U!hN&#27Jo74-_%Xom7XM|wb);3zlUSpuPMe4jt;@xW0Il{t~2|`|b2_;w0rv6eZU~cI_BS(bSw}(`&h~1Q}3UZW4'
    'l?lgOwFyR0h+w=2_8c5J?S;bzuM@x2T&!fFfp3@sBn{7LD!_!c$xfrbSs1HKBZZ%)>*Ss)8dmK8biA0r(6CR{#O6xNpo)OGeD{r9'
    '5BEMo`!9kQ7<wn;T#vMpD&$J#8$;$$KcEU9l41R?4T%{`>fi&DZ1i=j)_>xY;7AQ00y#$~DNtZ78TgEIF$<V;kofmn@c;FH{6Eu5'
    '9c2'
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
