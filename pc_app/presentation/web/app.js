const $ = (id) => document.getElementById(id);
const fields = ["deadzone", "smoothing", "step", "lost_grace", "speed_multiplier"];
let pending = new Map();
let configTimers = new Map();

function updateMultiplier(value) {
  const multiplier = $("speed_multiplier");
  const current = Math.max(0, Math.min(1.5, Number(value) || 0));
  const position = current / 1.5 * 100;
  multiplier.style.setProperty("--fill", `${position}%`);
  multiplier.style.setProperty("--position", `${position}%`);
  $("multiplier-value").style.top = `${43 + (1 - position / 100) * 200}px`;
  $("multiplier-value").textContent = `×${current.toFixed(1)}`;
}

function sendConfig(key, value) {
  pending.set(key, {value, at:Date.now()});
  clearTimeout(configTimers.get(key));
  configTimers.set(key, setTimeout(() => {
    fetch("/api/config", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({key, value})})
      .then((response) => { if (!response.ok) throw new Error(); })
      .catch(() => { pending.delete(key); });
  }, 120));
}
fields.forEach((key) => {
  const input = $(key);
  input.addEventListener(key === "speed_multiplier" ? "input" : "change", () => {
    sendConfig(key, key === "deadzone" ? Number(input.value) / 100 : Number(input.value));
    if (key === "speed_multiplier") updateMultiplier(input.value);
  });
});
$("run-switch").addEventListener("change", () => action("toggle_running"));
const fullscreenButton = $("fullscreen-button");
async function toggleFullscreen() {
  try {
    if (document.fullscreenElement) await document.exitFullscreen();
    else await document.documentElement.requestFullscreen();
  } catch (_) { /* el navegador puede denegar pantalla completa */ }
}
fullscreenButton.addEventListener("click", toggleFullscreen);
document.addEventListener("fullscreenchange", () => {
  const active = Boolean(document.fullscreenElement);
  fullscreenButton.setAttribute("aria-label", active ? "Salir de pantalla completa" : "Activar pantalla completa");
  fullscreenButton.title = active ? "Salir de pantalla completa" : "Pantalla completa";
});
const helpModal = $("help-modal");
document.querySelectorAll(".info-tip").forEach((button) => button.addEventListener("click", () => {
  $("help-title").textContent = button.dataset.helpTitle;
  $("help-description").textContent = button.dataset.help;
  helpModal.showModal();
}));
$("help-close").addEventListener("click", () => helpModal.close());
helpModal.addEventListener("click", (event) => {
  if (event.target === helpModal) helpModal.close();
});
document.addEventListener("keydown", (event) => {
  if (["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) return;
  if (event.key.toLowerCase() === "h") action("toggle_hands");
  if (event.key.toLowerCase() === "f") toggleFullscreen();
  if (event.key.toLowerCase() === "q" || event.key === "Escape") action("exit");
});
function action(name) { fetch("/api/action", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({action:name})}); }

function updateMeter(id, value, max) {
  const number = Number(value || 0);
  $(id).style.width = `${Math.min(100, Math.abs(number) / Math.max(1, max) * 100)}%`;
}
function updateHandPoint(id, hand, hands, bounds, frameWidth, frameHeight) {
  const marker = $(id);
  const point = hands && hands[hand] ? hands[hand] : null;
  if (!point) { marker.style.display = "none"; return; }
  const scale = Math.max(bounds.width / frameWidth, bounds.height / frameHeight);
  const imageWidth = frameWidth * scale;
  const imageHeight = frameHeight * scale;
  const x = (point.x * imageWidth + (bounds.width - imageWidth) / 2) / bounds.width;
  const y = (point.y * imageHeight + (bounds.height - imageHeight) / 2) / bounds.height;
  marker.style.display = "flex";
  marker.style.left = `${Math.max(0, Math.min(1, x)) * 100}%`;
  marker.style.top = `${Math.max(0, Math.min(1, y)) * 100}%`;
}
async function refresh() {
  try {
    const response = await fetch("/api/state", {cache:"no-store"});
    const state = await response.json();
    if (!state || !Object.keys(state).length) return;
    const running = Boolean(state.running);
    const connected = Boolean(state.connected) || Boolean(state.dry_run);
    $("run-switch").checked = running;
    $("run-label").textContent = running ? "EN MARCHA" : "DETENIDO";
    const visibleHands = Number(state.hands_count || 0);
    const ready = running && visibleHands === 2 && connected;
    const alert = $("status-alert");
    alert.classList.toggle("is-ok", ready);
    $("state-chip").textContent = ready ? "Todo en orden" : !running ? "Control pausado" : !connected ? "Sin conexión BLE" : visibleHands === 1 ? "Falta una mano" : "Faltan las dos manos";
    $("state-detail").textContent = ready ? state.dry_run ? "Seguimiento activo · modo de prueba local." : "Seguimiento activo; ambas ruedas responden por BLE." : !running ? "Carro detenido. Activa el control para seguir las manos." : !connected ? "Verifica la conexión con el vehículo." : visibleHands === 1 ? "La rueda sin mano se mantiene en 0." : "Carro detenido · sin envío por BLE. Mantén ambas manos a la vista.";
    $("ble-dot").style.background = connected ? "#18966b" : "#a7adb5";
    $("ble-label").textContent = state.dry_run ? "BLE sin conectar · prueba local" : (connected ? "BLE conectado" : "BLE desconectado");
    $("ble-name").textContent = state.address || state.device_name || "BBC micro:bit";
    $("camera-source").textContent = `cámara ${state.camera ?? 0}`;
    $("fps").textContent = `${state.fps ?? "--"} fps`;
    const maxSpeed = Number(state.max_speed || 255);
    for (const [side, value] of [["left", Number(state.left || 0)], ["right", Number(state.right || 0)]]) {
      const direction = value > 0 ? "ADELANTE" : value < 0 ? "ATRÁS" : "DETENIDO";
      const stateNode = $(`${side}-state`);
      stateNode.textContent = direction;
      stateNode.style.color = value > 0 ? "#007A33" : value < 0 ? "#A96500" : "#6B6B66";
      $(`${side}-sent`).textContent = `${value > 0 ? "+" : ""}${Math.round(value)}/${maxSpeed}`;
      const detected = Boolean(state.hands && state.hands[side === "left" ? "L" : "R"]);
      $(`${side}-hand`).textContent = detected ? "MANO DETECTADA" : "SIN MANO";
      $(`${side}-hand-dot`).style.background = detected ? "#007A33" : "#B0B0AB";
      $(`${side}-hand`).style.color = detected ? "#007A33" : "#B0B0AB";
    }
    updateMeter("left-meter", state.left, state.max_speed);
    updateMeter("right-meter", state.right, state.max_speed);
    $("left-meter").style.background = Number(state.left) < 0 ? "#A96500" : "#007A33";
    $("right-meter").style.background = Number(state.right) < 0 ? "#A96500" : "#007A33";
    const stage = $("camera-view").getBoundingClientRect();
    updateHandPoint("left-point", "L", state.hands, stage, state.frame_width || 1280, state.frame_height || 720);
    updateHandPoint("right-point", "R", state.hands, stage, state.frame_width || 1280, state.frame_height || 720);
    const neutralHeight = stage.height * Math.max(0, Math.min(0.99, Number(state.deadzone || 0)));
    const topHeight = Math.max(1, (stage.height - neutralHeight) / 2 - 84);
    const bottomHeight = Math.max(1, (stage.height - neutralHeight) / 2);
    document.querySelector(".zones").style.gridTemplateRows = `${topHeight}px ${Math.max(1, neutralHeight)}px ${bottomHeight}px`;
    fields.forEach((key) => {
      const pendingValue = pending.get(key);
      if (pendingValue && Math.abs(Number(state[key]) - pendingValue.value) < 0.001) pending.delete(key);
      else if (pendingValue && Date.now() - pendingValue.at > 1800) pending.delete(key);
      const fieldValue = key === "deadzone" ? Math.round(Number(state[key]) * 100) : state[key];
      if (document.activeElement !== $(key) && !pending.has(key) && fieldValue != null) $(key).value = fieldValue;
    });
    updateMultiplier(state.speed_multiplier);
  } catch (_) { /* se reintenta en el siguiente ciclo */ }
}
setInterval(refresh, 250);
refresh();
