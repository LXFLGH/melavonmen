/* ============================================================
   room.js — the room shell: concrete, steel, pipes, lamps
   ============================================================ */
(function () {
  var RC = window.RC || (window.RC = {});
  var B = RC.build;
  var W = 16, D = 13, H = 4.4;

  RC.room = { W: W, D: D, H: H, minX: -W / 2, maxX: W / 2, minZ: -D / 2, maxZ: D / 2 };

  function cloneMat(mat, rx, ry) {
    var m = mat.clone();
    if (m.map) { m.map = m.map.clone(); m.map.needsUpdate = true; m.map.wrapS = m.map.wrapT = THREE.RepeatWrapping; m.map.repeat.set(rx, ry); }
    return m;
  }

  RC.buildRoom = function (scene) {
    var g = new THREE.Group();
    scene.add(g);

    /* ---------- floor ---------- */
    var floor = new THREE.Mesh(new THREE.PlaneGeometry(W, D), RC.mat.floor);
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    g.add(floor);

    // floor plates border shadow
    var edgeMat = new THREE.MeshStandardMaterial({ color: 0x2a2d28, roughness: 0.8, metalness: 0.3 });

    /* ---------- ceiling ---------- */
    var ceil = new THREE.Mesh(new THREE.PlaneGeometry(W, D), cloneMat(RC.mat.ceiling, 4, 3.2));
    ceil.rotation.x = Math.PI / 2;
    ceil.position.y = H;
    g.add(ceil);

    // slab beams
    var beamMat = new THREE.MeshStandardMaterial({ color: 0x4c5247, roughness: 0.7, metalness: 0.45, envMapIntensity: 0.4 });
    for (var bz = -5.2; bz <= 5.3; bz += 2.6) {
      var b = B.box(W, 0.34, 0.16, beamMat);
      b.position.set(0, H - 0.20, bz);
      b.castShadow = false;
      g.add(b);
      var b2 = B.box(W, 0.06, 0.42, beamMat);
      b2.position.set(0, H - 0.045, bz);
      b2.castShadow = false;
      g.add(b2);
    }

    /* ---------- walls ---------- */
    function wall(cx, cz, len, rotY) {
      var grp = new THREE.Group();
      grp.position.set(cx, 0, cz);
      grp.rotation.y = rotY;

      // concrete upper
      var mat = cloneMat(RC.mat.wall, len / 4, 1.1);
      var up = new THREE.Mesh(new THREE.PlaneGeometry(len, H - 1.35), mat);
      up.position.set(0, 1.35 + (H - 1.35) / 2, 0);
      up.receiveShadow = true;
      grp.add(up);

      // steel wainscot
      var wmat = cloneMat(RC.mat.wainscot, len / 2.0, 0.62);
      var low = B.box(len, 1.35, 0.10, wmat);
      low.position.set(0, 0.675, 0.05);
      low.castShadow = false;
      grp.add(low);

      // trim rails
      var railMat = RC.mat.steelDark;
      for (var i = 0; i < 3; i++) {
        var rail = B.box(len, 0.045, 0.06, railMat);
        rail.position.set(0, 0.02 + i * 0.66, 0.11);
        rail.castShadow = false;
        grp.add(rail);
      }
      var topRail = B.box(len, 0.10, 0.14, railMat);
      topRail.position.set(0, 1.36, 0.08);
      topRail.castShadow = false;
      grp.add(topRail);

      // expansion joint every 4 m
      for (var s = -len / 2 + 4; s < len / 2; s += 4) {
        var seam = B.box(0.035, H - 1.35, 0.02, edgeMat);
        seam.position.set(s, 1.35 + (H - 1.35) / 2, 0.012);
        seam.castShadow = false;
        grp.add(seam);
      }
      g.add(grp);
      return grp;
    }

    wall(0, -D / 2, W, 0);            // north (door wall)
    wall(0, D / 2, W, Math.PI);       // south
    wall(-W / 2, 0, D, Math.PI / 2);  // west
    wall(W / 2, 0, D, -Math.PI / 2);  // east

    /* ---------- I-beam columns ---------- */
    var colMat = new THREE.MeshStandardMaterial({ color: 0x414a3d, roughness: 0.68, metalness: 0.5, envMapIntensity: 0.4 });
    function column(x, z) {
      var c = new THREE.Group();
      c.position.set(x, 0, z);
      var web = B.box(0.12, H, 0.26, colMat); web.position.y = H / 2; c.add(web);
      var f1 = B.box(0.34, H, 0.05, colMat); f1.position.set(0, H / 2, 0.145); c.add(f1);
      var f2 = B.box(0.34, H, 0.05, colMat); f2.position.set(0, H / 2, -0.145); c.add(f2);
      var plate = B.box(0.42, 0.12, 0.42, colMat); plate.position.y = 0.06; c.add(plate);
      g.add(c);
    }
    column(-8 + 0.24, -3.2); column(-8 + 0.24, 3.2);
    column(8 - 0.24, -3.2); column(8 - 0.24, 3.2);
    column(-4.2, -6.5 + 0.26); column(4.2, -6.5 + 0.26);

    /* ---------- blast door (north) ---------- */
    var doorG = new THREE.Group();
    doorG.position.set(0, 0, -D / 2 + 0.18);
    g.add(doorG);

    var frame = B.box(2.72, 3.22, 0.30, RC.mat.steelDark);
    frame.position.set(0, 1.61, 0.14);
    doorG.add(frame);
    var leafMat = cloneMat(RC.mat.cabinetDark, 1.6, 1.4);
    var leaf = B.box(2.30, 2.96, 0.16, leafMat);
    leaf.position.set(0, 1.48, 0.30);
    doorG.add(leaf);

    // door ribs
    for (var dr = 0; dr < 3; dr++) {
      var rib = B.box(2.16, 0.07, 0.05, RC.mat.steelDark);
      rib.position.set(0, 0.55 + dr * 0.86, 0.39);
      doorG.add(rib);
    }
    // wheel handle
    var wheel = B.valve(0.30);
    wheel.position.set(0, 1.35, 0.46);
    doorG.add(wheel);
    var hinge = B.cyl(0.06, 0.06, 1.1, RC.mat.steelDark, 12);
    hinge.position.set(-1.08, 1.35, 0.37);
    doorG.add(hinge);
    // hazard base
    var hz = new THREE.Mesh(new THREE.PlaneGeometry(2.34, 0.22),
      new THREE.MeshStandardMaterial({ map: RC.tex.hazard.clone(), roughness: 0.7, metalness: 0.2 }));
    hz.material.map.wrapS = hz.material.map.wrapT = THREE.RepeatWrapping;
    hz.material.map.repeat.set(6, 0.6);
    hz.position.set(0, 0.13, 0.395);
    doorG.add(hz);

    // porthole
    var port = new THREE.Mesh(new THREE.CircleGeometry(0.14, 24),
      new THREE.MeshBasicMaterial({ color: 0x2a0703 }));
    port.position.set(0, 2.42, 0.395); doorG.add(port);
    var portRing = new THREE.Mesh(new THREE.TorusGeometry(0.145, 0.022, 8, 28), RC.mat.steel);
    portRing.position.set(0, 2.42, 0.40); doorG.add(portRing);
    var portGlow = new THREE.Mesh(new THREE.CircleGeometry(0.12, 20),
      new THREE.MeshBasicMaterial({ color: 0x7a1a08, transparent: true, opacity: 0.75 }));
    portGlow.position.set(0, 2.42, 0.393); doorG.add(portGlow);

    // stencil above door
    var signTex = RC.tex.stencil('REACTOR HALL  ·  NO ENTRY', { w: 1024, h: 128, size: 62, color: 'rgba(196,60,40,0.85)' });
    var sign = new THREE.Mesh(new THREE.PlaneGeometry(1.6, 0.2), new THREE.MeshBasicMaterial({ map: signTex, transparent: true }));
    sign.position.set(0, 3.42, 0.05); doorG.add(sign);

    // unit stencil
    var unitTex = RC.tex.stencil('UNIT 4', { w: 1024, h: 256, size: 170, spacing: 22, color: 'rgba(206,198,168,0.5)' });
    var unit = new THREE.Mesh(new THREE.PlaneGeometry(1.5, 0.37), new THREE.MeshBasicMaterial({ map: unitTex, transparent: true }));
    unit.position.set(0, 3.78, 0.04); doorG.add(unit);

    /* ---------- caged bulkhead lamps ---------- */
    [-2.15, 2.15].forEach(function (lx) {
      var lamp = new THREE.Group();
      lamp.position.set(lx, 2.32, -D / 2 + 0.30);
      var plate = B.box(0.24, 0.30, 0.06, RC.mat.steelDark);
      plate.position.z = 0.01; lamp.add(plate);
      var bulb = new THREE.Mesh(new THREE.SphereGeometry(0.072, 16, 12),
        new THREE.MeshBasicMaterial({ color: 0xffd9a0 }));
      bulb.position.z = 0.13; lamp.add(bulb);
      var cageMat = RC.mat.steelDark;
      for (var cg = 0; cg < 4; cg++) {
        var bar = B.cyl(0.005, 0.005, 0.17, cageMat, 6);
        bar.position.set(Math.cos(cg * 1.5708) * 0.075, Math.sin(cg * 1.5708) * 0.075, 0.13);
        bar.rotation.x = Math.PI / 2;
        lamp.add(bar);
      }
      var ring1 = new THREE.Mesh(new THREE.TorusGeometry(0.078, 0.006, 6, 20), cageMat);
      ring1.position.z = 0.13; lamp.add(ring1);
      var cap = B.cyl(0.09, 0.09, 0.03, cageMat, 16);
      cap.rotation.x = Math.PI / 2; cap.position.z = 0.20; lamp.add(cap);
      g.add(lamp);

      var pl = new THREE.PointLight(0xffc07a, 0.34, 4.6, 2);
      pl.position.set(lx, 2.28, -D / 2 + 0.55);
      g.add(pl);
    });

    /* ---------- emergency beacon above door ---------- */
    var beacon = B.beacon();
    beacon.position.set(0, 3.55, -D / 2 + 0.28);
    g.add(beacon);
    RC.beacon = beacon;

    var beaconLight = new THREE.SpotLight(0xff2a08, 0.65, 16, 0.55, 0.6, 1.4);
    beaconLight.position.set(0, 3.5, -D / 2 + 0.5);
    beaconLight.target.position.set(0, 1.2, 2.0);
    g.add(beaconLight); g.add(beaconLight.target);
    RC.beaconLight = beaconLight;

    /* ---------- ceiling fluorescents ---------- */
    RC.fixtures = [];
    var fixPositions = [
      [-4.6, -3.4], [0, -3.4], [4.6, -3.4],
      [-4.6, 1.6], [0, 1.6], [4.6, 1.6]
    ];
    fixPositions.forEach(function (p, i) {
      var f = B.fluorescent(1.7);
      f.position.set(p[0], H - 0.30, p[1]);
      g.add(f);
      // drop rods
      for (var k = -1; k <= 1; k += 2) {
        var rod = B.cyl(0.008, 0.008, 0.26, RC.mat.steelDark, 6);
        rod.position.set(p[0] + k * 0.6, H - 0.15, p[1]);
        g.add(rod);
      }
      RC.fixtures.push(f);
    });

    var lampPositions = [[-4.6, -3.4], [4.6, -3.4], [-4.6, 1.6], [4.6, 1.6]];
    RC.ceilingLights = lampPositions.map(function (p) {
      var l = new THREE.PointLight(0xc7d4b2, 0.22, 11, 2);
      l.position.set(p[0], H - 0.45, p[1]);
      g.add(l);
      return l;
    });

    // warm spot on the main console
    var spot = new THREE.SpotLight(0xffcf92, 0.55, 10, 0.66, 0.65, 1.4);
    spot.position.set(0.3, H - 0.32, 2.4);
    spot.target.position.set(0, 0.8, 1.5);
    spot.castShadow = true;
    spot.shadow.mapSize.set(1024, 1024);
    spot.shadow.bias = -0.0006;
    spot.shadow.camera.near = 0.4;
    spot.shadow.camera.far = 10;
    g.add(spot); g.add(spot.target);
    RC.consoleSpot = spot;

    // faint fill from the door side
    var fill = new THREE.PointLight(0x3a4438, 0.16, 9, 2);
    fill.position.set(0, 2.6, -5.2);
    g.add(fill);

    /* ---------- pipes along the ceiling ---------- */
    var pipeGroup = new THREE.Group();
    g.add(pipeGroup);
    var pipeMats = [
      new THREE.MeshStandardMaterial({ color: 0x6f7368, roughness: 0.55, metalness: 0.75, envMapIntensity: 0.6 }),
      new THREE.MeshStandardMaterial({ color: 0x7b4a30, roughness: 0.7, metalness: 0.5 }),
      new THREE.MeshStandardMaterial({ color: 0x3f4c44, roughness: 0.6, metalness: 0.7 })
    ];
    var pipeXs = [-6.4, -5.85, -5.3];
    for (var pi = 0; pi < 3; pi++) {
      var p = B.pipe(0.055 + pi * 0.028, D - 0.4, pipeMats[pi], 'z');
      p.position.set(pipeXs[pi], H - 0.62 - pi * 0.05, 0);
      pipeGroup.add(p);
      // hangers
      for (var hz2 = -5; hz2 <= 5; hz2 += 2.5) {
        var hang = B.box(0.03, 0.38, 0.03, RC.mat.steelDark);
        hang.position.set(pipeXs[pi], H - 0.34, hz2);
        pipeGroup.add(hang);
      }
    }
    // valve wheels on the pipe run
    for (var v = 0; v < 3; v++) {
      var vw = B.valve(0.13);
      vw.rotation.y = Math.PI / 2;
      vw.position.set(pipeXs[v], H - 0.62 - v * 0.05, -2.6 + v * 2.4);
      pipeGroup.add(vw);
    }
    // vertical risers by the west column
    var riser = B.pipe(0.10, 2.2, pipeMats[0], 'y');
    riser.position.set(-7.4, 2.2, 4.4);
    pipeGroup.add(riser);

    /* ---------- cable tray (east) ---------- */
    var tray = new THREE.Group();
    tray.position.set(7.55, 3.35, 0);
    var trayMat = new THREE.MeshStandardMaterial({ color: 0x5c6157, roughness: 0.6, metalness: 0.6 });
    var base = B.box(0.42, 0.03, D - 1.2, trayMat); tray.add(base);
    for (var s2 = -1; s2 <= 1; s2 += 2) {
      var side = B.box(0.03, 0.14, D - 1.2, trayMat);
      side.position.set(s2 * 0.21, 0.08, 0);
      tray.add(side);
    }
    for (var ci = 0; ci < 9; ci++) {
      var cable = B.cyl(0.018 + (ci % 3) * 0.005, 0.018 + (ci % 3) * 0.005, D - 1.3, RC.mat.rubber, 8);
      cable.rotation.x = Math.PI / 2;
      cable.position.set(-0.15 + (ci % 5) * 0.075, 0.05 + Math.floor(ci / 5) * 0.032, 0);
      cable.castShadow = false;
      tray.add(cable);
    }
    g.add(tray);
    // hanger rods
    for (var hz3 = -5.2; hz3 <= 5.2; hz3 += 2.6) {
      var hr = B.cyl(0.008, 0.008, 0.5, RC.mat.steelDark, 6);
      hr.position.set(7.55, 3.62, hz3); g.add(hr);
    }

    /* ---------- floor markings ---------- */
    var yellow = new THREE.MeshStandardMaterial({ color: 0xd8b23a, roughness: 0.8, metalness: 0.05, emissive: 0x2a2208, emissiveIntensity: 0.6 });
    function lineX(x1, x2, z, w) {
      var m = new THREE.Mesh(new THREE.PlaneGeometry(Math.abs(x2 - x1), w || 0.07), yellow);
      m.rotation.x = -Math.PI / 2; m.position.set((x1 + x2) / 2, 0.008, z); g.add(m);
    }
    function lineZ(z1, z2, x, w) {
      var m = new THREE.Mesh(new THREE.PlaneGeometry(w || 0.07, Math.abs(z2 - z1)), yellow);
      m.rotation.x = -Math.PI / 2; m.position.set(x, 0.008, (z1 + z2) / 2); g.add(m);
    }
    // operator walkway box around the main console
    lineX(-2.6, 2.6, 2.55); lineX(-2.6, 2.6, 3.9);
    lineZ(2.55, 3.9, -2.6); lineZ(2.55, 3.9, 2.6);
    // keep-clear box in front of the door
    lineX(-1.6, 1.6, -5.2); lineZ(-6.3, -5.2, -1.6); lineZ(-6.3, -5.2, 1.6);
    // dashed centre aisle
    for (var dz = -4.4; dz < 4.4; dz += 0.9) {
      var dash = new THREE.Mesh(new THREE.PlaneGeometry(0.06, 0.42), yellow);
      dash.rotation.x = -Math.PI / 2; dash.position.set(0.0, 0.008, dz); g.add(dash);
    }

    // painted floor stencil
    var stTex = RC.tex.stencil('REACTOR  CONTROL', { w: 1024, h: 200, size: 96, spacing: 12, color: 'rgba(196,168,74,0.34)' });
    var st = new THREE.Mesh(new THREE.PlaneGeometry(3.4, 0.66), new THREE.MeshStandardMaterial({ map: stTex, transparent: true, roughness: 0.9, metalness: 0.0, depthWrite: false }));
    st.rotation.x = -Math.PI / 2; st.rotation.z = Math.PI;
    st.position.set(0, 0.009, 3.0);
    g.add(st);

    var numTex = RC.tex.stencil('4', { w: 512, h: 512, size: 380, color: 'rgba(196,168,74,0.26)' });
    var num = new THREE.Mesh(new THREE.PlaneGeometry(1.5, 1.5), new THREE.MeshStandardMaterial({ map: numTex, transparent: true, roughness: 0.9, metalness: 0.0, depthWrite: false }));
    num.rotation.x = -Math.PI / 2;
    num.position.set(-2.4, 0.009, -4.4);
    g.add(num);

    // hazard band along the north wall
    var band = new THREE.Mesh(new THREE.PlaneGeometry(9.6, 0.26),
      new THREE.MeshStandardMaterial({ map: RC.tex.hazard.clone(), color: 0xb9b49c, roughness: 0.85, metalness: 0.1 }));
    band.material.map.wrapS = band.material.map.wrapT = THREE.RepeatWrapping;
    band.material.map.repeat.set(14, 0.8);
    band.rotation.x = -Math.PI / 2;
    band.position.set(0, 0.011, -5.35);
    g.add(band);

    // 55 gallon drum
    var drum = new THREE.Group();
    drum.position.set(-6.5, 0, 4.9);
    var dMat = new THREE.MeshStandardMaterial({ color: 0x4a5a48, roughness: 0.7, metalness: 0.45, envMapIntensity: 0.4 });
    var dBody = B.cyl(0.29, 0.29, 0.88, dMat, 24);
    dBody.position.y = 0.44; drum.add(dBody);
    for (var dr2 = 0; dr2 < 2; dr2++) {
      var ring = new THREE.Mesh(new THREE.TorusGeometry(0.293, 0.012, 6, 24), RC.mat.steelDark);
      ring.rotation.x = Math.PI / 2; ring.position.y = 0.25 + dr2 * 0.38; drum.add(ring);
    }
    var dLbl = new THREE.Mesh(new THREE.PlaneGeometry(0.26, 0.18),
      new THREE.MeshStandardMaterial({ map: RC.tex.label('COOLANT', 'DO NOT DRINK', { w: 512, h: 320, mainSize: 60, subSize: 26, bg: '#8d1b12', fg: '#efe6cc' }), roughness: 0.8 }));
    dLbl.position.set(0, 0.55, 0.291); drum.add(dLbl);
    g.add(drum);

    // rolling tool cart
    var cart = new THREE.Group();
    cart.position.set(6.6, 0, 4.5);
    var cMat = new THREE.MeshStandardMaterial({ color: 0x7d3a20, roughness: 0.65, metalness: 0.4 });
    var cBody = B.box(0.62, 0.62, 0.42, cMat);
    cBody.position.y = 0.42; cart.add(cBody);
    for (var cw = 0; cw < 2; cw++) {
      var drawer = B.box(0.56, 0.04, 0.02, RC.mat.steel);
      drawer.position.set(0, 0.24 + cw * 0.18, 0.215); cart.add(drawer);
    }
    var handle = B.cyl(0.012, 0.012, 0.5, RC.mat.steel, 8);
    handle.rotation.z = Math.PI / 2; handle.position.set(0, 0.80, -0.19); cart.add(handle);
    for (var cw2 = -1; cw2 <= 1; cw2 += 2) for (var cd = -1; cd <= 1; cd += 2) {
      var wheel = B.cyl(0.055, 0.055, 0.03, RC.mat.rubber, 12);
      wheel.rotation.x = Math.PI / 2;
      wheel.position.set(cw2 * 0.24, 0.055, cd * 0.16);
      cart.add(wheel);
    }
    g.add(cart);

    // drain grate
    var drain = new THREE.Mesh(new THREE.PlaneGeometry(0.5, 0.5),
      new THREE.MeshStandardMaterial({ map: RC.tex.perf, roughness: 0.8, metalness: 0.6 }));
    drain.rotation.x = -Math.PI / 2; drain.position.set(5.2, 0.006, 4.6); g.add(drain);

    /* ---------- wall props ---------- */
    // clock
    var clock = new THREE.Group();
    clock.position.set(7.86, 2.9, 3.8);
    clock.rotation.y = -Math.PI / 2;
    var cbody = B.cyl(0.26, 0.26, 0.09, RC.mat.steelDark, 30);
    cbody.rotation.x = Math.PI / 2; clock.add(cbody);
    var cface = new THREE.Mesh(new THREE.CircleGeometry(0.235, 32),
      new THREE.MeshStandardMaterial({ map: RC.tex.clock, roughness: 0.6 }));
    cface.position.z = 0.05; clock.add(cface);
    var hh = new THREE.Group(); hh.position.z = 0.055; clock.add(hh);
    var h1 = B.box(0.012, 0.13, 0.006, RC.mat.black); h1.geometry.translate(0, 0.065, 0); hh.add(h1);
    var h2 = new THREE.Group(); h2.position.z = 0.06; clock.add(h2);
    var m1 = B.box(0.008, 0.19, 0.005, RC.mat.black); m1.geometry.translate(0, 0.095, 0); h2.add(m1);
    var sec = new THREE.Group(); sec.position.z = 0.064; clock.add(sec);
    var s1 = B.box(0.004, 0.20, 0.003, RC.mat.red); s1.geometry.translate(0, 0.10, 0); sec.add(s1);
    var glass = new THREE.Mesh(new THREE.CircleGeometry(0.235, 28), RC.mat.glass);
    glass.position.z = 0.072; clock.add(glass);
    g.add(clock);
    RC.clock = { h: hh, m: h2, s: sec };

    // fire extinguisher
    var ext = new THREE.Group();
    ext.position.set(-3.9, 0, 6.15);
    var tank = B.cyl(0.09, 0.09, 0.52, RC.mat.redBright, 18);
    tank.position.y = 0.34; ext.add(tank);
    var top = new THREE.Mesh(new THREE.SphereGeometry(0.09, 16, 8, 0, 6.283, 0, 1.3), RC.mat.redBright);
    top.position.y = 0.60; ext.add(top);
    var nozzle = B.cyl(0.012, 0.012, 0.16, RC.mat.black, 8);
    nozzle.position.set(0.07, 0.60, 0); nozzle.rotation.z = -0.6; ext.add(nozzle);
    var bracket = B.box(0.06, 0.06, 0.04, RC.mat.steelDark);
    bracket.position.set(0, 0.55, -0.09); ext.add(bracket);
    var extLabel = new THREE.Mesh(new THREE.PlaneGeometry(0.09, 0.06),
      new THREE.MeshStandardMaterial({ map: RC.tex.label('CO2', 'PRESS.', { w: 256, h: 160, mainSize: 70, subSize: 30 }), roughness: 0.7 }));
    extLabel.position.set(0, 0.36, 0.092); ext.add(extLabel);
    g.add(ext);

    // wall notice board + papers
    var board = new THREE.Group();
    board.position.set(-7.86, 2.35, 3.4);
    board.rotation.y = Math.PI / 2;
    var cork = B.box(0.9, 0.62, 0.04, new THREE.MeshStandardMaterial({ color: 0x6b5636, roughness: 0.95 }));
    board.add(cork);
    for (var pp = 0; pp < 4; pp++) {
      var paper = new THREE.Mesh(new THREE.PlaneGeometry(0.26, 0.34),
        new THREE.MeshStandardMaterial({ map: RC.tex.paper, roughness: 0.95, color: 0xe0d8bc }));
      paper.position.set(-0.28 + (pp % 2) * 0.4, 0.12 - Math.floor(pp / 2) * 0.3, 0.025);
      paper.rotation.z = RC.rnd(-0.05, 0.05);
      board.add(paper);
    }
    g.add(board);

    // electrical cabinet on the west wall
    var cab = new THREE.Group();
    cab.position.set(-7.62, 0, 4.9);
    cab.rotation.y = Math.PI / 2;
    var cabBody = B.box(0.9, 1.9, 0.42, RC.mat.cabinetDark);
    cabBody.position.y = 0.95; cab.add(cabBody);
    var cabDoor = B.box(0.44, 1.8, 0.03, RC.mat.cabinet);
    cabDoor.position.set(-0.22, 0.95, 0.225); cab.add(cabDoor);
    var cabDoor2 = B.box(0.44, 1.8, 0.03, RC.mat.cabinet);
    cabDoor2.position.set(0.22, 0.95, 0.225); cab.add(cabDoor2);
    var handles = B.box(0.02, 0.12, 0.02, RC.mat.steel);
    handles.position.set(0, 0.95, 0.25); cab.add(handles);
    var cabLabel = new THREE.Mesh(new THREE.PlaneGeometry(0.34, 0.10),
      new THREE.MeshStandardMaterial({ map: RC.tex.label('480 V  BUS 4B', 'DANGER', { w: 512, h: 160, mainSize: 44, subSize: 30, fg: '#d8cba8' }), roughness: 0.7 }));
    cabLabel.position.set(0, 1.66, 0.243); cab.add(cabLabel);
    g.add(cab);

    // shelving with binders (south wall)
    var shelf = new THREE.Group();
    shelf.position.set(4.4, 0, 6.0);
    shelf.rotation.y = Math.PI;
    var shMat = new THREE.MeshStandardMaterial({ color: 0x4a5245, roughness: 0.7, metalness: 0.4 });
    for (var sh = 0; sh < 3; sh++) {
      var plank = B.box(1.5, 0.035, 0.4, shMat);
      plank.position.set(0, 0.42 + sh * 0.5, 0); shelf.add(plank);
    }
    for (var sp = -1; sp <= 1; sp += 2) {
      var post = B.box(0.05, 1.5, 0.4, shMat);
      post.position.set(sp * 0.72, 0.75, 0); shelf.add(post);
    }
    var binderColors = [0x5a3a2a, 0x2f3a2a, 0x3a3a44, 0x6a5230];
    for (var bk = 0; bk < 11; bk++) {
      var bw = RC.rnd(0.05, 0.09);
      var binder = B.box(bw, RC.rnd(0.26, 0.33), 0.28,
        new THREE.MeshStandardMaterial({ color: binderColors[bk % 4], roughness: 0.8 }));
      binder.position.set(-0.62 + bk * 0.115, 0.58 + (bk % 2) * 0.5, 0.02);
      binder.rotation.z = RC.rnd(-0.02, 0.02);
      shelf.add(binder);
    }
    g.add(shelf);

    /* ---------- floor cables ---------- */
    function cableRun(points, radius) {
      var curve = new THREE.CatmullRomCurve3(points.map(function (p) { return new THREE.Vector3(p[0], p[1], p[2]); }));
      var geo = new THREE.TubeGeometry(curve, 24, radius, 6, false);
      var m = new THREE.Mesh(geo, RC.mat.rubber);
      m.castShadow = false; m.receiveShadow = true;
      g.add(m);
    }
    cableRun([[-7.2, 0.03, -1.0], [-6.0, 0.03, 0.6], [-4.0, 0.03, 1.4], [-2.1, 0.03, 1.2]], 0.020);
    cableRun([[7.2, 0.03, -1.4], [6.0, 0.03, 0.4], [3.6, 0.03, 2.2], [2.2, 0.03, 2.9]], 0.017);
    cableRun([[-3.4, 0.03, -5.9], [-2.4, 0.03, -4.4], [-1.6, 0.03, -2.4], [-2.0, 0.03, 1.2]], 0.014);

    /* ---------- colliders ---------- */
    RC.colliders.push(
      { minX: -W / 2 - 1, maxX: W / 2 + 1, minZ: -D / 2 - 1, maxZ: -D / 2 + 0.15 },
      { minX: -W / 2 - 1, maxX: W / 2 + 1, minZ: D / 2 - 0.15, maxZ: D / 2 + 1 },
      { minX: -W / 2 - 1, maxX: -W / 2 + 0.15, minZ: -D / 2 - 1, maxZ: D / 2 + 1 },
      { minX: W / 2 - 0.15, maxX: W / 2 + 1, minZ: -D / 2 - 1, maxZ: D / 2 + 1 },
      { minX: -1.35, maxX: 1.35, minZ: -D / 2, maxZ: -D / 2 + 0.45 },
      { minX: 3.5, maxX: 5.3, minZ: 5.75, maxZ: 6.5 },
      { minX: -8, maxX: -7.2, minZ: 3.3, maxZ: 5.4 }
    );

    /* ---------- dust ---------- */
    var dustGeo = new THREE.BufferGeometry();
    var N = 520, pos = new Float32Array(N * 3);
    for (var i = 0; i < N; i++) {
      pos[i * 3] = RC.rnd(-7.6, 7.6);
      pos[i * 3 + 1] = RC.rnd(0.3, 4.2);
      pos[i * 3 + 2] = RC.rnd(-6.2, 6.2);
    }
    dustGeo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    var dust = new THREE.Points(dustGeo, new THREE.PointsMaterial({
      color: 0xc8c8b0, size: 0.012, transparent: true, opacity: 0.35,
      depthWrite: false, blending: THREE.AdditiveBlending
    }));
    g.add(dust);
    RC.dust = dust;

    /* ---------- clock hands ---------- */
    RC.updateClock = function (t) {
      if (!RC.clock) return;
      RC.clock.s.rotation.z = -t * 0.6;
      RC.clock.m.rotation.z = -t * 0.02 - 1.1;
      RC.clock.h.rotation.z = -t * 0.0017 - 0.6;
    };

    return g;
  };

  RC.addCollider = function (x, z, w, d) {
    RC.colliders.push({ minX: x - w / 2, maxX: x + w / 2, minZ: z - d / 2, maxZ: z + d / 2 });
  };
})();
