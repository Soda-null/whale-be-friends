// Makes a still picture move: soft masks mark its parts (head, hair, water...),
// and a shader nudges each part every frame. Knows nothing about the story;
// what moves and when lives in rigs.js.
const MAX_REGIONS = 24;
const VERT = `#version 300 es
in vec2 pos; out vec2 uv;
void main(){ uv = pos; gl_Position = vec4(pos.x*2.-1., 1.-pos.y*2., 0., 1.); }`;
const FRAG = `#version 300 es
precision highp float; precision highp sampler2DArray;
uniform sampler2D img, shut, smile; uniform sampler2DArray masks;
uniform vec2 size; uniform int n; uniform float shutK, smileK;
uniform vec4 m[${MAX_REGIONS}], piv[${MAX_REGIONS}], wav[${MAX_REGIONS}], arg[${MAX_REGIONS}], anc[${MAX_REGIONS}];
in vec2 uv; out vec4 color;
void main(){
  vec2 p = uv*size, d = vec2(0.);
  for(int i=0;i<n;i++){
    float k = texture(masks, vec3(uv, float(i))).r;
    if(k < .004) continue;
    vec2 q = p-piv[i].xy;
    vec2 a = vec2(m[i].x*q.x+m[i].y*q.y, m[i].z*q.x+m[i].w*q.y)+piv[i].zw;
    if(arg[i].y > .5){                       // water: stronger towards the viewer
      float g = clamp((p.y-anc[i].x)/anc[i].y, 0., 1.), t = arg[i].x;
      a.x += (.5+2.1*g)*sin(p.y*(.62-.3*g)+t*1.7+2.*sin(p.x*.013+t*.45));
      a.y += (.2+1.1*g)*sin(p.x*.031+p.y*.21+t*1.15);
    } else if(wav[i].x != 0. || wav[i].y != 0.){
      float g = clamp(dot(p-anc[i].xy, anc[i].zw), 0., 1.);
      a += wav[i].xy*g*sin(dot(p, wav[i].zw)-arg[i].x);
    }
    d += k*a;
  }
  vec2 s = (p-d)/size;
  vec4 c = texture(img, s);
  if(shutK > 0.) c = mix(c, texture(shut, s), shutK);
  if(smileK > 0.) c = mix(c, texture(smile, s), smileK);
  color = c;
}`;

