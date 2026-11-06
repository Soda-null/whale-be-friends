// What moves in each picture: the parts (rough outlines in picture pixels) and
// how they move over time. Story beats come from timeline.json's "acting" block.
function makeRigs(TL) {
  const A = TL.acting, TAU = Math.PI*2;
  const clamp = (v,a=0,b=1) => Math.min(b,Math.max(a,v));
  const smooth = (a,b,t) => { const k=clamp((t-a)/(b-a)); return k*k*(3-2*k); };
  const pulse = (t,t0,d) => (t>=t0&&t<t0+d) ? Math.sin(Math.PI*(t-t0)/d) : 0;
  const pulses = (t,list,d) => list.reduce((s,t0)=>s+pulse(t,t0,d),0);
  const ring = (t,list,d,hz) => list.reduce((s,t0)=>{ const u=t-t0; return u<0||u>d ? s : s+Math.sin(u*hz*TAU)*(1-u/d); },0);
  const sin = (t,period,ph=0) => Math.sin(t*TAU/period+ph);
  const blink = t => A.blinks.reduce((s,[t0,d]) => Math.max(s, t<t0||t>t0+d ? 0 : Math.min(1,(t-t0)/.07,(t0+d-t)/.07)), 0);
  // slower, deeper breaths once she is asleep
  const breath = t => { const s=A.sleep_from; return Math.sin(TAU*(t<s ? t/3.6 : s/3.6+(t-s)/4.8)); };

  const cover = {
    image:"../../docs/images/cover.webp", w:1774, h:887,
    regions:[
      {name:"head", blur:11, poly:[[1248,418],[1300,395],[1345,335],[1345,262],[1395,240],[1462,252],[1462,296],[1520,302],[1600,335],[1690,385],[1735,480],[1700,512],[1640,515],[1600,545],[1552,600],[1480,612],[1400,614],[1358,592],[1330,540],[1275,525]]},
      {name:"ahoge", blur:9, poly:[[1342,292],[1368,252],[1420,236],[1470,252],[1468,298],[1425,338],[1392,346],[1356,330]]},
      {name:"hairLong", blur:16, poly:[[1560,560],[1620,525],[1700,510],[1774,545],[1774,745],[1690,725],[1640,700],[1600,640]]},
      {name:"tuft", blur:10, poly:[[1248,418],[1298,402],[1318,470],[1300,530],[1262,528],[1240,480]]},
      {name:"wisp", blur:8, poly:[[1140,690],[1175,650],[1240,640],[1238,672],[1175,702]]},
      {name:"body", blur:30, poly:[[1168,725],[1232,622],[1350,645],[1480,622],[1590,592],[1692,642],[1700,702],[1545,762],[1450,802],[1232,812],[1160,782]]},
      {name:"phone", blur:13, poly:[[1222,548],[1308,522],[1352,650],[1335,682],[1262,686],[1238,640]]},
      {name:"bowl", blur:12, poly:[[1352,652],[1398,612],[1482,616],[1508,652],[1492,702],[1452,746],[1400,742],[1366,702]]},
      {name:"water", blur:7, poly:[[0,606],[660,601],[660,768],[0,846]], cut:[[[430,702],[438,660],[684,660],[684,745],[540,756],[445,746]],[[556,732],[684,720],[684,782],[556,786]]]},
      {name:"cloudA", blur:22, poly:[[0,482],[200,470],[292,512],[345,560],[0,566]]},
      {name:"cloudB", blur:26, poly:[[468,482],[620,396],[760,345],[960,360],[1040,342],[1058,366],[980,432],[800,472],[650,492]]},
      {name:"leavesA", blur:9, poly:[[405,0],[790,0],[878,55],[850,112],[760,112],[680,52],[540,42],[440,78],[405,62]]},
      {name:"leavesB", blur:10, poly:[[882,152],[1000,62],[1103,104],[1103,340],[1060,402],[990,332],[892,262]]},
      {name:"vine", blur:9, poly:[[1610,0],[1774,0],[1774,120],[1690,330],[1640,300],[1625,120]]},
      {name:"curtain", blur:10, poly:[[1230,0],[1415,0],[1432,120],[1420,300],[1395,305],[1340,232],[1290,120]]},
      {name:"lantern", blur:7, poly:[[1512,84],[1598,84],[1598,212],[1512,212]]},
      {name:"scallion", blur:11, poly:[[640,478],[782,478],[782,682],[640,682]]},
      {name:"tomato", blur:11, poly:[[750,540],[922,540],[922,676],[750,676]]},
      {name:"fish", blur:11, poly:[[995,610],[1040,588],[1102,612],[1104,642],[1062,664],[1000,662]]},
      {name:"tail", blur:5, poly:[[996,606],[1032,612],[1034,650],[998,662]]},
      {name:"weedA", blur:7, poly:[[922,590],[985,590],[985,690],[922,690]]},
      {name:"weedB", blur:6, poly:[[1076,640],[1112,640],[1112,692],[1076,692]]},
      {name:"dapple", blur:18, poly:[[0,852],[420,800],[700,770],[1000,735],[1000,887],[0,887]]},
    ],
    eyes:[
      {patch:[[1365,539],[1372,525],[1394,511],[1416,512],[1419,531],[1396,547],[1378,546]], above:[1388,506], below:[1398,553], line:4.4,
       shut:[1366,535,1394,549,1413,522], smile:[1366,540,1386,510,1413,527]},
      {patch:[[1476,506],[1483,491],[1502,481],[1526,479],[1541,484],[1541,496],[1525,513],[1492,520],[1480,514]], above:[1508,472], below:[1508,527], line:4.8,
       shut:[1480,505,1513,523,1541,492], smile:[1480,511,1512,478,1541,501]},
    ],
    eyesAt(t){ const asleep=smooth(A.sleep_from,A.sleep_from+.1,t);
      const happy=A.happy.reduce((s,[a,b])=>Math.max(s,smooth(a,a+.14,t)*(1-smooth(b-.14,b,t))),0);
      return {shut:Math.max(blink(t),asleep), smile:happy}; },
    pose(t){
      const br=breath(t), sl=smooth(A.droop[0],A.droop[1],t);
      const perk=pulses(t,A.perk,.5), nod=pulses(t,A.nod,.34);
      const lift=smooth(A.bowl_lift[0],A.bowl_lift[0]+.35,t)*(1-smooth(A.bowl_lift[1]-.4,A.bowl_lift[1],t));
      const happy=A.happy.reduce((s,[a,b])=>Math.max(s,smooth(a,a+.3,t)*(1-smooth(b-.3,b,t))),0);
      return {
        head:{pivot:[1450,625], rot:(.75*sin(t,6.3)+.25*sin(t,3.9,1)+.7*happy*sin(t,1.3))*(1-.7*sl)-1.7*sl-.6*perk,
              dx:1.2*sin(t,7.7,2)+1*sl, dy:1.8*br-3*perk+2.4*nod+6*sl},
        ahoge:{pivot:[1405,342], rot:2.2*sin(t,2.7)+7*ring(t,A.perk,1.1,2.6)+2.2*sin(t,1.15,1)*(1-sl)},
        hairLong:{wave:{amp:[1.8,3.6],k:[.012,.022],w:1.25,from:[1620,525],dir:[.75,.66],len:230}},
        tuft:{pivot:[1305,525], rot:1.3*sin(t,3.3,.5)+2*ring(t,A.perk,.9,2.2)},
        wisp:{wave:{amp:[1.5,2.6],k:[.05,.01],w:1.9,from:[1240,660],dir:[-1,.2],len:95}},
        body:{pivot:[1440,870], sy:1+.0085*br, sx:1-.0025*br},
        phone:{pivot:[1290,690], rot:.5*sin(t,5.1,1)+.3*sin(t,2.9)-3*sl, dy:1.5*br+1.2*sin(t,4.3)+9*sl, dx:-4*sl},
        bowl:{pivot:[1430,700], rot:.25*sin(t,4.7)-1.2*sl, dy:1.4*br-9*lift+5*sl},
        water:{water:[600,210]},
        cloudA:{dx:.2*t}, cloudB:{dx:.3*t},
        leavesA:{wave:{amp:[2.6,2],k:[.018,.03],w:1.35,from:[600,0],dir:[0,1],len:70}},
        leavesB:{wave:{amp:[2.8,2.4],k:[.02,.018],w:1.5,ph:1,from:[1100,100],dir:[-.8,.6],len:220}},
        vine:{wave:{amp:[3.2,.6],k:[.008,.018],w:1.2,ph:2,from:[1680,0],dir:[0,1],len:300}},
        curtain:{wave:{amp:[4,.8],k:[.012,.016],w:1.1,from:[1320,0],dir:[0,1],len:300}},
        lantern:{pivot:[1555,72], rot:1.1*sin(t,4.3)},
        scallion:{pivot:[712,690], rot:.8*sin(t,3.8)+.3*sin(t,2.1,1)},
        tomato:{pivot:[835,682], rot:.7*sin(t,4.4,1)},
        fish:{dx:5*sin(t,7.3)+1.5*sin(t,3.1,1), dy:3.2*sin(t,5.2,.7)},
        tail:{wave:{amp:[.6,3.6],k:[.2,0],w:9,from:[1034,630],dir:[-1,0],len:38}},
        weedA:{wave:{amp:[2.2,0],k:[0,.05],w:1.3,from:[950,690],dir:[0,-1],len:100}},
        weedB:{wave:{amp:[1.6,0],k:[0,.08],w:1.6,ph:2,from:[1094,692],dir:[0,-1],len:50}},
        dapple:{wave:{amp:[3.4,1.4],k:[.01,.022],w:.85,from:[500,700],dir:[0,1],len:90}},
      };
    },
  };

  const cottage = {
    image:"../../docs/images/cottage_zh.webp", w:1672, h:941,
    regions:[
      {name:"body", blur:14, poly:[[800,420],[880,380],[975,400],[972,560],[925,640],[925,742],[825,748],[815,620],[790,560]]},
      {name:"head", blur:12, poly:[[832,398],[862,362],[885,345],[950,342],[972,396],[988,458],[962,496],[900,502],[840,472]]},
      {name:"ahoge", blur:6, poly:[[882,352],[908,335],[950,343],[956,386],[925,396],[894,376]]},
      {name:"hairBack", blur:9, poly:[[792,482],[858,468],[882,560],[862,596],[800,596],[784,530]]},
      {name:"hands", blur:8, poly:[[920,500],[968,500],[966,562],[922,566]]},
      {name:"bubble", blur:8, poly:[[778,282],[892,282],[898,358],[852,392],[812,402],[782,362]]},
      {name:"marks", blur:6, poly:[[930,308],[998,322],[992,362],[936,362]]},
      {name:"fish", blur:6, poly:[[474,492],[516,492],[516,528],[474,528]]},
      {name:"water", blur:6, poly:[[0,490],[228,492],[228,586],[96,596],[0,604]], cut:[[[36,528],[98,528],[98,612],[36,612]]]},
      {name:"treeA", blur:12, poly:[[0,0],[190,0],[265,70],[250,210],[110,330],[0,340]]},
      {name:"treeB", blur:12, poly:[[1040,0],[1420,0],[1400,70],[1250,130],[1120,110]]},
      {name:"treeC", blur:12, poly:[[440,0],[720,0],[740,50],[640,92],[490,70]]},
      {name:"plant", blur:8, poly:[[628,192],[775,192],[775,270],[720,430],[660,400],[640,280]]},
      {name:"lamp", blur:6, poly:[[780,122],[858,122],[858,238],[780,238]]},
      {name:"curtainL", blur:8, poly:[[280,300],[318,300],[318,520],[280,520]]},
      {name:"curtainR", blur:8, poly:[[482,298],[560,298],[600,540],[535,548],[496,420]]},
      {name:"flowersL", blur:10, poly:[[0,825],[140,810],[230,880],[230,941],[0,941]]},
      {name:"flowersR", blur:10, poly:[[1490,800],[1672,770],[1672,941],[1480,941]]},
      {name:"scallion", blur:6, poly:[[326,442],[378,442],[378,530],[326,530]]},
      {name:"pot", blur:5, poly:[[1250,500],[1336,500],[1336,520],[1250,520]]},
    ],
    eyes:[
      {patch:[[939,454],[945,446],[957,444],[958,455],[956,464],[947,465],[941,460]], above:[955,441], below:[951,468], line:2.4, feather:.8,
       shut:[940,453,949,461,958,450], smile:[940,456,949,443,958,453]},
    ],
    eyesAt(t){ return {shut:0, smile:Math.max(blink(t), A.cottage_grin.reduce((s,[a,b])=>Math.max(s,smooth(a,a+.14,t)*(1-smooth(b-.14,b,t))),0))}; },
    pose(t){
      const hop=Math.sin(t*TAU/.72), br=breath(t);
      return {
        body:{pivot:[880,750], sy:1+.009*hop+.004*br},
        head:{pivot:[905,505], rot:1.1*sin(t,1.44)+.5*sin(t,4.1), dy:-.6*hop},
        ahoge:{pivot:[925,394], rot:4*sin(t,.72,1)},
        hairBack:{wave:{amp:[2.4,1.4],k:[.018,.05],w:3,from:[858,470],dir:[-.6,.8],len:125}},
        hands:{dy:1.5*sin(t,.72,1.4)},
        bubble:{dy:3.2*sin(t,2.3), dx:1.2*sin(t,3.7)},
        marks:{pivot:[945,368], sx:1+.05*sin(t,.72), sy:1+.05*sin(t,.72)},
        fish:{dx:3*sin(t,4.3), dy:1.5*sin(t,3.1)},
        water:{water:[486,160]},
        treeA:{wave:{amp:[3,2.2],k:[.02,.02],w:1.4,from:[0,0],dir:[.7,.7],len:280}},
        treeB:{wave:{amp:[2.6,2.2],k:[.02,.03],w:1.2,ph:1,from:[1230,0],dir:[0,1],len:90}},
        treeC:{wave:{amp:[2.4,1.8],k:[.022,.03],w:1.3,ph:2,from:[580,0],dir:[0,1],len:70}},
        plant:{wave:{amp:[2.8,.5],k:[.01,.03],w:1.25,from:[700,192],dir:[0,1],len:210}},
        lamp:{pivot:[818,124], rot:1.1*sin(t,3.9)},
        curtainL:{wave:{amp:[2,0],k:[0,.022],w:1.2,from:[300,300],dir:[0,1],len:210}},
        curtainR:{wave:{amp:[3,0],k:[0,.018],w:1.05,ph:1,from:[510,298],dir:[0,1],len:240}},
        flowersL:{wave:{amp:[2.4,1],k:[.03,.02],w:1.7,from:[100,941],dir:[0,-1],len:110}},
        flowersR:{wave:{amp:[2.4,1],k:[.03,.02],w:1.5,ph:1.4,from:[1580,941],dir:[0,-1],len:140}},
        scallion:{pivot:[350,528], rot:.9*sin(t,3.3)},
        pot:{dy:.8*Math.sin(t*TAU/.31)},
      };
    },
  };
  return {cover,cottage};
}
window.makeRigs = makeRigs;
