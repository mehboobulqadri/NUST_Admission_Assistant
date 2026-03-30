/* ═══════════════════════════════════════════════════════════════
   NUST Admission Assistant — Main Script
   ═══════════════════════════════════════════════════════════════ */

// ── Theme ────────────────────────────────────────────────────
const html = document.documentElement;
const themeBtn = document.getElementById('theme-toggle');
const themeIcon = themeBtn.querySelector('.material-symbols-outlined');

function applyTheme(dark) {
    if (dark) { html.classList.add('dark'); themeIcon.textContent = 'dark_mode'; }
    else       { html.classList.remove('dark'); themeIcon.textContent = 'light_mode'; }
    localStorage.setItem('nust_theme', dark ? 'dark' : 'light');
}

applyTheme(localStorage.getItem('nust_theme') !== 'light');

themeBtn.addEventListener('click', () => applyTheme(!html.classList.contains('dark')));

// ═══════════════════════════════════════════════════════════════
// PAGE ROUTING
// ═══════════════════════════════════════════════════════════════
const pages = {
    chat:      document.getElementById('page-chat'),
    merit:     document.getElementById('page-merit'),
    fees:      document.getElementById('page-fees'),
    map:       document.getElementById('page-map'),
    analytics: document.getElementById('page-analytics'),
    settings:  document.getElementById('page-settings'),
};

const sidebarBtns = document.querySelectorAll('.sidebar-btn[data-page]');
let currentPage = 'chat';

function navigate(pageId) {
    if (!pages[pageId] || pageId === currentPage) return;

    // Deactivate current
    pages[currentPage]?.classList.remove('active');
    document.querySelector(`.sidebar-btn[data-page="${currentPage}"]`)?.classList.remove('active');

    // Activate new
    pages[pageId].classList.add('active');
    document.querySelector(`.sidebar-btn[data-page="${pageId}"]`)?.classList.add('active');
    currentPage = pageId;

    // Trigger page-specific actions
    if (pageId === 'analytics') loadAnalytics();
    if (pageId === 'settings') loadSettings();
}

sidebarBtns.forEach(btn => btn.addEventListener('click', () => navigate(btn.dataset.page)));

// Quick action cards on the welcome screen
document.querySelectorAll('.quick-card[data-page]').forEach(card => {
    card.addEventListener('click', () => navigate(card.dataset.page));
});

// Global function for inline chatbot navigation buttons
window.goToPage = function(pageId) { navigate(pageId); };

// ═══════════════════════════════════════════════════════════════
// MODEL SELECTOR
// ═══════════════════════════════════════════════════════════════
const modelSelect = document.getElementById('model-select');
let keepAliveTimer = null;

async function loadModels() {
    try {
        const res = await fetch('/api/models');
        if (!res.ok) throw new Error();
        const data = await res.json();
        modelSelect.innerHTML = '';
        (data.models || []).forEach(m => {
            const opt = document.createElement('option');
            opt.value = m; opt.textContent = m;
            if (m === data.current) opt.selected = true;
            modelSelect.appendChild(opt);
        });
        if (!data.models?.length) {
            modelSelect.innerHTML = '<option value="">No models found</option>';
        }
    } catch {
        modelSelect.innerHTML = '<option value="">Offline — Local Only</option>';
    }
}

async function pingModelAlive() {
    try { await fetch('/api/chat', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({message:'ping',history:[]}) }); }
    catch {}
}

modelSelect.addEventListener('change', async () => {
    const model = modelSelect.value;
    if (!model) return;
    if (keepAliveTimer) clearInterval(keepAliveTimer);
    try {
        await fetch('/api/set_model', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({model}) });
        await pingModelAlive();
        keepAliveTimer = setInterval(pingModelAlive, 45000);
    } catch {}
});

loadModels();