class WarpLayer {
  constructor(canvas, rig, scale) {
    this.rig = rig;
    canvas.width = rig.w*scale; canvas.height = rig.h*scale;
    const gl = this.gl = canvas.getContext("webgl2", {preserveDrawingBuffer:true, antialias:false, alpha:false});
    if(!gl) throw new Error("WebGL2 is not available");
    const prog = gl.createProgram();
    for(const [type,src] of [[gl.VERTEX_SHADER,VERT],[gl.FRAGMENT_SHADER,FRAG]]){
      const sh = gl.createShader(type); gl.shaderSource(sh,src); gl.compileShader(sh);
      if(!gl.getShaderParameter(sh,gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(sh));
      gl.attachShader(prog,sh);
    }
    gl.linkProgram(prog); gl.useProgram(prog);
    this.u = name => gl.getUniformLocation(prog,name);
    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([0,0,1,0,0,1,1,1]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0); gl.bindAttribLocation(prog,0,"pos");
    gl.linkProgram(prog); gl.useProgram(prog);
    gl.vertexAttribPointer(gl.getAttribLocation(prog,"pos"),2,gl.FLOAT,false,0,0);
    gl.uniform2f(this.u("size"),rig.w,rig.h);
    gl.uniform1i(this.u("n"),rig.regions.length);
    this.names = rig.regions.map(r=>r.name);
  }
  async load() {
    const {gl,rig} = this;
    const pic = new Image(); pic.src = rig.image; await pic.decode();
    const texture = (unit,name,source) => {
      gl.activeTexture(gl.TEXTURE0+unit); gl.bindTexture(gl.TEXTURE_2D,gl.createTexture());
      gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,source);
      for(const [p,v] of [[gl.TEXTURE_MIN_FILTER,gl.LINEAR],[gl.TEXTURE_MAG_FILTER,gl.LINEAR],[gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE],[gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE]])
        gl.texParameteri(gl.TEXTURE_2D,p,v);
      gl.uniform1i(this.u(name),unit);
    };
    texture(0,"img",pic);
    texture(1,"shut",this.paintEyes(pic,"shut"));
    texture(2,"smile",this.paintEyes(pic,"smile"));
    this.buildMasks();
  }
  // A copy of the picture with her eyes closed: skin over the eye, then one line.
  paintEyes(pic,kind) {
    const {w,h,eyes} = this.rig, cv = document.createElement("canvas"); cv.width=w; cv.height=h;
    const c = cv.getContext("2d",{willReadFrequently:true}); c.drawImage(pic,0,0,w,h);
    const sample = ([x,y]) => { const d=c.getImageData(x-2,y-2,5,5).data; let s=[0,0,0];
      for(let i=0;i<d.length;i+=4){s[0]+=d[i];s[1]+=d[i+1];s[2]+=d[i+2];} return `rgb(${s.map(v=>v/25|0).join()})`; };
    for(const e of eyes){
      const top = sample(e.above), low = sample(e.below);
      const g = c.createLinearGradient(...e.above,...e.below); g.addColorStop(0,top); g.addColorStop(1,low);
      c.save(); c.filter = `blur(${e.feather||1.2}px)`; c.fillStyle = g;
      c.beginPath(); e.patch.forEach(([x,y],i)=>i?c.lineTo(x,y):c.moveTo(x,y)); c.closePath(); c.fill(); c.restore();
      const [x0,y0,cx,cy,x1,y1] = e[kind];
      c.strokeStyle = "#4e2d24"; c.lineCap = "round"; c.lineWidth = e.line;
      c.beginPath(); c.moveTo(x0,y0); c.quadraticCurveTo(cx,cy,x1,y1); c.stroke();
    }
    return cv;
  }
  buildMasks() {
    const {gl,rig} = this, W = rig.w>>1, H = rig.h>>1, n = rig.regions.length;
    const data = new Uint8Array(W*H*n), cv = document.createElement("canvas"); cv.width=W; cv.height=H;
    const c = cv.getContext("2d",{willReadFrequently:true});
    const path = pts => { c.beginPath(); pts.forEach(([x,y],i)=>i?c.lineTo(x/2,y/2):c.moveTo(x/2,y/2)); c.closePath(); c.fill(); };
    rig.regions.forEach((r,layer) => {
      c.globalCompositeOperation = "source-over"; c.clearRect(0,0,W,H);
      c.filter = `blur(${(r.blur??12)/2}px)`; c.fillStyle = "#fff"; path(r.poly);
      if(r.cut){ c.globalCompositeOperation = "destination-out"; r.cut.forEach(path); }
      const px = c.getImageData(0,0,W,H).data;
      for(let i=0;i<W*H;i++) data[layer*W*H+i] = px[i*4+3];
    });
    gl.activeTexture(gl.TEXTURE3); gl.bindTexture(gl.TEXTURE_2D_ARRAY,gl.createTexture());
    gl.pixelStorei(gl.UNPACK_ALIGNMENT,1);
    gl.texImage3D(gl.TEXTURE_2D_ARRAY,0,gl.R8,W,H,n,0,gl.RED,gl.UNSIGNED_BYTE,data);
    gl.texParameteri(gl.TEXTURE_2D_ARRAY,gl.TEXTURE_MIN_FILTER,gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D_ARRAY,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
    gl.uniform1i(this.u("masks"),3);
  }
  draw(t) {
    const {gl,rig} = this, pose = rig.pose(t);
    const m=[],piv=[],wav=[],arg=[],anc=[];
    for(const name of this.names){
      const q = pose[name]||{}, a = (q.rot||0)*Math.PI/180, c=Math.cos(a), s=Math.sin(a), sx=q.sx??1, sy=q.sy??1;
      const P = q.pivot||[0,0], W = q.wave;
      m.push(c*sx-1,-s*sy,s*sx,c*sy-1);
      piv.push(P[0],P[1],q.dx||0,q.dy||0);
      if(q.water){ wav.push(0,0,0,0); arg.push(t,1,0,0); anc.push(q.water[0],q.water[1],0,0); }
      else if(W){ wav.push(W.amp[0],W.amp[1],W.k[0],W.k[1]); arg.push(W.w*t+(W.ph||0),0,0,0);
        anc.push(W.from[0],W.from[1],W.dir[0]/W.len,W.dir[1]/W.len); }
      else { wav.push(0,0,0,0); arg.push(0,0,0,0); anc.push(0,0,0,0); }
    }
    for(const [n,v] of [["m",m],["piv",piv],["wav",wav],["arg",arg],["anc",anc]]) gl.uniform4fv(this.u(n),new Float32Array(v));
    const eyes = rig.eyesAt(t);
    gl.uniform1f(this.u("shutK"),eyes.shut); gl.uniform1f(this.u("smileK"),eyes.smile);
    gl.drawArrays(gl.TRIANGLE_STRIP,0,4);
  }
}
window.WarpLayer = WarpLayer;
