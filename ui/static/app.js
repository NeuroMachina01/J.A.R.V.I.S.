// ═══════════════════════════════════════════════════════════
//  J.A.R.V.I.S. MARK VII — GOOSEBUMP EDITION
//  Particle field, orbital physics, arc-reactor core FX
// ═══════════════════════════════════════════════════════════

// ── PARTICLE FIELD CANVAS ──────────────────────────────────

const canvas = document.getElementById('neural-canvas');
const ctx = canvas.getContext('2d');
let W = canvas.width = window.innerWidth;
let H = canvas.height = window.innerHeight;

window.addEventListener('resize', () => {
    W = canvas.width = window.innerWidth;
    H = canvas.height = window.innerHeight;
    initParticles();
});

let mouse = { x: W / 2, y: H / 2 };
window.addEventListener('mousemove', e => { mouse.x = e.clientX; mouse.y = e.clientY; });

const PARTICLE_COUNT = 200;
let particles = [];

class Particle {
    constructor() { this.reset(); }
    reset() {
        this.x  = Math.random() * W;
        this.y  = Math.random() * H;
        this.bx = this.x;
        this.by = this.y;
        this.vx = (Math.random() - 0.5) * 0.8;
        this.vy = (Math.random() - 0.5) * 0.8;
        this.r  = Math.random() * 1.2 + 0.3;
        this.a  = Math.random() * 0.3 + 0.1;
    }
    update() {
        this.x += this.vx;
        this.y += this.vy;

        // Spring back to base
        this.vx += (this.bx - this.x) * 0.0008;
        this.vy += (this.by - this.y) * 0.0008;

        // Friction
        this.vx *= 0.995;
        this.vy *= 0.995;

        // Mouse repulsion
        const dx = mouse.x - this.x;
        const dy = mouse.y - this.y;
        const d  = Math.sqrt(dx * dx + dy * dy);
        if (d < 180) {
            const f = (180 - d) / 180 * 0.4;
            this.vx -= (dx / d) * f;
            this.vy -= (dy / d) * f;
        }

        // Speaking jitter
        if (_speaking) {
            this.vx += (Math.random() - 0.5) * 1.5;
            this.vy += (Math.random() - 0.5) * 1.5;
        }
    }
}

function initParticles() {
    particles = [];
    for (let i = 0; i < PARTICLE_COUNT; i++) particles.push(new Particle());
}
initParticles();

let _speaking = false;

function renderFrame() {
    ctx.clearRect(0, 0, W, H);

    for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        p.update();

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        const col = _speaking ? `rgba(0, 255, 200, ${p.a * 2})` : `rgba(0, 229, 255, ${p.a})`;
        ctx.fillStyle = col;
        ctx.fill();

        // Connect nearby particles
        for (let j = i + 1; j < particles.length; j++) {
            const q = particles[j];
            const dx = p.x - q.x;
            const dy = p.y - q.y;
            const dist = dx * dx + dy * dy;
            const maxD = _speaking ? 22000 : 14000;
            if (dist < maxD) {
                const alpha = (1 - dist / maxD) * (_speaking ? 0.25 : 0.1);
                ctx.beginPath();
                ctx.moveTo(p.x, p.y);
                ctx.lineTo(q.x, q.y);
                ctx.strokeStyle = _speaking
                    ? `rgba(0, 255, 200, ${alpha})`
                    : `rgba(0, 229, 255, ${alpha})`;
                ctx.lineWidth = 0.4;
                ctx.stroke();
            }
        }
    }

    requestAnimationFrame(renderFrame);
}
renderFrame();


// ── DATA STREAM (hex matrix) ───────────────────────────────

const dataStreamEl = document.getElementById("data-stream");
function hexStream() {
    if (!dataStreamEl) return;
    let s = "";
    for (let i = 0; i < 18; i++) {
        s += Math.floor(Math.random() * 16777215).toString(16).toUpperCase().padStart(6, '0') + " ";
        if ((i + 1) % 3 === 0) s += "<br>";
    }
    dataStreamEl.innerHTML = s;
}
setInterval(hexStream, 100);


// ── WEBSOCKET WITH AUTO-RECONNECT ──────────────────────────