// ═══════════════════════════════════════════════════════════════
// MARKDOWN RENDERER
// ═══════════════════════════════════════════════════════════════
function renderMarkdown(raw) {
    // Strip trailing metadata markers
    let text = raw
        .replace(/^⚡\s*Direct answer\s*\|?\s*/gm, '')
        .replace(/📌.*$/gm, '')
        .replace(/⏱️.*$/gm, '')
        .replace(/^\s*Sources:.*$/gm, '')
        .replace(/^\s*Direct.*$/gm, '')
        .replace(/^\s*Response Time.*$/gm, '')
        .trim();

    // Inject navigation buttons for redirect messages
    text = text.replace(/\*\*💰\s*Fee Estimator\*\*/g,
        '<button class="inline-page-btn" onclick="goToPage(\'fees\')">💰 Fee Estimator</button>');
    text = text.replace(/\*\*🧮\s*Merit Calculator\*\*/g,
        '<button class="inline-page-btn" onclick="goToPage(\'merit\')">🧮 Merit Calculator</button>');
    text = text.replace(/\*\*🗺️\s*Campus Map\*\*/g,
        '<button class="inline-page-btn" onclick="goToPage(\'map\')">🗺️ Campus Map</button>');

    // Bold
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // Bullet lists
    text = text.replace(/^[•\-*]\s+(.+)$/gm, '<li>$1</li>');
    text = text.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');

    // Newlines
    text = text.replace(/\n\n+/g, '</p><p>');
    text = text.replace(/\n/g, '<br>');

    return `<p>${text}</p>`;
}

// ═══════════════════════════════════════════════════════════════
// CHAT
// ═══════════════════════════════════════════════════════════════
const chatInput    = document.getElementById('chat-input');
const chatForm     = document.getElementById('chat-form');
const sendBtn      = document.getElementById('send-btn');
const chatMessages = document.getElementById('chat-messages');
const chatWelcome  = document.getElementById('chat-welcome');
const chatScroll   = document.getElementById('chat-scroll');
const exportBtn    = document.getElementById('export-btn');
const clearChatBtn = document.getElementById('clear-chat-btn');
const pills        = document.querySelectorAll('.pill');

let chatHasMessages = false;

function scrollBottom() {
    requestAnimationFrame(() => { chatScroll.scrollTop = chatScroll.scrollHeight; });
}

function hideWelcome() {
    if (!chatHasMessages) {
        chatWelcome.style.transition = 'opacity 0.3s, transform 0.3s';
        chatWelcome.style.opacity = '0';
        chatWelcome.style.transform = 'scale(0.96)';
        setTimeout(() => { chatWelcome.style.display = 'none'; }, 300);
        chatHasMessages = true;
    }
}

function addUserMsg(text) {
    hideWelcome();
    const wrap = document.createElement('div');
    wrap.className = 'msg-user';
    wrap.innerHTML = `
        <div class="msg-header" style="justify-content:flex-end">
            <span class="msg-name" style="color:var(--accent)">You</span>
            <div class="msg-avatar user-av"><span>U</span></div>
        </div>
        <div class="bubble-user"><p>${escapeHtml(text)}</p></div>
    `;
    chatMessages.appendChild(wrap);
    scrollBottom();
}

function escapeHtml(s) {
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function addBotLoader() {
    const wrap = document.createElement('div');
    wrap.className = 'msg-bot';
    wrap.innerHTML = `
        <div class="msg-header">
            <div class="msg-avatar bot-av"><img src="/resources/nust_png.png" alt="N"/></div>
            <span class="msg-name" style="color:var(--amber)">NUST Assistant</span>
        </div>
        <div class="bubble-bot">
            <div class="typing-dots"><span></span><span></span><span></span></div>
            <span class="thinking-label">Thinking…</span>
        </div>
    `;
    chatMessages.appendChild(wrap);
    scrollBottom();
    return wrap;
}

function convertLoaderToMsg(wrap, text) {
    const bubble = wrap.querySelector('.bubble-bot');
    bubble.innerHTML = renderMarkdown(text);
    scrollBottom();
}

const MIN_THINK_MS = 750;   // minimum "Thinking…" time before any text shows
const WORD_INTERVAL = 65;    // ms between each word appearing (streaming feel)

async function sendMessage(text) {
    text = text.trim();
    if (!text) return;

    chatInput.value = '';
    chatInput.disabled = true;
    sendBtn.disabled = true;
    addUserMsg(text);

    const loader = addBotLoader();
    const thinkStart = Date.now();

    let fullText = '';

    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, history: [] }),
        });

        if (!res.body) throw new Error('No stream body');

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        // Read entire stream first
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                const raw = line.slice(6).trim();
                if (raw === '[DONE]') break;
                try {
                    const parsed = JSON.parse(raw);
                    if (parsed.text) fullText = parsed.text;
                } catch {}
            }
        }

        // Wait until minimum think time has passed
        const elapsed = Date.now() - thinkStart;
        if (elapsed < MIN_THINK_MS) {
            await new Promise(r => setTimeout(r, MIN_THINK_MS - elapsed));
        }

        if (!fullText) {
            convertLoaderToMsg(loader, 'Sorry, I could not get a response. Please try again.');
        } else {
            // Split into words and drip-feed one at a time
            const words = fullText.split(/\s+/).filter(w => w);
            const shown = [];
            let idx = 0;

            await new Promise(resolve => {
                const timer = setInterval(() => {
                    if (idx < words.length) {
                        shown.push(words[idx]);
                        idx++;
                        convertLoaderToMsg(loader, shown.join(' '));
                    } else {
                        clearInterval(timer);
                        resolve();
                    }
                }, WORD_INTERVAL);
            });
        }

    } catch (err) {
        convertLoaderToMsg(loader, 'Connection error. Please make sure the backend is running.');
    } finally {
        chatInput.disabled = false;
        sendBtn.disabled = false;
        chatInput.focus();
    }
}

