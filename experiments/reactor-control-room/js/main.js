/* ============================================================
   main.js — renderer, player, interactions, loop
   ============================================================ */
(function () {
  var RC = window.RC || (window.RC = {});
  if (THREE.ColorManagement) THREE.ColorManagement.enabled = true;
  var Q = new URLSearchParams(location.search);
  var AUTOSTART = Q.get('autostart') === '1' || Q.get('shot') === '1';

  RC.colliders = [];
  RC.pickables = [];

  /* ---------------- renderer ---------------- */
  var canvas = document.getElementById('scene');
  var renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.outputEncoding = THREE.LinearEncoding;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.92;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  var scene = new THREE.Scene();
  scene.background = new THREE.Color(0x070806);
  scene.fog = new THREE.FogExp2(0x0a0c09, 0.0115);

  var camera = new THREE.PerspectiveCamera(58, window.innerWidth / window.innerHeight, 0.04, 80);
  camera.rotation.order = 'YXZ';

  /* ---------------- environment (custom, dim) ---------------- */
  try {
    var envScene = new THREE.Scene();
    var shell = new THREE.Mesh(
      new THREE.BoxGeometry(14, 8, 14),
      new THREE.MeshBasicMaterial({ color: 0x14170f, side: THREE.BackSide })
    );
    envScene.add(shell);
    // dim ceiling strips
    for (var ex = -1; ex <= 1; ex += 2) {
      for (var ez = -1; ez <= 1; ez += 2) {
        var strip = new THREE.Mesh(new THREE.PlaneGeometry(3.0, 1.2),
          new THREE.MeshBasicMaterial({ color: 0x6f7a58 }));
        strip.position.set(ex * 2.4, 3.85, ez * 2.4);
        strip.rotation.x = Math.PI / 2;
        envScene.add(strip);
      }
    }
    // warm operator glow + red door glow
    var warm = new THREE.Mesh(new THREE.PlaneGeometry(3.2, 2.0), new THREE.MeshBasicMaterial({ color: 0x6a4a20 }));
    warm.position.set(0, 1.2, 3.6); warm.rotation.y = Math.PI;
    envScene.add(warm);
    var redg = new THREE.Mesh(new THREE.PlaneGeometry(2.0, 2.0), new THREE.MeshBasicMaterial({ color: 0x3a0a04 }));
    redg.position.set(0, 1.6, -6.4);
    envScene.add(redg);

    var pmrem = new THREE.PMREMGenerator(renderer);
    var envRT = pmrem.fromScene(envScene, 0.02);
    scene.environment = envRT.texture;
    pmrem.dispose();
  } catch (e) { console.warn('env failed', e); }

  if (Q.get('noenv') === '1') scene.environment = null;

  /* ---------------- world ---------------- */
  RC.initMaterials();

  scene.add(new THREE.HemisphereLight(0x6d7a62, 0x0d0f0a, 0.16));
  scene.add(new THREE.AmbientLight(0x252b24, 0.40));

  RC.buildRoom(scene);
  RC.buildConsoles(scene);

  // emergency wall lamps (red, always dim except alarm)
  var emLamps = [];
  [[-7.8, 2.2, 6.2], [7.8, 2.2, 6.2]].forEach(function (p) {
    var m = new THREE.Mesh(new THREE.SphereGeometry(0.06, 12, 8),
      new THREE.MeshStandardMaterial({ color: 0x3a0603, emissive: 0xff2200, emissiveIntensity: 0.35, roughness: 0.4 }));
    m.position.set(p[0], p[1], p[2]);
    scene.add(m);
    var cage = new THREE.Mesh(new THREE.TorusGeometry(0.07, 0.006, 6, 16), RC.mat.steelDark);
    cage.position.copy(m.position); cage.rotation.y = Math.PI / 2;
    scene.add(cage);
    var l = new THREE.PointLight(0xff2200, 0.16, 4.5, 2);
    l.position.copy(m.position);
    scene.add(l);
    emLamps.push({ mesh: m, mat: m.material, light: l });
  });
  RC.emLamps = emLamps;

  /* ---------------- collect animated bits ---------------- */
  var tickers = [];
  scene.traverse(function (o) {
    var u = o.userData;
    if (u.api && u.api.tick) tickers.push(u.api.tick.bind(u.api));
    if (u.tick) tickers.push(u.tick.bind(u));
    if (u.update) tickers.push(u.update.bind(u));
    if (u.lamp) tickers.push(u.update.bind(u));
  });

  /* ---------------- post processing ---------------- */
  var composer = new THREE.EffectComposer(renderer);
  composer.addPass(new THREE.RenderPass(scene, camera));

  var bloom = new THREE.UnrealBloomPass(new THREE.Vector2(window.innerWidth, window.innerHeight), 0.55, 0.70, 0.90);
  composer.addPass(bloom);

  var GradeShader = {
    uniforms: {
      tDiffuse: { value: null },
      time: { value: 0 },
      alarm: { value: 0 },
      res: { value: new THREE.Vector2(window.innerWidth, window.innerHeight) }
    },
    vertexShader: [
      'varying vec2 vUv;',
      'void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }'
    ].join('\n'),
    fragmentShader: [
      'uniform sampler2D tDiffuse; uniform float time; uniform float alarm; uniform vec2 res;',
      'varying vec2 vUv;',
      'float hash(vec2 p){ return fract(sin(dot(p, vec2(12.9898,78.233))) * 43758.5453); }',
      'void main(){',
      '  vec3 c = texture2D(tDiffuse, vUv).rgb;',
      '  vec2 q = vUv - 0.5;',
      '  float vig = smoothstep(0.92, 0.28, length(q * vec2(1.08, 1.0)));',
      '  c *= mix(0.55, 1.0, vig);',
      '  float n = hash(vUv * res + time * 37.0);',
      '  c += (n - 0.5) * 0.018;',
      '  c *= 1.0 - 0.045 * sin(vUv.y * 780.0);',
      '  c = mix(c, vec3(0.40, 0.015, 0.004), alarm * (1.0 - vig) * 0.32);',
      '  c = pow(max(c, 0.0), vec3(1.0 / 2.2));',
      '  gl_FragColor = vec4(c, 1.0);',
      '}'
    ].join('\n')
  };
  var gradePass = new THREE.ShaderPass(GradeShader);
  gradePass.renderToScreen = true;
  composer.addPass(gradePass);

  /* ---------------- player ---------------- */
  var player = {
    pos: new THREE.Vector3(0, 0, 4.05),
    vel: new THREE.Vector3(),
    vy: 0,
    yaw: 0,
    pitch: -0.02,
    ground: true,
    eye: 1.68,
    radius: 0.30,
    bob: 0
  };
  RC.player = player;

  function applyCamParam() {
    var c = Q.get('cam');
    if (!c) return;
    var p = c.split(',').map(parseFloat);
    if (p.length >= 2) { player.pos.x = p[0]; player.pos.z = p[1]; }
    if (p.length >= 3) player.yaw = p[2];
    if (p.length >= 4) player.pitch = p[3];
    if (p.length >= 5) player.eye = p[4];
  }
  applyCamParam();

  var keys = {};
  window.addEventListener('keydown', function (e) {
    keys[e.code] = true;
    if (e.code === 'Space') e.preventDefault();
    if (e.code === 'KeyE') interact();
    if (e.code === 'KeyR') { player.pos.set(0, 0, 4.05); player.yaw = 0; player.pitch = -0.02; }
    if (e.code === 'KeyF') toggleTorch();
  });
  window.addEventListener('keyup', function (e) { keys[e.code] = false; });

  var locked = false;
  var fallback = false;        // pointer lock unavailable (preview iframe, etc.)
  var dragging = null;
  var pointer = new THREE.Vector2(0, 0);

  function requestLock() {
    if (canvas.requestPointerLock) {
      try { canvas.requestPointerLock(); } catch (e) { }
    }
  }

  function look(dx, dy) {
    player.yaw -= dx * 0.0021;
    player.pitch -= dy * 0.0021;
    player.pitch = THREE.MathUtils.clamp(player.pitch, -1.35, 1.35);
  }

  function enableFallback() {
    if (fallback) return;
    fallback = true;
    document.body.classList.add('fallback');
    hideIntro();
    if (hintEl) hintEl.classList.remove('show');
  }

  document.addEventListener('pointerlockchange', function () {
    locked = document.pointerLockElement === canvas;
    document.body.classList.toggle('locked', locked);
    if (locked) {
      fallback = false;
      document.body.classList.remove('fallback');
      hideIntro();
    } else if (!AUTOSTART && !fallback) showPause();
  });

  canvas.addEventListener('mousedown', function (e) {
    if (locked) { interact(); return; }
    if (AUTOSTART) return;
    dragging = { x: e.clientX, y: e.clientY, moved: 0 };
    if (!fallback) {
      requestLock();
      setTimeout(function () { if (!locked) enableFallback(); }, 450);
    }
  });

  document.addEventListener('mousemove', function (e) {
    pointer.set((e.clientX / window.innerWidth) * 2 - 1, -(e.clientY / window.innerHeight) * 2 + 1);
    if (locked) { look(e.movementX || 0, e.movementY || 0); return; }
    if (!dragging) return;
    var dx = e.clientX - dragging.x, dy = e.clientY - dragging.y;
    dragging.moved += Math.abs(dx) + Math.abs(dy);
    dragging.x = e.clientX; dragging.y = e.clientY;
    look(dx, dy);
  });

  window.addEventListener('mouseup', function (e) {
    if (dragging && fallback && dragging.moved < 8) interactAt(e.clientX, e.clientY);
    dragging = null;
  });

  /* ---------------- collision ---------------- */
  function blocked(x, z) {
    var r = player.radius;
    var c = RC.colliders;
    for (var i = 0; i < c.length; i++) {
      var b = c[i];
      var nx = Math.max(b.minX, Math.min(x, b.maxX));
      var nz = Math.max(b.minZ, Math.min(z, b.maxZ));
      var dx = x - nx, dz = z - nz;
      if (dx * dx + dz * dz < r * r) return true;
    }
    return false;
  }

  function move(dt) {
    var f = (keys['KeyW'] ? 1 : 0) - (keys['KeyS'] ? 1 : 0);
    var s = (keys['KeyD'] ? 1 : 0) - (keys['KeyA'] ? 1 : 0);
    var sp = (keys['ShiftLeft'] || keys['ShiftRight']) ? 3.6 : 1.95;
    var fx = -Math.sin(player.yaw), fz = -Math.cos(player.yaw);
    var rx = Math.cos(player.yaw), rz = -Math.sin(player.yaw);
    var wx = fx * f + rx * s, wz = fz * f + rz * s;
    var len = Math.hypot(wx, wz);
    if (len > 1e-4) { wx /= len; wz /= len; } else { wx = 0; wz = 0; }
    var tvx = wx * sp, tvz = wz * sp;
    var k = Math.min(1, dt * 9);
    player.vel.x += (tvx - player.vel.x) * k;
    player.vel.z += (tvz - player.vel.z) * k;

    var ox = player.pos.x, oz = player.pos.z;
    player.pos.x += player.vel.x * dt;
    if (blocked(player.pos.x, player.pos.z)) { player.pos.x = ox; player.vel.x = 0; }
    player.pos.z += player.vel.z * dt;
    if (blocked(player.pos.x, player.pos.z)) { player.pos.z = oz; player.vel.z = 0; }

    if (keys['Space'] && player.ground) { player.vy = 3.05; player.ground = false; }
    player.vy -= 9.2 * dt;
    player.pos.y += player.vy * dt;
    if (player.pos.y <= 0) { player.pos.y = 0; player.vy = 0; player.ground = true; }

    var speed = Math.hypot(player.vel.x, player.vel.z);
    if (player.ground && speed > 0.3) player.bob += dt * speed * 4.2;
    var bob = player.ground ? Math.sin(player.bob) * 0.014 * Math.min(1, speed) : 0;
    var sway = player.ground ? Math.cos(player.bob * 0.5) * 0.006 * Math.min(1, speed) : 0;

    camera.position.set(player.pos.x + sway, player.eye + player.pos.y + bob, player.pos.z);
    camera.rotation.set(player.pitch, player.yaw, 0, 'YXZ');
  }

  /* ---------------- flashlight ---------------- */
  var torch = new THREE.SpotLight(0xfff0d8, 0, 6.5, 0.42, 0.6, 1.6);
  torch.position.set(0.12, -0.10, 0);
  torch.target.position.set(0, 0, -1);
  camera.add(torch); camera.add(torch.target);
  scene.add(camera);
  var torchOn = false;
  function toggleTorch() {
    torchOn = !torchOn;
    torch.intensity = torchOn ? 1.4 : 0;
    var el = document.getElementById('torch');
    if (el) el.classList.toggle('on', torchOn);
  }

  /* ---------------- interaction ---------------- */
  var ray = new THREE.Raycaster();
  ray.far = 4.2;
  ray.camera = camera;   // required when the target graph contains sprites
  var center = new THREE.Vector2(0, 0);
  var hintEl = document.getElementById('hint');
  var focus = null;

  function findRoot(o) {
    while (o) { if (o.userData && o.userData.__ia) return o; o = o.parent; }
    return null;
  }

  function pickAt(ndc) {
    ray.setFromCamera(ndc || center, camera);
    var hits = ray.intersectObjects(RC.pickables, true);
    if (!hits.length) return null;
    return findRoot(hits[0].object);
  }

  function pick() {
    return pickAt((locked || AUTOSTART) ? center : pointer);
  }

  function interactAt(cx, cy) {
    pointer.set((cx / window.innerWidth) * 2 - 1, -(cy / window.innerHeight) * 2 + 1);
    var o = pickAt(pointer);
    if (o) { o.userData.__ia.action(); focus = o; hintEl.textContent = o.userData.__ia.label; hintEl.classList.add('show'); }
  }

  var pickAcc = 0;
  function updateFocus(dt) {
    if (!locked && !AUTOSTART && !fallback) { hintEl.classList.remove('show'); focus = null; return; }
    pickAcc += dt;
    if (pickAcc < 0.1) return;
    pickAcc = 0;
    var o = pick();
    if (o !== focus) {
      focus = o;
      if (o) { hintEl.textContent = o.userData.__ia.label; hintEl.classList.add('show'); }
      else hintEl.classList.remove('show');
    }
  }

  function interact() {
    var o = focus || pick();
    if (!o) return;
    o.userData.__ia.action();
  }

  /* ---------------- intro / hud ---------------- */
  var intro = document.getElementById('intro');
  var pauseEl = document.getElementById('pause');

  function hideIntro() {
    if (intro) {
      if (AUTOSTART) { intro.style.transition = 'none'; intro.style.display = 'none'; }
      intro.classList.add('gone');
    }
    if (pauseEl) pauseEl.classList.remove('show');
    document.body.classList.add('playing');
  }
  function showPause() {
    if (pauseEl) pauseEl.classList.add('show');
  }
  document.getElementById('enter').addEventListener('click', function () {
    if (AUTOSTART) { hideIntro(); return; }
    requestLock();
    setTimeout(function () { if (!locked) enableFallback(); }, 450);
  });
  if (pauseEl) pauseEl.addEventListener('click', function () { requestLock(); setTimeout(function () { if (!locked) enableFallback(); }, 450); });
  if (AUTOSTART) { hideIntro(); document.body.classList.add('playing'); }

  var hud = {
    pwr: document.getElementById('h-pwr'),
    cool: document.getElementById('h-cool'),
    rods: document.getElementById('h-rods'),
    flow: document.getElementById('h-flow'),
    pwrBar: document.getElementById('h-pwrbar'),
    coolBar: document.getElementById('h-coolbar'),
    clock: document.getElementById('h-clock'),
    state: document.getElementById('h-state'),
    log: document.getElementById('log-line')
  };

  function updateHud(t) {
    var s = RC.state;
    if (hud.pwr) hud.pwr.textContent = s.power.toFixed(1).padStart(5, '0');
    if (hud.cool) hud.cool.textContent = s.coolant.toFixed(1);
    if (hud.rods) hud.rods.textContent = String(Math.round(s.rods)).padStart(3, '0');
    if (hud.flow) hud.flow.textContent = s.flow.toFixed(1);
    if (hud.pwrBar) hud.pwrBar.style.width = THREE.MathUtils.clamp(s.power, 0, 100) + '%';
    if (hud.coolBar) hud.coolBar.style.width = THREE.MathUtils.clamp((s.coolant - 200) / 2, 0, 100) + '%';
    if (hud.clock) {
      var mm = Math.floor(t / 60) % 60, ss = Math.floor(t) % 60;
      hud.clock.textContent = '03:' + String(47 + Math.floor(t / 60)).padStart(2, '0') + ':' + String(ss).padStart(2, '0');
    }
    if (hud.state) {
      hud.state.textContent = s.scram ? 'REACTOR TRIP' : 'NOMINAL';
      hud.state.className = s.scram ? 'val bad' : 'val ok';
    }
  }

  /* ---------------- loop ---------------- */
  var clock = new THREE.Clock();
  var elapsed = 0;
  var stateAcc = 0, hudAcc = 0;
  var flick = { fixture: 3, timer: 3.2, level: 1 };
  var alarmT = 0;

  function animate() {
    requestAnimationFrame(animate);
    var dt = Math.min(clock.getDelta(), 0.05);
    elapsed += dt;

    move(dt);
    updateFocus(dt);

    for (var i = 0; i < tickers.length; i++) tickers[i](dt, elapsed);

    // power drift
    var s = RC.state;
    if (!s.scram) {
      s.power += Math.sin(elapsed * 0.27) * 0.0025 + Math.sin(elapsed * 1.13) * 0.0012;
      s.power = THREE.MathUtils.clamp(s.power, 0, 100);
      s.coolant = 291 + Math.sin(elapsed * 0.21) * 1.4 + (s.power - 72.4) * 0.9;
      s.flow = 86 + Math.sin(elapsed * 0.35 + 1) * 0.7;
    }
    stateAcc += dt;
    if (stateAcc > 0.45) { stateAcc = 0; RC.applyState(); }
    hudAcc += dt;
    if (hudAcc > 0.2) { hudAcc = 0; updateHud(elapsed); }

    // fluorescent flicker
    flick.timer -= dt;
    if (flick.timer <= 0) {
      if (flick.level > 0.9) { flick.level = 0.25; flick.timer = 0.055 + Math.random() * 0.06; }
      else { flick.level = 1; flick.timer = 5 + Math.random() * 9; }
      var fx = RC.fixtures[flick.fixture];
      if (fx) fx.userData.setIntensity(flick.level);
    }
    if (RC.ceilingLights && RC.ceilingLights[1]) {
      RC.ceilingLights[1].intensity = 0.22 * (flick.fixture === 3 ? (0.6 + 0.4 * flick.level) : 1);
    }

    // beacon sweep
    alarmT += dt;
    var spin = s.scram ? 4.5 : 0.7;
    var bAng = alarmT * spin;
    RC.beaconLight.position.x = Math.sin(bAng) * 1.5;
    RC.beaconLight.position.z = -6.0 + Math.cos(bAng) * 0.4;
    var bi = s.scram ? (3.2 + Math.sin(alarmT * 12) * 1.2) : 0.55;
    RC.beaconLight.intensity = bi;
    if (RC.beacon) RC.beacon.userData.domeMat.emissiveIntensity = s.scram ? (1.6 + Math.sin(alarmT * 12) * 0.8) : 0.55;

    // emergency lamps
    if (RC.emLamps) RC.emLamps.forEach(function (l) {
      var v = s.scram ? (0.9 + 0.5 * Math.sin(alarmT * 8)) : 0.22;
      l.mat.emissiveIntensity = v;
      l.light.intensity = s.scram ? 0.7 : 0.12;
    });

    // ceiling lights dip on trip
    if (RC.ceilingLights) RC.ceilingLights.forEach(function (l, i) {
      var base = 0.22;
      l.intensity = (s.scram ? base * 0.45 : base) + (i === 1 ? (flick.level - 1) * 0.15 : 0);
    });
    if (RC.consoleSpot) RC.consoleSpot.intensity = s.scram ? 0.32 : 0.55;

    if (RC.nixieGlow) RC.nixieGlow.intensity = 0.26 + Math.sin(elapsed * 3.1) * 0.03 + (s.scram ? 0 : 0.04);
    if (RC.ledGlow) RC.ledGlow.intensity = 0.20 + (s.scram ? 0.12 : 0);

    // mimic lamps pulse
    if (RC.ui && RC.ui.mimicLamps) {
      RC.ui.mimicLamps.forEach(function (l) {
        l.mat.emissiveIntensity = 1.0 + Math.sin(elapsed * 2 + l.phase) * 0.18;
      });
    }

    // dust
    if (RC.dust) {
      RC.dust.rotation.y += dt * 0.006;
      RC.dust.position.y = Math.sin(elapsed * 0.09) * 0.06;
    }

    // clock
    if (RC.updateClock) RC.updateClock(elapsed);

    // grade pass
    gradePass.uniforms.time.value = elapsed;
    var targetAlarm = s.scram ? 1 : 0;
    gradePass.uniforms.alarm.value += (targetAlarm - gradePass.uniforms.alarm.value) * Math.min(1, dt * 2.5);
    document.body.classList.toggle('alarm', s.scram);

    composer.render();
  }

  window.addEventListener('resize', function () {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
    composer.setSize(window.innerWidth, window.innerHeight);
    bloom.setSize(window.innerWidth, window.innerHeight);
    if (gradePass.uniforms.res) gradePass.uniforms.res.value.set(window.innerWidth, window.innerHeight);
  });

  /* ---------------- boot ---------------- */
  RC.scene = scene; RC.camera = camera; RC.renderer = renderer;
  RC.teleport = function (x, z, yaw, pitch) {
    player.pos.x = x; player.pos.z = z;
    if (yaw !== undefined) player.yaw = yaw;
    if (pitch !== undefined) player.pitch = pitch;
  };
  if (Q.get('scram') === '1') setTimeout(function () { RC.toggleScram(); }, 1500);
  RC.log('SYSTEMS NOMINAL — SHIFT B');
  updateHud(0);

  var loadEl = document.getElementById('loading');
  if (loadEl) loadEl.classList.add('gone');

  animate();
})();