const messageEl   = document.getElementById("agent-messages");
const imgCont     = document.getElementById("image-container");
const imgEl       = document.getElementById("hud-image");
const coreDot     = document.querySelector(".core-dot");
const coreRings   = document.querySelectorAll(".core-ring");
const agentStatus = document.getElementById("agent-status");
const coreStatus  = document.getElementById("core-status");
const uplinkStatus = document.getElementById("uplink-status");

let speakInterval, speakTimeout;
let ws;
let reconnectTimer;

function connectWebSocket() {
    ws = new WebSocket("ws://localhost:8000/ws");

    ws.onopen = function() {
        console.log("[JARVIS] WebSocket connected.");
        document.body.classList.remove("disconnected");
        coreStatus.innerHTML  = '<span class="dot green"></span> CORE: ONLINE';
        uplinkStatus.innerHTML = '<span class="dot green"></span> UPLINK: SECURE';
        clearInterval(reconnectTimer);
    };

    ws.onclose = function() {
        console.log("[JARVIS] WebSocket disconnected. Reconnecting...");
        document.body.classList.add("disconnected");
        coreStatus.innerHTML  = '<span class="dot red"></span> CORE: OFFLINE';
        uplinkStatus.innerHTML = '<span class="dot red"></span> UPLINK: LOST';
        agentStatus.innerHTML = '<span class="dot red"></span> RECONNECTING...';
        // Retry every 3 seconds
        reconnectTimer = setInterval(() => {
            try { connectWebSocket(); } catch(e) {}
        }, 3000);
    };

    ws.onerror = function() {
        ws.close();
    };

    ws.onmessage = handleMessage;
}

connectWebSocket();


// ── CINEMATIC TITLE CARD ───────────────────────────────────

const titleCard     = document.getElementById("title-card");
const titleCardText = document.getElementById("title-card-text");

function flashTitleCard(agentName) {
    // Format the agent name for display
    const displayName = agentName.replace(/_/g, " ").toUpperCase();
    titleCardText.textContent = displayName;

    // Reset animation by cloning
    const newText = titleCardText.cloneNode(true);
    titleCardText.parentNode.replaceChild(newText, titleCardText);

    // Store the new reference (old one was replaced)
    const liveText = document.getElementById("title-card-text");

    titleCard.classList.remove("hidden");

    // Auto-hide after the animation completes (1.8s)
    setTimeout(() => {
        titleCard.classList.add("hidden");
    }, 1800);
}


// ── UPTIME COUNTER ─────────────────────────────────────────

const uptimeEl = document.getElementById("uptime-counter");
const sessionStart = Date.now();

function updateUptime() {
    const elapsed = Math.floor((Date.now() - sessionStart) / 1000);
    const h = String(Math.floor(elapsed / 3600)).padStart(2, '0');
    const m = String(Math.floor((elapsed % 3600) / 60)).padStart(2, '0');
    const s = String(elapsed % 60).padStart(2, '0');
    uptimeEl.textContent = `${h}:${m}:${s}`;
}
setInterval(updateUptime, 1000);


// ── SPEAKING SIMULATION ────────────────────────────────────

function startSpeaking(textLen) {
    _speaking = true;
    document.body.classList.add("speaking");
    clearInterval(speakInterval);
    clearTimeout(speakTimeout);

    speakInterval = setInterval(() => {
        const scale = 1 + Math.random() * 6;
        const glow  = 20 + Math.random() * 50;
        const bloom = 5 + Math.random() * 20;
        coreDot.style.transform  = `scale(${scale})`;
        coreDot.style.boxShadow  = `0 0 ${glow}px ${bloom}px #00e5ff, 0 0 ${glow * 2}px ${bloom}px rgba(0,255,200,0.15)`;
    }, 40);

    speakTimeout = setTimeout(stopSpeaking, textLen * 65);
}

function stopSpeaking() {
    _speaking = false;
    document.body.classList.remove("speaking");
    clearInterval(speakInterval);
    coreDot.style.transform = "scale(1)";
    coreDot.style.boxShadow = "0 0 12px 4px #00e5ff, 0 0 40px 8px rgba(0,229,255,0.3), 0 0 80px 20px rgba(0,229,255,0.1)";
}