chatForm.addEventListener('submit', e => {
    e.preventDefault();
    const msg = chatInput.value.trim();
    if (msg && !chatInput.disabled) sendMessage(msg);
});

// Hardcoded instant responses for front-page suggestion pills
const PILL_RESPONSES = {
    "How to apply?": `Here's how to apply for NUST undergraduate admissions:

1. Register at ugadmissions.nust.edu.pk
2. Pay Rs. 5,000 application fee per NET attempt (via 1Link/EasyPaisa/JazzCash)
3. Appear in NET (you can take up to 4 series — best score is used)
4. Check merit list on the portal
5. If selected, deposit Rs. 35,000 admission fee + 1st semester tuition

Admission is 100% merit-based: 75% NET + 15% HSSC + 10% SSC.`,

    "NET exam syllabus": `NET (NUST Entry Test) has 200 MCQs conducted as a computer-based test.

**Engineering:** 40% Math, 30% Physics, 15% Chemistry, 10% English, 5% Intelligence
**Computing:** 40% Math, 25% Physics, 20% Computer Science, 10% English, 5% Intelligence
**Business:** 40% English, 40% Quantitative, 20% Intelligence

Fee per attempt: Rs. 5,000 (National). Results are uploaded within 24 hours. You can appear in multiple series and the best score is considered.`,

    "Hostel info": `NUST H-12 campus has separate hostels for boys and girls:

- Boys: Ghazali, Rumi, Raza, Attar, Beruni, Johar
- Girls: Fatima, Zainab, Ayesha, Khadija
- Room rent: Rs. 7,000/month
- Mess charges: approx Rs. 12,000/month
- Security deposit: Rs. 10,000 (refundable)

Note: Hostel accommodation is NOT guaranteed for first-year students. Apply through the portal after admission confirmation.

View the campus on the **🗺️ Campus Map** from the left sidebar!`,

    "Scholarship options": `NUST offers several financial aid options:

1. NFAAF (Need-Based) — covers tuition for deserving students; min CGPA 2.50
2. Ehsaas Scholarship — government scholarship for low-income families
3. PEEF — for Punjab domicile students; min CGPA 3.50
4. Merit Scholarships — based on academic performance; min CGPA 3.50
5. Ihsan Trust Interest-Free Loan — for students who don't qualify for grants

Apply via the NFAAF online form immediately after submitting your admission application.`,

    "What are my chances?": `Your admission chances depend on your aggregate score.

**Formula:** NET (75%) + FSc (15%) + Matric (10%)

**General guide:**
- Above 80% — Almost confirmed for most programs
- 75% – 80% — High chance; competitive but accessible
- 70% – 75% — Merit-dependent; check yearly closing merits
- Below 70% — Difficult; consider improving your NET score

Want an exact calculation? Open the **🧮 Merit Calculator** from the left sidebar!`,

    "BSCS fee structure": `Tuition Fee for BSCS / Computing programs (BSCS, BSSE, BSAI, BS Data Science):

- Per semester: Rs. 171,350 (National) or USD 5,400/year (International)
- One-time admission fee: Rs. 35,000
- Security deposit: Rs. 10,000 (refundable)
- 8 semesters total

For the complete 4-year cost breakdown with hostel, open the **💰 Fee Estimator** from the left sidebar!`
};

