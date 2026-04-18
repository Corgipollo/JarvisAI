/* ═══════════════════════════════════════════════════
   JARVIS AI — Voice-First. Solo habla. Sin wake word.
   ═══════════════════════════════════════════════════ */

const WS_URL = 'ws://127.0.0.1:8766/ws';
const API_URL = 'http://127.0.0.1:8766/api';

let ws = null;
let currentResponse = '';
let isStreaming = false;
let reconnectAttempts = 0;

// Voice
let micStream = null;
let audioContext = null;
let analyser = null;
let mediaRecorder = null;
let audioChunks = [];
let isSpeaking = false;
let jarvisTalking = false;
let silenceTimer = null;
let speechStart = 0;
let vadInterval = null;
let noiseFloor = 2; // se calibra

// DOM
const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const voiceIndicator = document.getElementById('voice-indicator');
const rightPanel = document.getElementById('right-panel');
const cameraImg = document.getElementById('camera-img');
const timeWidget = document.getElementById('time-widget');
const weatherWidget = document.getElementById('weather-widget');
const locationWidget = document.getElementById('location-widget');
const projectsList = document.getElementById('projects-list');

// ═══ WS ═══
function connect() {
  ws = new WebSocket(WS_URL);
  ws.onopen = () => {
    reconnectAttempts = 0;
    dot('status-ollama', true);
    setTimeout(startMic, 800);
    setTimeout(loadInfo, 1500);
    getLocation();
  };
  ws.onmessage = e => handle(JSON.parse(e.data));
  ws.onclose = () => { dot('status-ollama', false); if (reconnectAttempts++ < 10) setTimeout(connect, 2000); };
}

function handle(d) {
  switch (d.type) {
    case 'connected': msg('system', d.message); break;
    case 'response_start':
      isStreaming = true; jarvisTalking = true; currentResponse = '';
      msg('jarvis', '', true);
      break;
    case 'response_chunk':
      currentResponse += d.content;
      updStream(currentResponse);
      break;
    case 'response_end':
      isStreaming = false;
      finStream();
      // Si TTS no llega en 5s, reanudar mic
      setTimeout(() => { if (jarvisTalking) jarvisTalking = false; }, 5000);
      break;
    case 'transcription':
      if (d.text && d.text.length > 2) {
        let txt = d.text.trim();
        // Limpiar "oye jarvis" si lo dijo (ya no es necesario pero por si acaso)
        txt = txt.replace(/^(oye\s+)?(jarvis|jarves|jarbis|jarbi)[,.\s]*/i, '').trim();
        if (txt.length > 1) {
          beep();
          msg('user', txt);
          ws.send(JSON.stringify({ type: 'chat', message: txt, from_voice: true }));
        }
      }
      break;
    case 'audio':
      playTTS(d.data, d.format);
      break;
    case 'action_result':
      showData(d.data);
      break;
    case 'camera_status':
      dot('status-camera', d.active);
      if (d.active) { rightPanel.classList.remove('hidden'); camStream(); }
      break;
    case 'camera_frame':
      cameraImg.src = 'data:image/jpeg;base64,' + d.image;
      break;
  }
}

// ═══ MIC + VAD ═══
async function startMic() {
  try {
    micStream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true }
    });
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const src = audioContext.createMediaStreamSource(micStream);
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 512;
    analyser.smoothingTimeConstant = 0.4;
    src.connect(analyser);

    dot('status-voice', true);
    document.getElementById('btn-voice').classList.add('listening');

    // Calibrar ruido ambiente 1.5s
    let samples = [];
    const cal = setInterval(() => {
      samples.push(getLevel());
    }, 80);

    setTimeout(() => {
      clearInterval(cal);
      if (samples.length > 0) {
        noiseFloor = samples.reduce((a,b) => a+b) / samples.length;
      }
      // Threshold = ruido + 1.5 (MUY sensible)
      const th = noiseFloor + 1.5;
      msg('system', '🎤 Listo. Solo habla.');
      startVAD(th);
    }, 1500);

  } catch (e) {
    msg('system', '❌ Mic: ' + e.message);
  }
}

