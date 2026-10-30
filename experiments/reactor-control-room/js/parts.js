/* ============================================================
   parts.js — instrument builders (nixie / split-flap / LED / CRT)
   ============================================================ */
(function () {
  var RC = window.RC || (window.RC = {});
  var B = RC.build = {};

  /* ---------------- shared materials ---------------- */
  RC.initMaterials = function () {
    var T = RC.tex;
    function std(o) { return new THREE.MeshStandardMaterial(o); }
    RC.mat = {
      cabinet: std({ map: T.cabinet, color: 0x9aa08f, roughness: 0.62, metalness: 0.30, envMapIntensity: 0.5 }),
      cabinetDark: std({ map: T.cabinetDark, color: 0x8f9484, roughness: 0.68, metalness: 0.32, envMapIntensity: 0.45 }),
      wainscot: std({ map: T.wainscot, color: 0x969b8c, roughness: 0.7, metalness: 0.28, envMapIntensity: 0.4 }),
      steel: std({ color: 0x9aa09a, roughness: 0.42, metalness: 0.88, envMapIntensity: 0.9 }),
      steelDark: std({ color: 0x555b56, roughness: 0.5, metalness: 0.8, envMapIntensity: 0.7 }),
      steelBlack: std({ color: 0x23251f, roughness: 0.55, metalness: 0.7, envMapIntensity: 0.5 }),
      chrome: std({ color: 0xd6dad4, roughness: 0.18, metalness: 1.0, envMapIntensity: 1.2 }),
      brass: std({ color: 0xb08a48, roughness: 0.35, metalness: 0.9, envMapIntensity: 0.9 }),
      copper: std({ color: 0x8a5a3a, roughness: 0.45, metalness: 0.85, envMapIntensity: 0.7 }),
      olive: std({ color: 0x4a5140, roughness: 0.72, metalness: 0.25, envMapIntensity: 0.35 }),
      oliveDark: std({ color: 0x333a2e, roughness: 0.78, metalness: 0.2, envMapIntensity: 0.3 }),
      black: std({ color: 0x121310, roughness: 0.62, metalness: 0.35, envMapIntensity: 0.35 }),
      bakelite: std({ color: 0x1a1611, roughness: 0.5, metalness: 0.2, envMapIntensity: 0.5 }),
      cream: std({ color: 0xd2cbae, roughness: 0.75, metalness: 0.05, envMapIntensity: 0.3 }),
      rubber: std({ color: 0x141412, roughness: 0.95, metalness: 0.0, envMapIntensity: 0.15 }),
      red: std({ color: 0x8e1b12, roughness: 0.5, metalness: 0.25, envMapIntensity: 0.4 }),
      redBright: std({ color: 0xb3281b, roughness: 0.42, metalness: 0.2, envMapIntensity: 0.45 }),
      floor: std({ map: T.floor, color: 0x8a8e87, roughness: 0.72, metalness: 0.45, envMapIntensity: 0.4 }),
      wall: std({ map: T.concrete, color: 0x8a8c80, roughness: 0.92, metalness: 0.02, envMapIntensity: 0.25 }),
      ceiling: std({ map: T.concrete, color: 0x787a70, roughness: 0.95, metalness: 0.0, envMapIntensity: 0.2 }),
      hazard: std({ map: T.hazard, color: 0xc9c2a8, roughness: 0.7, metalness: 0.25, envMapIntensity: 0.35 }),
      glass: new THREE.MeshStandardMaterial({
        color: 0x20302c, roughness: 0.06, metalness: 0.1, transparent: true,
        opacity: 0.10, envMapIntensity: 1.5, side: THREE.DoubleSide, depthWrite: false
      }),
      smoked: new THREE.MeshStandardMaterial({
        color: 0x3c1206, roughness: 0.08, metalness: 0.25, transparent: true,
        opacity: 0.20, envMapIntensity: 1.1, side: THREE.DoubleSide, depthWrite: false
      }),
      tubeGlass: new THREE.MeshStandardMaterial({
        color: 0xffe6d8, roughness: 0.02, metalness: 0.0, transparent: true,
        opacity: 0.07, envMapIntensity: 1.1, side: THREE.DoubleSide, depthWrite: false
      }),
      ledWindow: std({ color: 0x1a0504, roughness: 0.25, metalness: 0.1, envMapIntensity: 0.6 }),
      paper: std({ map: T.paper, color: 0xd8d0b4, roughness: 0.9, metalness: 0.0, envMapIntensity: 0.2 })
    };
  };

  /* ---------------- primitives ---------------- */
  function box(w, h, d, mat) {
    var m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
    // only furniture-scale objects cast shadows (keeps the shadow pass cheap)
    m.castShadow = (w * h * d) > 0.0025;
    m.receiveShadow = true;
    return m;
  }
  function cyl(r1, r2, h, mat, seg) {
    var m = new THREE.Mesh(new THREE.CylinderGeometry(r1, r2, h, seg || 18), mat);
    m.castShadow = true; m.receiveShadow = true; return m;
  }
  B.box = box; B.cyl = cyl;

  B.contactShadow = function (w, d, opacity) {
    var m = new THREE.Mesh(
      new THREE.PlaneGeometry(w, d),
      new THREE.MeshBasicMaterial({ map: RC.tex.contact, transparent: true, opacity: opacity === undefined ? 1 : opacity, depthWrite: false, color: 0x000000 })
    );
    m.rotation.x = -Math.PI / 2;
    m.position.y = 0.012;
    m.renderOrder = 1;
    return m;
  };

  B.plate = function (w, h, texture, emissive) {
    var mat = emissive
      ? new THREE.MeshStandardMaterial({ map: texture, emissiveMap: texture, emissive: 0xffffff, emissiveIntensity: 1.0, roughness: 0.5, metalness: 0.1 })
      : new THREE.MeshStandardMaterial({ map: texture, emissiveMap: texture, emissive: 0x2e2a20, emissiveIntensity: 0.42, roughness: 0.62, metalness: 0.15, envMapIntensity: 0.4 });
    var m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), mat);
    m.receiveShadow = true;
    return m;
  };

  /* ---------------- screws & rivets ---------------- */
  var screwGeo = new THREE.CylinderGeometry(0.006, 0.006, 0.004, 8);
  B.screw = function (x, y, z, mat) {
    var m = new THREE.Mesh(screwGeo, mat || RC.mat.steel);
    m.rotation.x = Math.PI / 2; m.position.set(x, y, z);
    return m;
  };

  /* ---------------- knobs / switches ---------------- */
  B.knob = function (r, h, mat) {
    var g = new THREE.Group();
    var body = cyl(r, r * 0.94, h, mat || RC.mat.bakelite, 28);
    body.rotation.x = Math.PI / 2;
    g.add(body);
    var skirt = cyl(r * 1.16, r * 1.16, 0.006, RC.mat.steelDark, 28);
    skirt.rotation.x = Math.PI / 2; skirt.position.z = -h * 0.45;
    g.add(skirt);
    var pointer = new THREE.Mesh(new THREE.BoxGeometry(r * 0.14, r * 0.72, 0.004), RC.mat.cream);
    pointer.position.set(0, r * 0.42, h * 0.52);
    g.add(pointer);
    g.userData.rotate = function (a) { g.rotation.z = a; };
    return g;
  };

  B.toggle = function (labelTex) {
    var g = new THREE.Group();
    var base = box(0.05, 0.075, 0.012, RC.mat.steelDark);
    g.add(base);
    var lever = cyl(0.005, 0.007, 0.05, RC.mat.chrome, 10);
    lever.geometry.translate(0, 0.025, 0);
    lever.position.z = 0.012; lever.rotation.x = -0.55;
    g.add(lever);
    if (labelTex) {
      var p = new THREE.Mesh(new THREE.PlaneGeometry(0.08, 0.03), new THREE.MeshStandardMaterial({ map: labelTex, roughness: 0.7 }));
      p.position.set(0, -0.055, 0.002); g.add(p);
    }
    g.userData.set = function (up) { lever.rotation.x = up ? -0.55 : 0.55; };
    return g;
  };

  /* ---------------- analog meter ---------------- */
  B.meter = function (o) {
    o = o || {};
    var r = o.r || 0.085, depth = o.depth || 0.055;
    var g = new THREE.Group();
    var body = cyl(r, r, depth, RC.mat.black, 32);
    body.rotation.x = Math.PI / 2; body.position.z = -depth / 2;
    g.add(body);
    var bezel = new THREE.Mesh(new THREE.TorusGeometry(r * 0.96, r * 0.09, 8, 40), RC.mat.steel);
    bezel.position.z = 0.002; g.add(bezel);
    var face = new THREE.Mesh(new THREE.CircleGeometry(r * 0.9, 40),
      new THREE.MeshStandardMaterial({ map: o.face, emissiveMap: o.face, emissive: 0xffffff, emissiveIntensity: 0.22, roughness: 0.55, metalness: 0.05, envMapIntensity: 0.3 }));
    face.position.z = 0.004; g.add(face);
    // needle
    var ng = new THREE.Group();
    var needle = box(r * 0.03, r * 1.28, 0.0025, RC.mat.black);
    needle.geometry.translate(0, r * 0.58, 0);
    ng.add(needle);
    var hub = cyl(r * 0.12, r * 0.12, 0.008, RC.mat.steel, 16);
    hub.rotation.x = Math.PI / 2; ng.add(hub);
    ng.position.z = 0.012; g.add(ng);
    var glass = new THREE.Mesh(new THREE.CircleGeometry(r * 0.9, 32), RC.mat.glass);
    glass.position.z = 0.022; g.add(glass);

    var cur = o.value || 0, target = cur, wob = RC.rnd(0, 6);
    g.userData.set = function (v) { target = v; };
    g.userData.update = function (dt, t) {
      cur += (target - cur) * Math.min(1, dt * 4.5);
      wob += dt;
      var n = Math.sin(wob * 3.1) * 0.004 + Math.sin(wob * 11.7) * 0.002;
      var f = THREE.MathUtils.clamp((cur / (o.max || 100)) + n, -0.015, 1.03);
      ng.rotation.z = THREE.MathUtils.degToRad(135) - f * THREE.MathUtils.degToRad(270);
    };
    g.userData.update(0, 0);
    return g;
  };

  /* ---------------- nixie tube ---------------- */
  var nixiePlaneGeo = new THREE.PlaneGeometry(0.0165, 0.0265);
  B.nixieTube = function (digit) {
    var g = new THREE.Group();
    // bakelite base + green collar (as in the reference photo)
    var base = cyl(0.0105, 0.0115, 0.016, RC.mat.bakelite, 20);
    base.position.y = 0.008; g.add(base);
    var collar = cyl(0.0102, 0.0102, 0.004, new THREE.MeshStandardMaterial({ color: 0x2f5c33, roughness: 0.6, metalness: 0.2 }), 20);
    collar.position.y = 0.018; g.add(collar);
    // pins
    for (var i = 0; i < 8; i++) {
      var a = i / 8 * Math.PI * 2;
      var p = cyl(0.0007, 0.0007, 0.014, RC.mat.steel, 6);
      p.position.set(Math.cos(a) * 0.0075, -0.002, Math.sin(a) * 0.0075);
      g.add(p);
    }
    // dark backing so the numerals read against the cavity
    var backPlate = new THREE.Mesh(new THREE.PlaneGeometry(0.017, 0.030),
      new THREE.MeshBasicMaterial({ color: 0x120402 }));
    backPlate.position.set(0, 0.0395, -0.0035);
    g.add(backPlate);
    // digit plane
    var mat = new THREE.MeshBasicMaterial({
      map: RC.tex.nixie, transparent: true, blending: THREE.AdditiveBlending,
      depthWrite: false, color: 0xffffff, side: THREE.DoubleSide
    });
    var planeGeo = nixiePlaneGeo.clone();
    var baseUV = Float32Array.from(planeGeo.attributes.uv.array);
    var plane = new THREE.Mesh(planeGeo, mat);
    plane.position.y = 0.0395;
    g.add(plane);
    // glass envelope
    var glass = new THREE.Mesh(new THREE.CylinderGeometry(0.0102, 0.0102, 0.05, 20, 1, true), RC.mat.tubeGlass);
    glass.position.y = 0.043; g.add(glass);
    var dome = new THREE.Mesh(new THREE.SphereGeometry(0.0102, 20, 10, 0, 6.283, 0, 1.2), RC.mat.tubeGlass);
    dome.position.y = 0.068; g.add(dome);
    var tip = cyl(0.0025, 0.0015, 0.006, RC.mat.tubeGlass, 8);
    tip.position.y = 0.075; g.add(tip);
    // anode cap
    var cap = cyl(0.0106, 0.0106, 0.003, RC.mat.steel, 20);
    cap.position.y = 0.0705; g.add(cap);

    // soft halo
    var halo = new THREE.Sprite(new THREE.SpriteMaterial({
      map: RC.glowTex, color: 0xff5a18, transparent: true, opacity: 0.16,
      blending: THREE.AdditiveBlending, depthWrite: false
    }));
    halo.scale.set(0.030, 0.030, 1);
    halo.position.y = 0.042;
    halo.raycast = function () { };   // sprites must not block picking
    g.add(halo);

    g.userData.setDigit = function (d) {
      var i = (typeof d === 'number' ? d : 0) % 10;
      var uv = plane.geometry.attributes.uv;
      var u0 = i / 10, u1 = (i + 1) / 10;
      for (var k = 0; k < uv.count; k++) {
        uv.setX(k, baseUV[k * 2] < 0.5 ? u0 + 0.006 : u1 - 0.006);
      }
      uv.needsUpdate = true;
    };
    g.userData.setDigit(digit === undefined ? 0 : digit);
    return g;
  };

  /* ---------------- nixie bank ---------------- */
  B.nixieBank = function (o) {
    o = o || {};
    var cols = o.cols || 4, rows = o.rows || 2, dx = o.dx || 0.032, dy = o.dy || 0.07;
    var g = new THREE.Group();
    var tubes = [];
    for (var r = 0; r < rows; r++) for (var c = 0; c < cols; c++) {
      var t = B.nixieTube(0);
      t.position.set((c - (cols - 1) / 2) * dx, -r * dy, 0);
      g.add(t); tubes.push(t);
      // socket
      var sock = cyl(0.013, 0.013, 0.006, RC.mat.steelDark, 16);
      sock.position.set(t.position.x, -0.002, 0);
      g.add(sock);
    }
    g.userData.tubes = tubes;
    g.userData.set = function (str) {
      str = String(str);
      for (var i = 0; i < tubes.length; i++) {
        var ch = str[i];
        tubes[i].userData.setDigit(ch >= '0' && ch <= '9' ? +ch : 0);
      }
    };
    return g;
  };

  /* ---------------- split-flap module ---------------- */
  B.flapModule = function (w, h) {
    var g = new THREE.Group();
    // recessed black well
    g.add(box(w + 0.008, h + 0.008, 0.012, RC.mat.black));
    var geo = new THREE.PlaneGeometry(w, h);
    var baseUV = Float32Array.from(geo.attributes.uv.array);
    var mat = new THREE.MeshStandardMaterial({
      map: RC.tex.flap, emissiveMap: RC.tex.flap, emissive: 0xffffff, emissiveIntensity: 0.42,
      roughness: 0.75, metalness: 0.05, envMapIntensity: 0.25
    });
    var flap = new THREE.Mesh(geo, mat);
    flap.position.z = 0.0075;
    g.add(flap);
    // shadow above seam
    var seam = new THREE.Mesh(new THREE.PlaneGeometry(w, 0.006), new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.55 }));
    seam.position.set(0, 0, 0.0085); g.add(seam);
    g.userData = { flap: flap, w: w, h: h, index: 0, target: 0, phase: 0, t: 0, delay: 0 };
    g.userData.setChar = function (ch) {
      var i = RC.tex.flapIndex(ch);
      if (i === g.userData.index && g.userData.phase === 0) return;
      g.userData.target = i;
      if (g.userData.phase === 0) { g.userData.phase = 1; g.userData.t = 0; }
    };
    g.userData.setIndex = function (i) {
      var uv = flap.geometry.attributes.uv;
      var cols = RC.tex.flapCols, rows = RC.tex.flapRows;
      var col = i % cols, row = Math.floor(i / cols);
      var u0 = col / cols, u1 = (col + 1) / cols;
      var v1 = 1 - row / rows, v0 = 1 - (row + 1) / rows;
      var pad = 0.0015;
      for (var k = 0; k < uv.count; k++) {
        uv.setXY(k, baseUV[k * 2] < 0.5 ? u0 + pad : u1 - pad,
          baseUV[k * 2 + 1] < 0.5 ? v0 + pad : v1 - pad);
      }
      uv.needsUpdate = true;
      g.userData.index = i;
      // fade seam line brightness
      seam.material.opacity = 0.5;
    };
    g.userData.update = function (dt) {
      var u = g.userData;
      if (u.phase === 0) return;
      u.t += dt;
      var half = 0.11;
      if (u.phase === 1) {
        var k = Math.min(1, u.t / half);
        u.flap.rotation.x = -k * Math.PI / 2;
        u.flap.position.z = 0.0075 + Math.sin(k * Math.PI) * 0.004;
        u.flap.scale.y = 1 - 0.12 * k;
        if (k >= 1) { u.setIndex(u.target); u.phase = 2; u.t = 0; }
      } else {
        var k2 = Math.min(1, u.t / half);
        u.flap.rotation.x = -(1 - k2) * Math.PI / 2;
        u.flap.scale.y = 0.88 + 0.12 * k2;
        if (k2 >= 1) { u.phase = 0; u.flap.rotation.x = 0; u.flap.scale.y = 1; u.flap.position.z = 0.0075; }
      }
    };
    g.userData._cellUpdate = g.userData.update;
    delete g.userData.update;
    g.userData.setIndex(0);
    return g;
  };

  /* ---------------- split-flap display ---------------- */
  B.flapDisplay = function (o) {
    o = o || {};
    var cols = o.cols || 8, rows = o.rows || 5, cw = o.cw || 0.105, ch = o.ch || 0.135;
    var g = new THREE.Group(), cells = [];
    for (var r = 0; r < rows; r++) for (var c = 0; c < cols; c++) {
      var m = B.flapModule(cw, ch);
      m.position.set((c - (cols - 1) / 2) * (cw + 0.012), -(r - (rows - 1) / 2) * (ch + 0.014), 0);
      g.add(m); cells.push(m);
    }
    g.userData.setLines = function (lines, instant) {
      for (var r = 0; r < rows; r++) {
        var s = (lines[r] || '').toUpperCase().padEnd(cols, ' ');
        for (var c = 0; c < cols; c++) {
          var cell = cells[r * cols + c];
          if (instant) {
            cell.userData.setIndex(RC.tex.flapIndex(s[c] || ' '));
            cell.userData.target = cell.userData.index;
            cell.userData.phase = 0;
          } else cell.userData.setChar(s[c] || ' ');
        }
      }
    };
    g.userData.update = function (dt) { for (var i = 0; i < cells.length; i++) cells[i].userData._cellUpdate(dt); };
    return g;
  };

  /* ---------------- 5x7 LED font ---------------- */
  var F57 = {
    ' ': [0, 0, 0, 0, 0, 0, 0],
    'A': [14, 17, 17, 31, 17, 17, 17], 'B': [30, 17, 17, 30, 17, 17, 30],
    'C': [14, 17, 16, 16, 16, 17, 14], 'D': [30, 17, 17, 17, 17, 17, 30],
    'E': [31, 16, 16, 30, 16, 16, 31], 'F': [31, 16, 16, 30, 16, 16, 16],
    'G': [14, 17, 16, 23, 17, 17, 15], 'H': [17, 17, 17, 31, 17, 17, 17],
    'I': [14, 4, 4, 4, 4, 4, 14], 'J': [7, 2, 2, 2, 2, 18, 12],
    'K': [17, 18, 20, 24, 20, 18, 17], 'L': [16, 16, 16, 16, 16, 16, 31],
    'M': [17, 27, 21, 21, 17, 17, 17], 'N': [17, 25, 21, 19, 17, 17, 17],
    'O': [14, 17, 17, 17, 17, 17, 14], 'P': [30, 17, 17, 30, 16, 16, 16],
    'Q': [14, 17, 17, 17, 21, 18, 13], 'R': [30, 17, 17, 30, 20, 18, 17],
    'S': [15, 16, 16, 14, 1, 1, 30], 'T': [31, 4, 4, 4, 4, 4, 4],
    'U': [17, 17, 17, 17, 17, 17, 14], 'V': [17, 17, 17, 17, 17, 10, 4],
    'W': [17, 17, 17, 21, 21, 27, 17], 'X': [17, 17, 10, 4, 10, 17, 17],
    'Y': [17, 17, 10, 4, 4, 4, 4], 'Z': [31, 1, 2, 4, 8, 16, 31],
    '0': [14, 17, 19, 21, 25, 17, 14], '1': [4, 12, 4, 4, 4, 4, 14],
    '2': [14, 17, 1, 2, 4, 8, 31], '3': [31, 2, 4, 2, 1, 17, 14],
    '4': [2, 6, 10, 18, 31, 2, 2], '5': [31, 16, 30, 1, 1, 17, 14],
    '6': [6, 8, 16, 30, 17, 17, 14], '7': [31, 1, 2, 4, 8, 8, 8],
    '8': [14, 17, 17, 14, 17, 17, 14], '9': [14, 17, 17, 15, 1, 2, 12],
    '-': [0, 0, 0, 31, 0, 0, 0], '.': [0, 0, 0, 0, 0, 12, 12],
    '/': [1, 2, 2, 4, 8, 8, 16], ':': [0, 12, 12, 0, 12, 12, 0],
    '%': [17, 2, 4, 8, 16, 17, 0], '>': [8, 4, 2, 1, 2, 4, 8],
    '<': [2, 4, 8, 16, 8, 4, 2], '=': [0, 31, 0, 31, 0, 0, 0],
    '+': [0, 4, 4, 31, 4, 4, 0], '*': [0, 21, 14, 31, 14, 21, 0]
  };
  B.F57 = F57;

  /* ---------------- LED dot-matrix panel ---------------- */
  B.ledPanel = function (o) {
    o = o || {};
    var cols = o.cols || 40, rows = o.rows || 14;
    var dotPx = 12, pad = 2;
    var cw = cols * dotPx, ch = rows * dotPx;
    var cv = RC.cv(cw, ch), ctx = cv.getContext('2d');
    var tex = new THREE.CanvasTexture(cv);
    tex.encoding = THREE.sRGBEncoding; tex.anisotropy = 4;

    var g = new THREE.Group();
    var body = box(o.w || 0.40, o.h || 0.16, 0.03, RC.mat.black);
    g.add(body);
    var screen = new THREE.Mesh(new THREE.PlaneGeometry(o.w || 0.40, o.h || 0.16),
      new THREE.MeshBasicMaterial({ map: tex, color: 0xffffff }));
    screen.position.z = 0.016; g.add(screen);
    // tinted window
    var win = new THREE.Mesh(new THREE.PlaneGeometry((o.w || 0.40) * 1.01, (o.h || 0.16) * 1.01), RC.mat.smoked);
    win.material = new THREE.MeshStandardMaterial({ color: 0x38060a, roughness: 0.1, metalness: 0.4, transparent: true, opacity: 0.30, envMapIntensity: 1.4 });
    win.position.z = 0.019; g.add(win);

    var state = { text: o.text || 'REACTOR CONTROL  UNIT 4', offset: 0, mode: o.mode || 'text', t: 0, t0: 0, bar: 0 };
    var LIT = '#ff2b12', DIM = '#330704';

    function dot(px, py, lit, alpha) {
      var x = px * dotPx + dotPx / 2, y = py * dotPx + dotPx / 2;
      var r = dotPx * 0.235;
      var grd = ctx.createRadialGradient(x, y, 0, x, y, r * 1.26);
      if (lit) {
        grd.addColorStop(0, '#fff4dc'); grd.addColorStop(0.32, '#ff8a44');
        grd.addColorStop(0.66, LIT); grd.addColorStop(1, 'rgba(255,40,10,0)');
      } else {
        grd.addColorStop(0, DIM); grd.addColorStop(0.7, '#170303'); grd.addColorStop(1, 'rgba(0,0,0,0)');
      }
      ctx.fillStyle = grd;
      ctx.beginPath(); ctx.arc(x, y, r * 1.26, 0, 6.283); ctx.fill();
      if (lit) {
        ctx.fillStyle = 'rgba(255,235,196,0.98)';
        ctx.beginPath(); ctx.arc(x, y, r * 0.44, 0, 6.283); ctx.fill();
      }
    }

    function render() {
      ctx.fillStyle = '#080202'; ctx.fillRect(0, 0, cw, ch);
      // subtle unlit dot grid
      for (var y = 0; y < rows; y++) for (var x = 0; x < cols; x++) dot(x, y, false);

      if (state.mode === 'text') {
        var s = state.text.toUpperCase() + '   ';
        var total = s.length * 6;
        var off = Math.floor(state.offset) % total;
        for (var c = 0; c < cols; c++) {
          var ci = Math.floor((c + off) / 6) % s.length;
          var li = (c + off) % 6;
          var glyph = F57[s[ci]] || F57[' '];
          if (li > 4) continue;
          for (var row = 0; row < 7; row++) {
            var bits = glyph[row];
            if (bits & (1 << (4 - li))) {
              var gy = Math.floor((rows - 7) / 2) + row;
              if (gy >= 0 && gy < rows) dot(c, gy, true);
            }
          }
        }
      } else if (state.mode === 'bars') {
        // spectrum-ish bar graph
        for (var bx2 = 0; bx2 < cols; bx2 += 3) {
          var hgt = Math.round((0.5 + 0.5 * Math.sin(state.t * 1.7 + bx2 * 0.35)) * (rows - 2));
          for (var yy = 0; yy < hgt; yy++) dot(bx2, rows - 1 - yy, true);
          dot(bx2 + 1, rows - 1 - hgt, hgt > 0);
        }
      } else if (state.mode === 'wave') {
        for (var xx = 0; xx < cols; xx++) {
          var v = rows / 2 + Math.sin(state.t * 2 + xx * 0.5) * (rows * 0.28) + Math.sin(state.t * 5.3 + xx * 0.14) * 2;
          var yy2 = Math.round(v);
          if (yy2 >= 0 && yy2 < rows) { dot(xx, yy2, true); if (yy2 + 1 < rows) dot(xx, yy2 + 1, false); }
        }
      }
      tex.needsUpdate = true;
    }

    g.userData.canvas = cv;
    g.userData.api = {
      setText: function (t) { state.text = t; state.offset = 0; },
      setMode: function (m) { state.mode = m; },
      tick: function (dt, t) {
        state.t = t;
        state.offset += dt * 9;
        state.t0 += dt;
        if (state.t0 > 0.075) { state.t0 = 0; render(); }
      }
    };
    render();
    return g;
  };

  /* ---------------- 7-segment readout ---------------- */
  var SEG = {
    '0': 'abcdef', '1': 'bc', '2': 'abged', '3': 'abgcd', '4': 'fgbc', '5': 'afgcd',
    '6': 'afgedc', '7': 'abc', '8': 'abcdefg', '9': 'abcdfg', '-': 'g', ' ': ''
  };

  B.segReadout = function (o) {
    o = o || {};
    var digits = o.digits || 5, W = 640, H = 200;
    var cv = RC.cv(W, H), ctx = cv.getContext('2d');
    var tex = new THREE.CanvasTexture(cv); tex.encoding = THREE.sRGBEncoding; tex.anisotropy = 4;
    var g = new THREE.Group();
    var w = o.w || 0.24, h = o.h || 0.075;
    var body = box(w, h, 0.026, RC.mat.black); g.add(body);
    var screen = new THREE.Mesh(new THREE.PlaneGeometry(w * 0.94, h * 0.86), new THREE.MeshBasicMaterial({ map: tex }));
    screen.position.z = 0.014; g.add(screen);
    var color = o.color || '#ff2a10';

    function segPath(x, y, sw, sh, type) {
      var t = Math.max(3, sh * 0.16);
      if (type === 'h') return [[x + t * 0.8, y], [x + sw - t * 0.8, y], [x + sw, y + t / 2], [x + sw - t * 0.8, y + t], [x + t * 0.8, y + t], [x, y + t / 2]];
      return [[x, y + t * 0.8], [x + t / 2, y], [x + t, y + t * 0.8], [x + t, y + sh - t * 0.8], [x + t / 2, y + sh], [x, y + sh - t * 0.8]];
    }
    function poly(pts, on) {
      ctx.beginPath(); ctx.moveTo(pts[0][0], pts[0][1]);
      for (var i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
      ctx.closePath();
      if (on) {
        ctx.shadowColor = color; ctx.shadowBlur = 26;
        ctx.fillStyle = color; ctx.fill();
        ctx.shadowBlur = 0;
        ctx.fillStyle = 'rgba(255,235,210,0.55)'; ctx.fill();
      } else {
        ctx.shadowBlur = 0;
        ctx.fillStyle = 'rgba(120,14,6,0.12)'; ctx.fill();
      }
    }

    function render(value, label) {
      ctx.fillStyle = '#0a0201'; ctx.fillRect(0, 0, W, H);
      var str = String(value);
      var dW = W * 0.78 / digits, gap = dW * 0.13;
      for (var i = 0; i < digits; i++) {
        var ch = str[i] || ' ';
        var on = SEG[ch] || '';
        var ox = W * 0.06 + i * dW + gap / 2, oy = H * 0.16;
        var dw = dW - gap, dh = H * 0.66;
        var st = Math.max(4, dh * 0.15);
        var midY = oy + dh / 2;
        poly(segPath(ox + st, oy, dw - st * 2, st, 'h'), on.indexOf('a') >= 0);
        poly(segPath(ox + dw - st, oy + st * 0.9, st, dh / 2 - st * 1.4, 'v'), on.indexOf('b') >= 0);
        poly(segPath(ox + dw - st, midY + st * 0.4, st, dh / 2 - st * 1.4, 'v'), on.indexOf('c') >= 0);
        poly(segPath(ox + st, oy + dh - st, dw - st * 2, st, 'h'), on.indexOf('d') >= 0);
        poly(segPath(ox, midY + st * 0.4, st, dh / 2 - st * 1.4, 'v'), on.indexOf('e') >= 0);
        poly(segPath(ox, oy + st * 0.9, st, dh / 2 - st * 1.4, 'v'), on.indexOf('f') >= 0);
        poly(segPath(ox + st, midY - st / 2, dw - st * 2, st, 'h'), on.indexOf('g') >= 0);
      }
      if (label) {
        ctx.fillStyle = 'rgba(255,120,60,0.55)';
        ctx.font = '600 34px ' + RC.FONT; ctx.textAlign = 'right';
        ctx.fillText(label, W - 24, H * 0.30);
        ctx.fillStyle = 'rgba(255,90,40,0.35)';
        ctx.font = '500 24px ' + RC.MONO;
        ctx.fillText('UNIT-4', W - 24, H * 0.44);
      }
      tex.needsUpdate = true;
    }
    g.userData.set = function (v, label) { render(v, label); };
    g.userData.set(o.value === undefined ? '00000' : o.value, o.label);
    return g;
  };

  /* ---------------- LED bar graph ---------------- */
  B.barGraph = function (o) {
    o = o || {};
    var n = o.count || 16, g = new THREE.Group();
    var w = o.w || 0.02, h = o.h || 0.008, gap = o.gap || 0.011;
    var on = new THREE.MeshBasicMaterial({ color: o.color || 0xff2a10 });
    var off = new THREE.MeshBasicMaterial({ color: 0x240504 });
    var bars = [];
    for (var i = 0; i < n; i++) {
      var m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), off);
      m.position.set(0, (i - n / 2) * gap, 0.001);
      g.add(m); bars.push(m);
    }
    g.userData.set = function (frac) {
      var k = Math.round(THREE.MathUtils.clamp(frac, 0, 1) * n);
      for (var i = 0; i < n; i++) {
        var lit = i < k;
        if (lit && Math.random() > 0.985) lit = false;
        bars[i].material = lit ? on : off;
      }
    };
    g.userData.set(o.value === undefined ? 0.6 : o.value);
    return g;
  };

  /* ---------------- annunciator tile ---------------- */
  B.annunciator = function (label, sub, color) {
    var g = new THREE.Group();
    var w = 0.115, h = 0.062;
    var body = box(w, h, 0.014, RC.mat.black);
    g.add(body);
    var tex = RC.tex.label(label, sub, { w: 400, h: 200, mainSize: sub ? 44 : 58, subSize: 24, fg: '#e8e0c4' });
    var face = new THREE.Mesh(new THREE.PlaneGeometry(w * 0.94, h * 0.86),
      new THREE.MeshStandardMaterial({ map: tex, roughness: 0.65, metalness: 0.1 }));
    face.position.z = 0.0075; g.add(face);
    // glow layer
    var glowCv = RC.cv(400, 200), gx = glowCv.getContext('2d');
    gx.fillStyle = '#000'; gx.fillRect(0, 0, 400, 200);
    gx.textAlign = 'center';
    gx.fillStyle = color || '#ffb43c';
    gx.font = '600 ' + (sub ? 44 : 58) + 'px ' + RC.FONT;
    gx.fillText(label, 200, sub ? 92 : 122);
    if (sub) { gx.font = '500 24px ' + RC.FONT; gx.fillText(sub, 200, 152); }
    var gtex = new THREE.CanvasTexture(glowCv); gtex.encoding = THREE.sRGBEncoding;
    var glow = new THREE.Mesh(new THREE.PlaneGeometry(w * 0.94, h * 0.86),
      new THREE.MeshBasicMaterial({ map: gtex, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }));
    glow.position.z = 0.0095; g.add(glow);
    g.userData.lamp = { glow: glow, on: false, target: 0, color: color || '#ffb43c' };
    g.userData.setLit = function (v) { g.userData.lamp.target = v ? 1 : 0; };
    g.userData.update = function (dt, t) {
      var L = g.userData.lamp;
      L.on = L.target > 0.5;
      var val = L.on ? (0.75 + 0.25 * Math.sin(t * 6.5)) : 0;
      L.glow.material.opacity += (val - L.glow.material.opacity) * Math.min(1, dt * 12);
    };
    return g;
  };

  /* ---------------- CRT oscilloscope ---------------- */
  B.scope = function (o) {
    o = o || {};
    var W = 512, H = 320, cv = RC.cv(W, H), ctx = cv.getContext('2d');
    var tex = new THREE.CanvasTexture(cv); tex.encoding = THREE.sRGBEncoding;
    var g = new THREE.Group();
    var w = o.w || 0.34, h = o.h || 0.26;
    var body = box(w, h, 0.10, RC.mat.steelDark); g.add(body);
    var face = new THREE.Mesh(new THREE.PlaneGeometry(w * 0.88, h * 0.84), new THREE.MeshBasicMaterial({ map: tex }));
    face.position.z = 0.052; g.add(face);
    var glass = new THREE.Mesh(new THREE.PlaneGeometry(w * 0.92, h * 0.88), RC.mat.glass);
    glass.position.z = 0.056; g.add(glass);

    // knobs
    for (var i = 0; i < 3; i++) {
      var k = B.knob(0.014, 0.01, RC.mat.bakelite);
      k.position.set(-w / 2 + 0.03 + i * 0.05, -h / 2 - 0.02, 0.05);
      g.add(k);
    }

    var trail = [];
    var flat = false;
    function render(t) {
      ctx.fillStyle = '#020b06'; ctx.fillRect(0, 0, W, H);
      // persistence
      ctx.fillStyle = 'rgba(2,11,6,0.26)'; ctx.fillRect(0, 0, W, H);
      // graticule
      ctx.strokeStyle = 'rgba(90,220,150,0.16)'; ctx.lineWidth = 1;
      for (var gx = 0; gx <= 10; gx++) {
        ctx.beginPath(); ctx.moveTo(gx * W / 10, 0); ctx.lineTo(gx * W / 10, H); ctx.stroke();
      }
      for (var gy = 0; gy <= 8; gy++) {
        ctx.beginPath(); ctx.moveTo(0, gy * H / 8); ctx.lineTo(W, gy * H / 8); ctx.stroke();
      }
      ctx.strokeStyle = 'rgba(90,220,150,0.35)';
      ctx.beginPath(); ctx.moveTo(W / 2, 0); ctx.lineTo(W / 2, H); ctx.moveTo(0, H / 2); ctx.lineTo(W, H / 2); ctx.stroke();

      // trace
      ctx.strokeStyle = flat ? 'rgba(120,255,180,0.5)' : 'rgba(120,255,170,0.95)';
      ctx.lineWidth = 2.2; ctx.shadowColor = 'rgba(80,255,150,0.9)'; ctx.shadowBlur = 10;
      ctx.beginPath();
      if (flat) {
        ctx.moveTo(0, H / 2); ctx.lineTo(W, H / 2);
      } else {
        for (var x = 0; x < W; x++) {
          var ph = x / W * Math.PI * 2;
          var v = Math.sin(ph * 3 + t * 2.2) * 0.32 + Math.sin(ph * 7 - t * 0.9) * 0.10 + Math.sin(ph * 23 + t * 5) * 0.018;
          var y = H / 2 - v * H * 0.38;
          if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
      }
      ctx.stroke(); ctx.shadowBlur = 0;

      // labels
      ctx.fillStyle = 'rgba(140,255,190,0.72)';
      ctx.font = '600 22px ' + RC.MONO;
      ctx.fillText('NEUTRON FLUX  CH-1', 18, 30);
      ctx.fillText(flat ? 'SIGNAL LOST' : '2.4 MW  10s/div', 18, H - 18);
      ctx.textAlign = 'right';
      ctx.fillText('HV ON', W - 18, 30);
      ctx.textAlign = 'left';
      // scanlines
      ctx.fillStyle = 'rgba(0,0,0,0.22)';
      for (var sy = 0; sy < H; sy += 3) ctx.fillRect(0, sy, W, 1);
      // roll bar
      var rb = (t * 40) % (H + 80) - 40;
      var lg = ctx.createLinearGradient(0, rb, 0, rb + 60);
      lg.addColorStop(0, 'rgba(140,255,190,0)'); lg.addColorStop(0.5, 'rgba(140,255,190,0.045)'); lg.addColorStop(1, 'rgba(140,255,190,0)');
      ctx.fillStyle = lg; ctx.fillRect(0, rb, W, 60);
      tex.needsUpdate = true;
    }
    var acc = 0;
    g.userData.tick = function (dt, t) {
      acc += dt;
      if (acc > 0.05) { acc = 0; render(t); }
    };
    g.userData.setFlat = function (v) { flat = v; };
    render(0);
    return g;
  };

  /* ---------------- chart recorder ---------------- */
  B.chartRecorder = function (o) {
    o = o || {};
    var W = 256, H = 512, cv = RC.cv(W, H), ctx = cv.getContext('2d');
    var tex = new THREE.CanvasTexture(cv); tex.wrapT = THREE.RepeatWrapping; tex.wrapS = THREE.RepeatWrapping;
    tex.encoding = THREE.sRGBEncoding; tex.repeat.set(1, 1);
    var g = new THREE.Group();
    var w = o.w || 0.26, h = o.h || 0.34;
    var body = box(w, h, 0.12, RC.mat.cabinetDark); g.add(body);
    var paper = new THREE.Mesh(new THREE.PlaneGeometry(w * 0.8, h * 0.62),
      new THREE.MeshStandardMaterial({ map: tex, roughness: 0.9, metalness: 0, envMapIntensity: 0.2, color: 0xe8e0c0 }));
    paper.position.set(0, 0.03, 0.062); g.add(paper);
    // pens
    for (var i = 0; i < 2; i++) {
      var pen = box(w * 0.5, 0.006, 0.006, i ? RC.mat.red : RC.mat.steelDark);
      pen.position.set(0, 0.10 - i * 0.19, 0.068);
      g.add(pen);
    }
    var glass = new THREE.Mesh(new THREE.PlaneGeometry(w * 0.86, h * 0.68), RC.mat.glass);
    glass.position.set(0, 0.03, 0.070); g.add(glass);

    function draw() {
      ctx.fillStyle = '#ded6b8'; ctx.fillRect(0, 0, W, H);
      ctx.strokeStyle = 'rgba(90,80,60,0.35)'; ctx.lineWidth = 1;
      for (var y = 0; y < H; y += 16) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
      for (var x = 0; x < W; x += 32) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
      ctx.strokeStyle = 'rgba(120,30,20,0.85)'; ctx.lineWidth = 1.6; ctx.beginPath();
      for (var yy = 0; yy < H; yy++) {
        var v = 0.5 + 0.22 * Math.sin(yy * 0.03) + 0.10 * Math.sin(yy * 0.11 + 2) + 0.05 * Math.sin(yy * 0.31);
        var px = v * W;
        if (yy === 0) ctx.moveTo(px, yy); else ctx.lineTo(px, yy);
      }
      ctx.stroke();
      ctx.strokeStyle = 'rgba(30,40,80,0.8)'; ctx.beginPath();
      for (var yy2 = 0; yy2 < H; yy2++) {
        var v2 = 0.5 + 0.10 * Math.sin(yy2 * 0.014 + 1.4) + 0.03 * Math.sin(yy2 * 0.22);
        var px2 = v2 * W;
        if (yy2 === 0) ctx.moveTo(px2, yy2); else ctx.lineTo(px2, yy2);
      }
      ctx.stroke();
      ctx.fillStyle = 'rgba(60,55,40,0.75)'; ctx.font = '500 13px ' + RC.MONO;
      ctx.fillText('CH-2  ROD POSITION   %', 8, H - 10);
      tex.needsUpdate = true;
    }
    draw();
    g.userData.tick = function (dt) {
      tex.offset.y -= dt * 0.035;
      if (tex.offset.y < -1) tex.offset.y += 1;
    };
    return g;
  };

  /* ---------------- fluorescent fixture ---------------- */
  B.fluorescent = function (len) {
    var g = new THREE.Group();
    var housing = box(len, 0.09, 0.22, RC.mat.steelDark);
    g.add(housing);
    var tubeMat = new THREE.MeshBasicMaterial({ color: 0xdfe8d2 });
    var tubes = [];
    for (var i = 0; i < 2; i++) {
      var t = cyl(0.018, 0.018, len * 0.92, tubeMat, 10);
      t.rotation.z = Math.PI / 2;
      t.position.set(0, -0.05, -0.05 + i * 0.10);
      g.add(t); tubes.push(t);
    }
    for (var k = 0; k < 2; k++) {
      var cap = box(0.03, 0.05, 0.24, RC.mat.steel);
      cap.position.x = (k ? 1 : -1) * (len / 2 - 0.03);
      g.add(cap);
    }
    g.userData.tubes = tubes;
    g.userData.setIntensity = function (v) {
      tubeMat.color.setRGB(0.75 * v, 0.82 * v, 0.72 * v);
    };
    return g;
  };

  /* ---------------- warning beacon ---------------- */
  B.beacon = function () {
    var g = new THREE.Group();
    var base = cyl(0.055, 0.07, 0.03, RC.mat.steelDark, 16);
    g.add(base);
    var domeMat = new THREE.MeshStandardMaterial({
      color: 0x5a0805, roughness: 0.15, metalness: 0.1, transparent: true,
      opacity: 0.85, emissive: 0xff1a00, emissiveIntensity: 0.6
    });
    var dome = new THREE.Mesh(new THREE.SphereGeometry(0.055, 20, 12, 0, 6.283, 0, Math.PI / 2), domeMat);
    dome.position.y = 0.015; g.add(dome);
    var bulb = new THREE.Mesh(new THREE.SphereGeometry(0.028, 12, 8), new THREE.MeshBasicMaterial({ color: 0xff5a2a }));
    bulb.position.y = 0.032; g.add(bulb);
    g.userData.domeMat = domeMat;
    return g;
  };

  /* ---------------- rotary telephone ---------------- */
  B.phone = function () {
    var g = new THREE.Group();
    var body = box(0.24, 0.075, 0.19, RC.mat.bakelite);
    g.add(body);
    var dial = new THREE.Mesh(new THREE.CylinderGeometry(0.058, 0.058, 0.006, 32),
      new THREE.MeshStandardMaterial({ color: 0x1d1a15, roughness: 0.45, metalness: 0.3 }));
    dial.rotation.x = Math.PI / 2; dial.position.set(-0.028, 0.042, 0.05);
    g.add(dial);
    // finger holes
    for (var i = 0; i < 10; i++) {
      var a = i / 10 * Math.PI * 1.7 + 0.4;
      var h = cyl(0.0085, 0.0085, 0.008, RC.mat.cream, 10);
      h.position.set(-0.028 + Math.cos(a) * 0.036, 0.046, 0.05 + Math.sin(a) * 0.036);
      g.add(h);
    }
    var hs = new THREE.Group();
    var barGeo = THREE.CapsuleGeometry
      ? new THREE.CapsuleGeometry(0.022, 0.14, 4, 12)
      : new THREE.CylinderGeometry(0.022, 0.022, 0.18, 12);
    var bar = new THREE.Mesh(barGeo, RC.mat.bakelite);
    bar.rotation.z = Math.PI / 2; hs.add(bar);
    for (var k = 0; k < 2; k++) {
      var ear = new THREE.Mesh(new THREE.CylinderGeometry(0.034, 0.034, 0.028, 16), RC.mat.bakelite);
      ear.rotation.z = Math.PI / 2;
      ear.position.x = (k ? 1 : -1) * 0.085;
      hs.add(ear);
    }
    hs.position.set(0, 0.085, -0.02); g.add(hs);
    return g;
  };

  /* ---------------- coffee cup ---------------- */
  B.cup = function () {
    var g = new THREE.Group();
    var mat = new THREE.MeshStandardMaterial({ color: 0xd7d2bf, roughness: 0.4, metalness: 0.05 });
    var body = new THREE.Mesh(new THREE.CylinderGeometry(0.036, 0.028, 0.085, 20, 1, true), mat);
    body.position.y = 0.043; body.material.side = THREE.DoubleSide; g.add(body);
    var coffee = new THREE.Mesh(new THREE.CircleGeometry(0.033, 20), new THREE.MeshStandardMaterial({ color: 0x231208, roughness: 0.25 }));
    coffee.rotation.x = -Math.PI / 2; coffee.position.y = 0.072; g.add(coffee);
    var handle = new THREE.Mesh(new THREE.TorusGeometry(0.022, 0.006, 8, 16, Math.PI * 1.3), mat);
    handle.position.set(0.038, 0.045, 0); handle.rotation.y = Math.PI / 2; g.add(handle);
    return g;
  };

  /* ---------------- pipe + flange ---------------- */
  B.pipe = function (r, len, mat, axis) {
    var g = new THREE.Group();
    var p = cyl(r, r, len, mat || RC.mat.steel, 16);
    p.castShadow = false;
    g.add(p);
    for (var i = -1; i <= 1; i += 2) {
      var f = cyl(r * 1.35, r * 1.35, 0.035, RC.mat.steelDark, 16);
      f.position.y = i * (len / 2 - 0.03);
      g.add(f);
    }
    if (axis === 'x') g.rotation.z = Math.PI / 2;
    if (axis === 'z') g.rotation.x = Math.PI / 2;
    return g;
  };

  /* ---------------- valve wheel ---------------- */
  B.valve = function (r) {
    var g = new THREE.Group();
    var wheel = new THREE.Mesh(new THREE.TorusGeometry(r, r * 0.10, 8, 24), RC.mat.redBright);
    g.add(wheel);
    for (var i = 0; i < 4; i++) {
      var spoke = box(r * 1.8, r * 0.09, r * 0.09, RC.mat.redBright);
      spoke.rotation.z = i * Math.PI / 4;
      g.add(spoke);
    }
    var stem = cyl(r * 0.12, r * 0.12, r * 0.5, RC.mat.steel, 10);
    stem.position.z = -r * 0.25; stem.rotation.x = Math.PI / 2;
    g.add(stem);
    return g;
  };

  /* ---------------- glow texture ---------------- */
  RC.glowTex = (function () {
    var S = 128, c = RC.cv(S, S), x = c.getContext('2d');
    var g = x.createRadialGradient(S / 2, S / 2, 0, S / 2, S / 2, S / 2);
    g.addColorStop(0, 'rgba(255,255,255,1)');
    g.addColorStop(0.25, 'rgba(255,220,180,0.55)');
    g.addColorStop(0.6, 'rgba(255,160,80,0.14)');
    g.addColorStop(1, 'rgba(255,120,40,0)');
    x.fillStyle = g; x.fillRect(0, 0, S, S);
    var t = new THREE.CanvasTexture(c); t.encoding = THREE.LinearEncoding; return t;
  })();
})();