// ── LOGS MODAL ─────────────────────────────────────────────

const logsBtn      = document.getElementById("logs-btn");
const logsModal    = document.getElementById("logs-modal");
const logsOverlay  = document.getElementById("logs-overlay");
const closeLogsBtn = document.getElementById("close-logs");
const logsContent  = document.getElementById("logs-content");

function openLogs()  { logsModal.classList.remove("hidden"); logsOverlay.classList.remove("hidden"); }
function closeLogs() { logsModal.classList.add("hidden");    logsOverlay.classList.add("hidden"); }

logsBtn.addEventListener("click", openLogs);
closeLogsBtn.addEventListener("click", closeLogs);
logsOverlay.addEventListener("click", closeLogs);


// ── CHAT INPUT WITH QUERY HISTORY ──────────────────────────

const chatInput = document.getElementById("chat-input");
let queryHistory = [];
let historyIndex = -1;

chatInput.addEventListener("keydown", function(e) {
    if (e.key === "Enter" && chatInput.value.trim()) {
        const query = chatInput.value.trim();
        queryHistory.push(query);
        historyIndex = queryHistory.length; // reset to end
        ws.send(JSON.stringify({ query: query }));
        chatInput.value = "";
    }
    else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (queryHistory.length > 0 && historyIndex > 0) {
            historyIndex--;
            chatInput.value = queryHistory[historyIndex];
        }
    }
    else if (e.key === "ArrowDown") {
        e.preventDefault();
        if (historyIndex < queryHistory.length - 1) {
            historyIndex++;
            chatInput.value = queryHistory[historyIndex];
        } else {
            historyIndex = queryHistory.length;
            chatInput.value = "";
        }
    }
});


// ── WEBSOCKET MESSAGE HANDLER ──────────────────────────────

function handleMessage(event) {
    const data = JSON.parse(event.data);

    // ── Log messages → observability console
    if (data.type === "log") {
        const line = document.createElement("div");
        line.className = "log-line";
        line.textContent = data.message;
        logsContent.appendChild(line);
        logsContent.scrollTop = logsContent.scrollHeight;
        return;
    }

    // ── Clear event (new query starting)
    if (data.type === "clear") {
        messageEl.style.filter  = "blur(12px)";
        messageEl.style.opacity = "0";
        imgCont.style.opacity   = "0";
        setTimeout(() => {
            imgCont.style.width  = "0px";
            imgCont.style.height = "0px";
            imgEl.src = "";
        }, 500);
        agentStatus.innerHTML = '<span class="dot cyan"></span> AGENT: PROCESSING';
        return;
    }

    // ── Text responses & status messages
    if (data.type === "result" || data.type === "status") {
        const text = data.text || data.message || "";

        // Update agent status indicator
        if (data.type === "status") {
            agentStatus.innerHTML = `<span class="dot cyan"></span> ${text}`;

            // Flash the cinematic title card when routing to an agent
            if (text.includes("ROUTING TO:")) {
                const agentName = text.replace("ROUTING TO:", "").trim();
                flashTitleCard(agentName);
            }
        }
        if (data.agent) {
            agentStatus.innerHTML = `<span class="dot green"></span> AGENT: ${data.agent.toUpperCase()}`;
        }

        // Cinematic blur-in for subtitle text
        messageEl.style.filter  = "blur(12px)";
        messageEl.style.opacity = "0";
        setTimeout(() => {
            messageEl.innerHTML     = `<span class="subtitle-text">${text}</span>`;
            messageEl.style.filter  = "blur(0px)";
            messageEl.style.opacity = "1";
        }, 350);

        if (data.type === "result") {
            startSpeaking(text.length);
        } else {
            coreDot.style.transform = "scale(2.5)";
            setTimeout(stopSpeaking, 400);
        }
    }

    // ── Image display
    else if (data.type === "image") {
        imgCont.style.width   = "480px";
        imgCont.style.height  = "320px";
        imgCont.style.opacity = "0";
        setTimeout(() => {
            imgEl.src = "data:image/png;base64," + data.content;
            imgCont.style.opacity = "1";
        }, 500);
    }
}