function getLevel() {
  const d = new Uint8Array(analyser.frequencyBinCount);
  analyser.getByteFrequencyData(d);
  let s = 0; for (let i = 0; i < d.length; i++) s += d[i];
  return s / d.length;
}

function startVAD(threshold) {
  if (vadInterval) clearInterval(vadInterval);

  vadInterval = setInterval(() => {
    if (jarvisTalking || !analyser) return;

    const level = getLevel();

    if (level > threshold) {
      // VOZ
      if (!isSpeaking) {
        isSpeaking = true;
        speechStart = Date.now();
        // Grabar
        audioChunks = [];
        try {
          mediaRecorder = new MediaRecorder(micStream, {
            mimeType: MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : 'audio/webm'
          });
          mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };
          mediaRecorder.start(200);
        } catch(e) {}
        voiceIndicator.classList.remove('hidden');
        voiceIndicator.querySelector('span').textContent = '🎤 Escuchando...';
      }
      if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }
    } else if (isSpeaking && !silenceTimer) {
      // SILENCIO tras habla
      silenceTimer = setTimeout(() => {
        silenceTimer = null;
        const dur = Date.now() - speechStart;
        if (dur > 500 && mediaRecorder && mediaRecorder.state === 'recording') {
          voiceIndicator.querySelector('span').textContent = '⏳ Procesando...';
          mediaRecorder.onstop = () => {
            const blob = new Blob(audioChunks, { type: 'audio/webm' });
            audioChunks = [];
            if (blob.size > 2000 && ws && ws.readyState === 1) {
              const r = new FileReader();
              r.onload = () => ws.send(JSON.stringify({ type: 'voice', audio: r.result.split(',')[1] }));
              r.readAsDataURL(blob);
            }
            isSpeaking = false;
            voiceIndicator.classList.add('hidden');
          };
          mediaRecorder.stop();
        } else {
          isSpeaking = false;
          voiceIndicator.classList.add('hidden');
          if (mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.onstop = () => {};
            mediaRecorder.stop();
          }
        }
      }, 1500);
    }
  }, 40);
}

// ═══ TTS ═══
function playTTS(b64, fmt) {
  jarvisTalking = true;
  // Pausar grabacion
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.onstop = () => {};
    mediaRecorder.stop();
  }
  isSpeaking = false;

  const audio = new Audio(`data:audio/${fmt};base64,${b64}`);
  audio.onended = () => { jarvisTalking = false; };
  audio.onerror = () => { jarvisTalking = false; };
  audio.play().catch(() => { jarvisTalking = false; });
}

function beep() {
  try {
    const c = new (window.AudioContext || window.webkitAudioContext)();
    const o = c.createOscillator(), g = c.createGain();
    o.connect(g); g.connect(c.destination);
    o.frequency.value = 880; g.gain.setValueAtTime(0.15, c.currentTime);
    g.gain.exponentialRampToValueAtTime(0.01, c.currentTime + 0.12);
    o.start(); o.stop(c.currentTime + 0.12);
  } catch(e) {}
}

// ═══ LOCATION ═══
function getLocation() {
  if (!('geolocation' in navigator)) return;
  navigator.geolocation.getCurrentPosition(p => {
    const {latitude: lat, longitude: lon} = p.coords;
    locationWidget.innerHTML = `📍 ${lat.toFixed(2)}, ${lon.toFixed(2)}`;
    ws?.readyState === 1 && ws.send(JSON.stringify({type:'add_fact', fact:`GPS: ${lat.toFixed(4)},${lon.toFixed(4)}`}));
    fetch(`https://geocode.maps.co/reverse?lat=${lat}&lon=${lon}`).then(r=>r.json()).then(d=>{
      const city = d.address?.city||d.address?.town||d.address?.village||'';
      const state = d.address?.state||'';
      if (city) { locationWidget.innerHTML = `📍 ${city}, ${state}`; }
    }).catch(()=>{});
  }, ()=>{}, {enableHighAccuracy:false, timeout:10000});
}