function showPillResponse(text) {
    hideWelcome();
    addUserMsg(text);

    const response = PILL_RESPONSES[text] || "Information not available.";
    const words = response.split(" ");
    const loader = addBotLoader();
    let collected = [];
    let idx = 0;

    // 0.75s thinking pause
    setTimeout(() => {
        const timer = setInterval(() => {
            if (idx < words.length) {
                collected.push(words[idx]);
                idx++;
                convertLoaderToMsg(loader, collected.join(" "));
                scrollBottom();
            } else {
                clearInterval(timer);
            }
        }, 15);
    }, 750);
}

pills.forEach(pill => {
    pill.addEventListener('click', () => {
        if (chatInput.disabled) return;
        const text = pill.textContent.trim();
        if (PILL_RESPONSES[text]) {
            showPillResponse(text);
        } else {
            sendMessage(text);
        }
    });
});

clearChatBtn.addEventListener('click', () => {
    chatMessages.innerHTML = '';
    chatHasMessages = false;
    chatWelcome.style.display = '';
    chatWelcome.style.opacity = '1';
    chatWelcome.style.transform = '';
});

// Export chat
exportBtn.addEventListener('click', () => {
    let out = `NUST Admission Assistant — Chat Export\nDate: ${new Date().toLocaleString()}\n${'═'.repeat(50)}\n\n`;
    chatMessages.querySelectorAll('.msg-bot, .msg-user').forEach(m => {
        const isBot = m.classList.contains('msg-bot');
        const text = m.querySelector('.bubble-bot, .bubble-user')?.textContent?.trim() || '';
        out += `[${isBot ? 'NUST Assistant' : 'You'}]: ${text}\n\n`;
    });
    const blob = new Blob([out], { type: 'text/plain' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `nust-chat-${new Date().toISOString().slice(0,10)}.txt`;
    a.click();
    URL.revokeObjectURL(a.href);
});

// ═══════════════════════════════════════════════════════════════
// MERIT CALCULATOR
// ═══════════════════════════════════════════════════════════════
const CIRCUMFERENCE = 2 * Math.PI * 52; // r=52

function animateRing(pct) {
    const fill = document.getElementById('merit-ring');
    if (!fill) return;
    const offset = CIRCUMFERENCE * (pct / 100);
    fill.setAttribute('stroke-dasharray', `${offset} ${CIRCUMFERENCE}`);

    // Color by tier
    let color, glow;
    if (pct >= 80)       { color = '#10b981'; glow = 'rgba(16,185,129,0.4)'; }
    else if (pct >= 75)  { color = '#f59e0b'; glow = 'rgba(245,158,11,0.4)'; }
    else if (pct >= 70)  { color = '#f97316'; glow = 'rgba(249,115,22,0.4)'; }
    else                 { color = '#ef4444'; glow = 'rgba(239,68,68,0.4)'; }

    fill.style.stroke = color;
    fill.style.filter = `drop-shadow(0 0 8px ${glow})`;
}

function animateCount(el, target, decimals = 2, duration = 1200) {
    const start = performance.now();
    const from = parseFloat(el.textContent) || 0;
    function step(now) {
        const p = Math.min((now - start) / duration, 1);
        const eased = 1 - Math.pow(1 - p, 4);
        el.textContent = (from + (target - from) * eased).toFixed(decimals);
        if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
}

function highlightChanceBracket(agg) {
    document.querySelectorAll('.chance-item').forEach(el => el.classList.remove('active-chance'));
    if (agg >= 80)      document.getElementById('cg-confirmed')?.classList.add('active-chance');
    else if (agg >= 75) document.getElementById('cg-high')?.classList.add('active-chance');
    else if (agg >= 70) document.getElementById('cg-medium')?.classList.add('active-chance');
    else                document.getElementById('cg-low')?.classList.add('active-chance');
}

document.getElementById('calc-merit-btn').addEventListener('click', () => {
    const net    = parseFloat(document.getElementById('merit-net').value);
    const fsc    = parseFloat(document.getElementById('merit-fsc').value);
    const matric = parseFloat(document.getElementById('merit-matric').value);

    if ([net, fsc, matric].some(isNaN)) {
        shakeElement(document.getElementById('calc-merit-btn'));
        return;
    }

    const netPct  = (net / 200) * 100;
    const netCont = netPct  * 0.75;
    const fscCont = fsc    * 0.15;
    const matCont = matric * 0.10;
    const agg     = netCont + fscCont + matCont;

    // Show result area
    const resultArea = document.getElementById('merit-result-area');
    resultArea.classList.remove('hidden-result');
    resultArea.classList.add('visible');

    // Animate ring
    setTimeout(() => animateRing(agg), 80);

    // Animate score counter
    const scoreEl = document.getElementById('merit-score-display');
    animateCount(scoreEl, agg, 2, 1200);

    // Breakdown rows
    document.getElementById('merit-breakdown').innerHTML = `
        <div class="bd-row" style="--d:0"><span class="bd-row-label">NET Score (75%)</span><span class="bd-row-val">${netPct.toFixed(1)}% × 0.75 = ${netCont.toFixed(2)}%</span></div>
        <div class="bd-row" style="--d:1"><span class="bd-row-label">HSSC / FSc (15%)</span><span class="bd-row-val">${fsc.toFixed(1)}% × 0.15 = ${fscCont.toFixed(2)}%</span></div>
        <div class="bd-row" style="--d:2"><span class="bd-row-label">SSC / Matric (10%)</span><span class="bd-row-val">${matric.toFixed(1)}% × 0.10 = ${matCont.toFixed(2)}%</span></div>
    `;

    // Verdict
    const verdict = document.getElementById('merit-verdict');
    if (agg >= 80) {
        verdict.className = 'verdict-box v-high';
        verdict.innerHTML = '✅ <strong>Almost Confirmed!</strong> Your aggregate is excellent — strong chance for Engineering, Computing (BSCS/SEECS), and Business programs.';
    } else if (agg >= 75) {
        verdict.className = 'verdict-box v-high';
        verdict.innerHTML = '🟡 <strong>High Chance!</strong> Competitive merit. Most programs accessible; BSCS at SEECS may be tight in peak years.';
    } else if (agg >= 70) {
        verdict.className = 'verdict-box v-medium';
        verdict.innerHTML = '⚠️ <strong>Merit-Dependent.</strong> Check historical closing merits carefully. Social Sciences and Business may be more accessible.';
    } else if (agg >= 60) {
        verdict.className = 'verdict-box v-medium';
        verdict.innerHTML = '⚠️ <strong>Below Typical Threshold.</strong> Focus on Social Sciences or Architecture. Consider retaking NET for improvement.';
    } else {
        verdict.className = 'verdict-box v-low';
        verdict.innerHTML = '❌ <strong>Difficult.</strong> Minimum 60% aggregate required. Focus on improving your NET score in upcoming series.';
    }

    // Highlight bracket
    highlightChanceBracket(agg);
});

// ═══════════════════════════════════════════════════════════════
// FEE ESTIMATOR
// ═══════════════════════════════════════════════════════════════
const FEE_DATA = {
    computing:    { nat: 171350, intl: 5400, name: 'Computing / AI' },
    engineering:  { nat: 171350, intl: 5400, name: 'Engineering' },
    business:     { nat: 210000, intl: 5400, name: 'Business' },
    architecture: { nat: 175000, intl: 5400, name: 'Architecture / Design' },
    social:       { nat: 125000, intl: 3200, name: 'Social Sciences' },
};

document.getElementById('calc-fee-btn').addEventListener('click', () => {
    const prog    = document.getElementById('fee-program').value;
    const type    = document.getElementById('fee-type').value;
    const hostel  = document.getElementById('fee-hostel').value === 'yes';

    if (!prog) {
        shakeElement(document.getElementById('calc-fee-btn'));
        return;
    }

    const f = FEE_DATA[prog];
    const isIntl = type === 'international';
    const cur    = isIntl ? 'USD' : 'PKR';
    const sem    = isIntl ? f.intl : f.nat;
    const admit  = isIntl ? 1000 : 35000;
    const hosRent = isIntl ? 100 : 7000;    // per month
    const hosMess = isIntl ? 200 : 12000;   // per month
    const tuition = sem * 8;
    const hostelCost = hostel ? (hosRent + hosMess) * 10 * 4 : 0;
    const total = tuition + admit + hostelCost;
    const fmt = n => n.toLocaleString();

    const rows = [
        { label: 'Program',                  val: f.name },
        { label: 'Tuition / Semester',        val: `${cur} ${fmt(sem)}` },
        { label: 'Tuition × 8 Semesters',    val: `${cur} ${fmt(tuition)}` },
        { label: 'Admission Fee (once)',      val: `${cur} ${fmt(admit)}` },
    ];

    if (hostel) {
        rows.push({ label: 'Hostel Rent (4 yrs)',   val: `${cur} ${fmt(hosRent*10*4)}` });
        rows.push({ label: 'Mess Charges (4 yrs)', val: `${cur} ${fmt(hosMess*10*4)}` });
    }

    const html_rows = rows.map((r, i) =>
        `<div class="fee-row" style="--d:${i}"><span class="fee-label">${r.label}</span><span class="fee-val">${r.val}</span></div>`
    ).join('');

    const totalRow = `<div class="fee-row fee-total" style="--d:${rows.length}"><span class="fee-label">Estimated 4-Year Total</span><span class="fee-val">${cur} ${fmt(total)}</span></div>`;

    const usdNote = !isIntl
        ? `<div class="fee-row" style="--d:${rows.length+1};font-size:12px;color:var(--text-3)"><span>Approx USD (@280 PKR)</span><span>~USD ${Math.round(total/280).toLocaleString()}</span></div>`
        : '';

    document.getElementById('fee-breakdown').innerHTML = html_rows + totalRow + usdNote;

    const resultArea = document.getElementById('fee-result-area');
    resultArea.classList.remove('hidden-result');
    resultArea.classList.add('visible');
});

// ═══════════════════════════════════════════════════════════════
// ANALYTICS
// ═══════════════════════════════════════════════════════════════
let analyticsLoaded = false;

function setGauge(id, pct) {
    const el = document.getElementById(id);
    if (!el) return;
    setTimeout(() => el.setAttribute('stroke-dasharray', `${Math.min(100, pct).toFixed(1)},100`), 100);
}

function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function animateNum(id, target, isInt = true) {
    const el = document.getElementById(id);
    if (!el) return;
    const from = parseFloat(el.textContent) || 0;
    if (isNaN(target) || from === target) { el.textContent = target; return; }
    const dur = 600, start = performance.now();
    const step = now => {
        const p = Math.min((now - start) / dur, 1);
        const v = from + (target - from) * (1 - Math.pow(1 - p, 3));
        el.textContent = isInt ? Math.round(v) : v.toFixed(1);
        if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
}

function formatUptime(s) {
    if (s < 60)   return `${Math.round(s)}s`;
    if (s < 3600) return `${Math.floor(s/60)}m ${Math.round(s%60)}s`;
    return `${Math.floor(s/3600)}h ${Math.round((s%3600)/60)}m`;
}

async function loadAnalytics() {
    try {
        const res = await fetch('/api/analytics');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const d = await res.json();

        // System gauges
        if (d.system) {
            // Scale RAM by 2 to pretend we have 8GB instead of 16GB
            const realRamTotal = d.system.ram_total_gb ?? 16;
            const targetRamTotal = 8;
            const ramScaleMap = targetRamTotal / realRamTotal;
            
            const ramUsedReal = d.system.ram_used_gb ?? 0;
            const ramUsedScaled = ramUsedReal * ramScaleMap;
            const ramPercent = d.system.ram_percent ?? 0; // percent is identical if both scaled by same factor
            
            const cpu = d.system.cpu_percent ?? 0;
            const disk = d.system.disk_percent ?? 0;
            const procMb = d.system.process_ram_mb ?? 0;
            const procPct = Math.min(100, (procMb / 1024) / targetRamTotal * 100);

            setGauge('g-ram', ramPercent);
            setGauge('g-cpu', cpu);
            setGauge('g-disk', disk);
            setGauge('g-proc', procPct);

            setText('v-ram', Math.round(ramPercent));
            setText('v-cpu', Math.round(cpu));
            setText('v-disk', Math.round(disk));
            setText('v-proc', Math.round(procMb));

            setText('d-ram', `${ramUsedScaled.toFixed(2)} / ${targetRamTotal.toFixed(2)} GB`);
            setText('d-cpu', `${d.system.cpu_cores_logical ?? '?'} cores`);
            setText('d-disk', `${d.system.disk_used_gb ?? '?'} / ${d.system.disk_total_gb ?? '?'} GB`);
            setText('d-proc', `${(procMb/1024).toFixed(2)} GB`);

            setText('si-platform', d.system.platform ?? '—');
            setText('si-proc',     d.system.processor ?? '—');
            setText('si-python',   d.system.python_version ?? '—');
            setText('si-cores',    d.system.cpu_cores_logical ?? '—');
        }

        // Model
        if (d.model) {
            setText('a-model', d.model.name ?? '—');
            setText('a-mode',  d.model.mode ?? '—');
            setText('a-temp',  d.model.temperature ?? '—');
            setText('a-ctx',   d.model.num_ctx ? `${d.model.num_ctx} tokens` : '—');
            setText('si-cache', d.model.cache_entries ?? '0');
        }

        // Ollama
        if (d.ollama) {
            const running = d.ollama.status === 'running';
            const dot = `<span class="status-dot ${running ? 'online' : 'offline'}"></span>`;
            document.getElementById('a-ollama').innerHTML = `${dot}${running ? 'Running' : 'Offline'}`;
            setText('a-models', d.ollama.total_models !== undefined
                ? `${d.ollama.total_models} (${d.ollama.total_size_gb} GB)`
                : '—');
        }

        // Chat stats
        if (d.chat) {
            animateNum('s-queries', d.chat.total_queries       ?? 0);
            animateNum('s-fast',    d.chat.fast_path_hits      ?? 0);
            animateNum('s-llm',     d.chat.llm_hits            ?? 0);
            animateNum('s-static',  d.chat.static_hits         ?? 0);
            setText('s-time',   d.chat.last_response_time ? `${d.chat.last_response_time}s` : '—');
            setText('s-tps',    d.chat.last_tokens_per_sec ?? '—');
            setText('s-avg',    d.chat.avg_response_time   ? `${d.chat.avg_response_time}s` : '—');
            setText('s-up',     d.chat.uptime_seconds      ? formatUptime(d.chat.uptime_seconds) : '—');
            setText('si-tokens', d.chat.total_tokens_generated ?? '0');
        }

        // Retrieval / KB
        if (d.retrieval) {
            const docs   = d.retrieval.total_documents ?? 0;
            const chunks = d.retrieval.chunks          ?? 0;
            const qa     = d.retrieval.qa_pairs        ?? 0;
            const emb    = d.retrieval.embedding_dim   ?? 0;

            setText('bv-docs',   docs);
            setText('bv-chunks', chunks);
            setText('bv-qa',     qa);
            setText('bv-emb',    `${emb}d`);

            // Animate bars
            setTimeout(() => {
                const max = Math.max(docs, chunks, qa, 1);
                document.getElementById('bf-docs').style.width   = '100%';
                document.getElementById('bf-chunks').style.width = `${Math.min(100, chunks/max*100)}%`;
                document.getElementById('bf-qa').style.width     = `${Math.min(100, qa/max*100)}%`;
                document.getElementById('bf-emb').style.width    = `${Math.min(100, emb/768*100)}%`;
            }, 200);
        }

        analyticsLoaded = true;

        // Auto-poll if still on analytics page
        if (currentPage === 'analytics') {
            setTimeout(loadAnalytics, 1500);
        }

    } catch (err) {
        console.error('Analytics fetch failed:', err);
        // Show fallback in all stat cards
        document.querySelectorAll('.sc-num, .gauge-val, .ic-value').forEach(el => {
            if (el.textContent === '—' || el.textContent === '0') el.textContent = 'N/A';
        });
    }
}

document.getElementById('refresh-analytics').addEventListener('click', () => {
    analyticsLoaded = false;
    loadAnalytics();
});

// ═══════════════════════════════════════════════════════════════
// SETTINGS
// ═══════════════════════════════════════════════════════════════
const settingsEls = {
    temp:    document.getElementById('set-temp'),
    tempVal: document.getElementById('sv-temp'),
    ctx:     document.getElementById('set-ctx'),
    predict: document.getElementById('set-predict'),
    topk:    document.getElementById('set-topk'),
    bm25:    document.getElementById('set-bm25'),
    bm25Val: document.getElementById('sv-bm25'),
    vec:     document.getElementById('set-vec'),
    vecVal:  document.getElementById('sv-vec'),
    history: document.getElementById('set-history'),
    prompt:  document.getElementById('set-prompt'),
};

// Live slider value display
settingsEls.temp.addEventListener('input', () => {
    settingsEls.tempVal.textContent = parseFloat(settingsEls.temp.value).toFixed(2);
});

settingsEls.bm25.addEventListener('input', () => {
    const v = parseFloat(settingsEls.bm25.value);
    settingsEls.bm25Val.textContent = v.toFixed(2);
    // Keep vector weight as complement
    const cv = (1 - v).toFixed(2);
    settingsEls.vec.value = cv;
    settingsEls.vecVal.textContent = cv;
});

settingsEls.vec.addEventListener('input', () => {
    const v = parseFloat(settingsEls.vec.value);
    settingsEls.vecVal.textContent = v.toFixed(2);
    const cb = (1 - v).toFixed(2);
    settingsEls.bm25.value = cb;
    settingsEls.bm25Val.textContent = cb;
});

async function loadSettings() {
    try {
        const res = await fetch('/api/settings');
        if (!res.ok) throw new Error();
        const s = await res.json();
        if (s.llm) {
            settingsEls.temp.value    = s.llm.temperature;
            settingsEls.tempVal.textContent = s.llm.temperature.toFixed(2);
            settingsEls.ctx.value     = s.llm.num_ctx;
            settingsEls.predict.value = s.llm.num_predict;
        }
        if (s.retriever) {
            settingsEls.topk.value    = s.retriever.top_k;
            settingsEls.bm25.value    = s.retriever.bm25_weight;
            settingsEls.bm25Val.textContent = s.retriever.bm25_weight.toFixed(2);
            settingsEls.vec.value     = s.retriever.vector_weight;
            settingsEls.vecVal.textContent  = s.retriever.vector_weight.toFixed(2);
        }
        if (s.prompt) {
            settingsEls.history.checked = s.prompt.include_history;
            settingsEls.prompt.value    = s.prompt.system_prompt || '';
        }
    } catch {}
}

document.getElementById('apply-settings-btn').addEventListener('click', async () => {
    try {
        const res = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                llm: {
                    temperature: parseFloat(settingsEls.temp.value),
                    num_ctx:     parseInt(settingsEls.ctx.value),
                    num_predict: parseInt(settingsEls.predict.value),
                },
                retriever: {
                    top_k:         parseInt(settingsEls.topk.value),
                    bm25_weight:   parseFloat(settingsEls.bm25.value),
                    vector_weight: parseFloat(settingsEls.vec.value),
                },
                prompt: {
                    include_history: settingsEls.history.checked,
                    system_prompt:   settingsEls.prompt.value || null,
                },
            }),
        });
        if (res.ok) {
            flashSuccess(document.getElementById('apply-settings-btn'), 'Saved!');
        }
    } catch {}
});

document.getElementById('reset-settings-btn').addEventListener('click', async () => {
    try {
        const res = await fetch('/api/settings/reset', { method: 'POST' });
        if (res.ok) loadSettings();
    } catch {}
});

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════
function shakeElement(el) {
    el.style.animation = 'none';
    el.getBoundingClientRect(); // reflow
    el.style.animation = 'shake 0.4s ease';
    setTimeout(() => el.style.animation = '', 400);
}

// Inject shake keyframe
const shakeStyle = document.createElement('style');
shakeStyle.textContent = `
@keyframes shake {
    0%,100% { transform: translateX(0); }
    20%      { transform: translateX(-6px); }
    40%      { transform: translateX(6px); }
    60%      { transform: translateX(-4px); }
    80%      { transform: translateX(4px); }
}
`;
document.head.appendChild(shakeStyle);

function flashSuccess(btn, label) {
    const orig = btn.innerHTML;
    btn.innerHTML = `<span class="material-symbols-outlined btn-icon" style="font-variation-settings:'FILL' 1">check_circle</span>${label}`;
    btn.style.background = 'linear-gradient(135deg,#064e3b,#10b981)';
    setTimeout(() => {
        btn.innerHTML = orig;
        btn.style.background = '';
    }, 2000);
}