// ═══ UI ═══
function msg(type, content, streaming=false) {
  const div = document.createElement('div');
  div.className = `message ${type}`;
  if (streaming) { div.id = 'stream'; div.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>'; }
  else div.innerHTML = fmt(content);
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}
function updStream(c) { const el=document.getElementById('stream'); if(el){el.innerHTML=fmt(c); chatMessages.scrollTop=chatMessages.scrollHeight;} }
function finStream() { const el=document.getElementById('stream'); if(el) el.removeAttribute('id'); }
function fmt(t) {
  if(!t) return '';
  t=t.replace(/```(\w*)\n([\s\S]*?)```/g,(_,l,c)=>`<pre><code>${esc(c.trim())}</code></pre>`);
  t=t.replace(/`([^`]+)`/g,'<code>$1</code>');
  t=t.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>');
  return t.replace(/\n/g,'<br>');
}
function esc(t){const d=document.createElement('div');d.textContent=t;return d.innerHTML;}

function showData(r) {
  const {type,data} = r;
  let c = '';
  if (type==='weather') { c=`🌡 ${data.temp_c}°C — ${data.description}`; weatherWidget.innerHTML=`<div class="temp">${data.temp_c}°C</div><div>${data.description}</div>`; }
  else if (type==='location') { c=`📍 ${data.city}, ${data.region}`; locationWidget.innerHTML=c; }
  else if (type==='pc'||type==='spotify') { c=data.message||data.error||JSON.stringify(data); }
  else if (type==='web') { c=data.map(x=>x.title).join(', '); }
  else if (type==='projects') { c=data.projects.join(', '); renderProj(data.projects); }
  else c=JSON.stringify(data,null,2);
  msg('action-data', c);
}

function sendMsg() {
  const m=chatInput.value.trim();
  if(!m||!ws||ws.readyState!==1) return;
  msg('user',m);
  ws.send(JSON.stringify({type:'chat',message:m,from_voice:false}));
  chatInput.value='';
}

function dot(id,on){const el=document.getElementById(id);if(el){const d=el.querySelector('.dot');if(d)d.className=`dot ${on?'online':'offline'}`;}}
function renderProj(p){projectsList.innerHTML=p.map(x=>`<div class="project-item" onclick="chatInput.value='Status de ${x}';sendMsg()">${x}</div>`).join('');}
function clock(){const n=new Date();timeWidget.textContent=`${String(n.getHours()).padStart(2,'0')}:${String(n.getMinutes()).padStart(2,'0')}:${String(n.getSeconds()).padStart(2,'0')}`;}

async function loadInfo(){
  try{
    const [w,p]=await Promise.allSettled([fetch(`${API_URL}/weather`),fetch(`${API_URL}/obsidian/projects`)]);
    if(w.status==='fulfilled'&&w.value.ok){const d=await w.value.json();if(!d.error)weatherWidget.innerHTML=`<div class="temp">${d.temp_c}°C</div><div>${d.description}</div>`;}
    if(p.status==='fulfilled'&&p.value.ok){const d=await p.value.json();renderProj(d.projects||[]);}
  }catch(e){}
}

function camStream(){const iv=setInterval(()=>{if(!rightPanel.classList.contains('hidden')&&ws?.readyState===1)ws.send(JSON.stringify({type:'camera_snapshot'}));else clearInterval(iv);},100);}

// Events
document.getElementById('btn-send').addEventListener('click',sendMsg);
document.getElementById('btn-voice').addEventListener('click',()=>{
  if(micStream){micStream.getTracks().forEach(t=>t.stop());micStream=null;if(vadInterval)clearInterval(vadInterval);document.getElementById('btn-voice').classList.remove('listening');dot('status-voice',false);msg('system','Mic apagado');}
  else startMic();
});
document.getElementById('btn-camera').addEventListener('click',()=>{
  if(rightPanel.classList.contains('hidden'))ws?.readyState===1&&ws.send(JSON.stringify({type:'camera_start'}));
  else{rightPanel.classList.add('hidden');ws?.readyState===1&&ws.send(JSON.stringify({type:'camera_stop'}));}
});
chatInput.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMsg();}});
document.getElementById('btn-close-panel')?.addEventListener('click',()=>{rightPanel.classList.add('hidden');ws?.readyState===1&&ws.send(JSON.stringify({type:'camera_stop'}));});
document.getElementById('btn-analyze')?.addEventListener('click',()=>{chatInput.value='Que ves?';sendMsg();});

setInterval(clock,1000);clock();connect();
