// Theme Toggle
const themeToggleBtn = document.getElementById('theme-toggle');
const htmlTag = document.documentElement;

// On load, check preference
if (localStorage.getItem('theme') === 'light') {
    htmlTag.classList.remove('dark');
    themeToggleBtn.textContent = 'light_mode';
}

themeToggleBtn.addEventListener('click', () => {
    if (htmlTag.classList.contains('dark')) {
        htmlTag.classList.remove('dark');
        themeToggleBtn.textContent = 'light_mode';
        localStorage.setItem('theme', 'light');
    } else {
        htmlTag.classList.add('dark');
        themeToggleBtn.textContent = 'dark_mode';
        localStorage.setItem('theme', 'dark');
    }
});

// Sidebar Toggle
const sidebar = document.getElementById('sidebar');
const menuBtns = document.querySelectorAll('.menu-toggle');
menuBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        sidebar.classList.toggle('-translate-x-full');
        // Also close settings sidebar
        if (!settingsSidebar.classList.contains('translate-x-full')) {
            settingsSidebar.classList.add('translate-x-full');
        }
    });
});
// Close sidebar when clicking outside on mobile
document.addEventListener('click', (e) => {
    if (window.innerWidth < 1024 && !sidebar.contains(e.target) && !e.target.closest('.menu-toggle')) {
        if (!sidebar.classList.contains('-translate-x-full')) {
            sidebar.classList.add('-translate-x-full');
        }
    }
});

// ============================================================
// HARDCODED QA MAPPING
// ============================================================
const HARDCODED_QA = {
    'how to apply': `Apply to NUST, visit nust.edu.pk/admissions/ and follow these steps:

(1) Register online with your CNIC
(2) Fill in personal and educational details
(3) Upload required documents (marks sheets, CNIC copy)
(4) Pay application fee
(5) Submit your application before the deadline

The application portal usually opens in March and closes in May. Make sure you meet the eligibility criteria before applying.`,

    'what is the net syllabus': `NUST's NET (National Entrance Test) syllabus includes:

(1) Mathematics - Calculus, Algebra, Geometry
(2) Physics - Mechanics, Electricity, Magnetism, Modern Physics
(3) Chemistry - Organic, Inorganic, and Physical Chemistry
(4) English - Reading Comprehension, Grammar

The test is designed to assess reasoning and problem-solving skills. You can download the detailed syllabus from nust.edu.pk/admissions/.`,

    'hostel guidelines': `NUST provides residential facilities for both male and female students. Hostel guidelines include:

(1) Check-in procedures and documentation required
(2) Room allocation based on merit and preference
(3) Rules for visitors and guest policies
(4) Curfew timings (usually 11 PM on weekdays)
(5) Hostel dues must be paid on time

All students must follow the code of conduct. For detailed guidelines, contact the Hostel Office or visit nust.edu.pk.`
};

function normalizeQuery(query) {
    // Remove special characters and convert to lowercase
    return query.toLowerCase().replace(/[^a-z0-9\s]/g, '').trim();
}

function findHardcodedAnswer(query) {
    const normalized = normalizeQuery(query);
    const queryWords = new Set(normalized.split(/\s+/).filter(w => w.length > 0));
    
    for (const [key, answer] of Object.entries(HARDCODED_QA)) {
        const keyWords = key.split(/\s+/);
        // Require ALL key words to be present in the query for a match
        const matchedKeyWords = keyWords.filter(w => queryWords.has(w));
        if (matchedKeyWords.length === keyWords.length) {
            return answer;
        }
    }
    return null;
}

// Chat Logic
const chatContainer = document.getElementById('chat-container');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const submitBtn = document.getElementById('submit-btn');
const suggestionBtns = document.querySelectorAll('.suggestion-btn');
const modelSelect = document.getElementById('model-select');

// Auto format URLs, bold text, and strip Sources/Time meta footer
function parseMarkdown(text) {
    let output = text;
    
    if (text.includes('📌')) {
        output = text.split('📌')[0].trim();
    } else if (text.includes('⏱️')) {
        output = text.split('⏱️')[0].trim();
    }

    let parsed = output.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Format numbered lists with line breaks - only match at start of line or after newline
    parsed = parsed.replace(/(?:^|\n)(\s*)(\d+\))\s/gm, '<br><br>$1$2 ');
    
    parsed = parsed.replace(/\n/g, '<br>');
    return parsed;
}

function scrollToBottom() {
    window.scrollTo(0, document.body.scrollHeight);
}

const botAvatarHtml = `
    <div class="w-8 h-8 rounded-full bg-white flex items-center justify-center shadow overflow-hidden border border-slate-200 dark:border-slate-800 shrink-0">
        <img src="/resources/nust_png.png" class="w-5 h-5 object-contain" alt="NUST">
    </div>
`;
const botNameHtml = `<span class="text-[10px] font-label font-bold uppercase tracking-widest text-blue-700 dark:text-yellow-500">NUST Assistant</span>`;

const userAvatarHtml = `
    <div class="w-8 h-8 rounded-full bg-blue-600 dark:bg-blue-500 flex items-center justify-center shrink-0 shadow-inner">
        <span class="text-white font-bold text-[10px] font-manrope uppercase tracking-widest">You</span>
    </div>
`;
const userNameHtml = `<span class="text-[10px] font-label font-bold uppercase tracking-widest text-slate-500 dark:text-slate-400">Candidate</span>`;


function addUserMessage(message) {
    const div = document.createElement('div');
    div.className = 'flex flex-col items-end gap-2 ml-auto max-w-[85%]';
    div.innerHTML = `
        <div class="flex items-center gap-3 mb-1">
            ${userNameHtml}
            ${userAvatarHtml}
        </div>
        <div class="bg-blue-600 dark:bg-blue-900/60 p-4 rounded-2xl rounded-tr-none shadow-md text-white dark:text-blue-50">
            <p class="text-body-lg leading-relaxed">${message}</p>
        </div>
    `;
    chatContainer.appendChild(div);
    scrollToBottom();
}

function addBotMessageLoader() {
    const div = document.createElement('div');
    div.className = 'flex flex-col items-start gap-2 max-w-[85%] bot-message-loader';
    div.innerHTML = `
        <div class="flex items-center gap-3 mb-1">
            ${botAvatarHtml}
            ${botNameHtml}
        </div>
        <div class="glass-panel p-4 rounded-2xl rounded-tl-none border border-slate-200 dark:border-slate-800/50 shadow-md bg-white/90 dark:bg-[#071324]/80 text-slate-800 dark:text-slate-200">
            <div class="flex items-center gap-2 font-medium text-sm tracking-wide">
                <span class="thinking-text">Crafting response</span>
                <div class="typing-indicator flex items-center gap-1 text-blue-600 dark:text-yellow-500">
                    <span></span><span></span><span></span>
                </div>
            </div>
        </div>
    `;
    chatContainer.appendChild(div);
    scrollToBottom();
    return div;
}

function replaceBotMessageLoader(loaderDiv, message) {
    loaderDiv.classList.remove('bot-message-loader');
    loaderDiv.innerHTML = `
        <div class="flex items-center gap-3 mb-1">
            ${botAvatarHtml}
            ${botNameHtml}
        </div>
        <div class="glass-panel p-4 rounded-2xl rounded-tl-none border border-slate-200 dark:border-slate-800/50 shadow-md bg-white/90 dark:bg-slate-800/80 text-slate-800 dark:text-slate-200">
            <div class="text-body-lg leading-relaxed markdown-content" id="typed-content">${parseMarkdown(message)}</div>
        </div>
    `;
    scrollToBottom();
}

async function typeStreamingResponse(contentDiv, fullText) {
    // Type out the response character by character for natural feel
    const text = parseMarkdown(fullText);
    let displayText = '';
    const typingSpeed = 5; // milliseconds per character (faster = more natural)
    
    for (let i = 0; i < text.length; i++) {
        displayText += text[i];
        contentDiv.innerHTML = displayText;
        scrollToBottom();
        await new Promise(resolve => setTimeout(resolve, typingSpeed));
    }
}

async function initializeModels() {
    try {
        const response = await fetch('/api/models');
        if (response.ok) {
            const data = await response.json();
            modelSelect.innerHTML = '';
            data.models.forEach(model => {
                const opt = document.createElement('option');
                opt.value = model;
                opt.textContent = model;
                if (model === data.current) {
                    opt.selected = true;
                }
                modelSelect.appendChild(opt);
            });
        }
    } catch (e) {
        console.error("Failed to load models.", e);
        modelSelect.innerHTML = '<option value="">Local Model Only</option>';
    }
}

modelSelect.addEventListener('change', async (e) => {
    const selected = e.target.value;
    try {
        await fetch('/api/set_model', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model: selected })
        });
    } catch (err) {
        console.error("Failed to set model", err);
    }
});

async function handleChat(message) {
    addUserMessage(message);
    chatInput.value = '';
    
    // Lock input
    chatInput.disabled = true;
    submitBtn.disabled = true;
    submitBtn.classList.add('opacity-50', 'cursor-not-allowed');
    
    // Artificial delay of 2-3 seconds for consistent response feel
    let craftingDelay = Math.random() * 1000 + 2000; // 2000-3000ms

    // Check for hardcoded answer first
    const hardcodedAnswer = findHardcodedAnswer(message);
    if (hardcodedAnswer) {
        const loader = addBotMessageLoader();
        await new Promise(resolve => setTimeout(resolve, craftingDelay));
        replaceBotMessageLoader(loader, hardcodedAnswer);
        const contentDiv = loader.querySelector('#typed-content');
        if (contentDiv) await typeStreamingResponse(contentDiv, hardcodedAnswer);
        
        // Unlock input
        chatInput.disabled = false;
        submitBtn.disabled = false;
        submitBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        chatInput.focus();
        return;
    }

    const loader = addBotMessageLoader();
    
    // Apply crafting delay before reading response stream
    await new Promise(resolve => setTimeout(resolve, craftingDelay));
    
    try {
        const payload = {
            message: message,
            history: [] // Stateless tracking handled by backend mostly
        };

        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.body) throw new Error("ReadableStream not supported by browser.");
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let done = false;
        let contentDiv = null;
        let lastUpdateTime = 0;
        let lastText = "";

        while (!done) {
            const { value, done: readerDone } = await reader.read();
            done = readerDone;
            if (value) {
                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');
                
                for (let line of lines) {
                    if (line.startsWith('data: ')) {
                        const dataStr = line.slice(6).trim();
                        if (dataStr === '[DONE]') break;
                        if (dataStr) {
                            try {
                                const parsed = JSON.parse(dataStr);
                                if (parsed.text) {
                                    // First token received? Convert loader to content container
                                    if (!contentDiv) {
                                        loader.classList.remove('bot-message-loader');
                                        loader.innerHTML = `
                                            <div class="flex items-center gap-3 mb-1">
                                                ${botAvatarHtml}
                                                ${botNameHtml}
                                            </div>
                                            <div class="glass-panel p-4 rounded-2xl rounded-tl-none border border-slate-200 dark:border-slate-800/50 shadow-md bg-white/90 dark:bg-[#071324]/80 text-slate-800 dark:text-slate-200">
                                                <div class="text-body-lg leading-relaxed markdown-content" id="stream-content"></div>
                                            </div>
                                        `;
                                        contentDiv = loader.querySelector('#stream-content');
                                    }
                                    
                                    lastText = parsed.text;
                                    const now = Date.now();
                                    // 20ms Render Throttling for faster, more responsive streaming
                                    if (now - lastUpdateTime > 20) {
                                        contentDiv.innerHTML = parseMarkdown(lastText);
                                        scrollToBottom();
                                        lastUpdateTime = now;
                                    }
                                }
                            } catch(e) {}
                        }
                    }
                }
            }
        }
        
        // Final UI render flush (no typing animation for API responses)
        if (contentDiv && lastText) {
            contentDiv.innerHTML = parseMarkdown(lastText);
            scrollToBottom();
        }

    } catch (error) {
        console.error("API Error:", error);
        replaceBotMessageLoader(loader, "Connection error. Ensure the NUST assistant backend is running.");
    } finally {
        // Unlock input
        chatInput.disabled = false;
        submitBtn.disabled = false;
        submitBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        chatInput.focus();
    }
}

chatForm.addEventListener('submit', (e) => {
    e.preventDefault();
    if (chatInput.disabled) return;
    const msg = chatInput.value.trim();
    if (msg) {
        handleChat(msg);
    }
});

suggestionBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        if (!chatInput.disabled) {
            handleChat(btn.textContent);
        }
    });
});

// Initialize environment
initializeModels();

// ============================================================
// SETTINGS SIDEBAR
// ============================================================

const settingsBtn = document.getElementById('settings-btn');
const settingsSidebar = document.getElementById('settings-sidebar');
const closeSettingsSidebarBtn = document.getElementById('close-settings-sidebar-btn');
const applySettingsSbBtn = document.getElementById('apply-settings-sb-btn');
const resetSettingsSbBtn = document.getElementById('reset-settings-sb-btn');
const clearChatBtn = document.getElementById('clear-chat-btn');

// Sidebar form elements
const tempSliderSb = document.getElementById('temperature-slider-sb');
const tempValueSb = document.getElementById('temp-value-sb');
const numCtxSelectSb = document.getElementById('num-ctx-select-sb');
const numPredictSelectSb = document.getElementById('num-predict-select-sb');
const topKSelectSb = document.getElementById('top-k-select-sb');
const bm25SliderSb = document.getElementById('bm25-slider-sb');
const bm25ValueSb = document.getElementById('bm25-value-sb');
const vectorSliderSb = document.getElementById('vector-slider-sb');
const vectorValueSb = document.getElementById('vector-value-sb');
const includeHistoryCheckSb = document.getElementById('include-history-check-sb');
const systemPromptTextareaSb = document.getElementById('system-prompt-textarea-sb');

// Load settings on page load
async function loadSettings() {
    try {
        const response = await fetch('/api/settings');
        if (response.ok) {
            const settings = await response.json();
            
            // LLM Settings
            tempSliderSb.value = settings.llm.temperature;
            tempValueSb.textContent = settings.llm.temperature.toFixed(2);
            numCtxSelectSb.value = settings.llm.num_ctx;
            numPredictSelectSb.value = settings.llm.num_predict;
            
            // Retrieval Settings
            topKSelectSb.value = settings.retriever.top_k;
            bm25SliderSb.value = settings.retriever.bm25_weight;
            bm25ValueSb.textContent = settings.retriever.bm25_weight.toFixed(2);
            vectorSliderSb.value = settings.retriever.vector_weight;
            vectorValueSb.textContent = settings.retriever.vector_weight.toFixed(2);
            
            // Prompt Settings
            includeHistoryCheckSb.checked = settings.prompt.include_history;
            systemPromptTextareaSb.value = settings.prompt.system_prompt || '';
        }
    } catch (e) {
        console.error("Failed to load settings", e);
    }
}

// Update sliders display
tempSliderSb.addEventListener('input', (e) => {
    tempValueSb.textContent = parseFloat(e.target.value).toFixed(2);
});

bm25SliderSb.addEventListener('input', (e) => {
    bm25ValueSb.textContent = parseFloat(e.target.value).toFixed(2);
    // Sync vector weight to maintain sum ≈ 1.0
    const newVector = (1 - parseFloat(e.target.value)).toFixed(2);
    vectorSliderSb.value = newVector;
    vectorValueSb.textContent = newVector;
});

vectorSliderSb.addEventListener('input', (e) => {
    vectorValueSb.textContent = parseFloat(e.target.value).toFixed(2);
    // Sync bm25 weight to maintain sum ≈ 1.0
    const newBm25 = (1 - parseFloat(e.target.value)).toFixed(2);
    bm25SliderSb.value = newBm25;
    bm25ValueSb.textContent = newBm25;
});

// Sidebar controls
settingsBtn.addEventListener('click', () => {
    settingsSidebar.classList.remove('translate-x-full');
    loadSettings();
});

closeSettingsSidebarBtn.addEventListener('click', () => {
    settingsSidebar.classList.add('translate-x-full');
});

// Close sidebar when clicking outside on mobile
document.addEventListener('click', (e) => {
    if (window.innerWidth < 1024 && !settingsSidebar.contains(e.target) && !e.target.closest('#settings-btn')) {
        if (!settingsSidebar.classList.contains('translate-x-full')) {
            settingsSidebar.classList.add('translate-x-full');
        }
    }
});

// Apply settings
applySettingsSbBtn.addEventListener('click', async () => {
    try {
        const updateData = {
            llm: {
                temperature: parseFloat(tempSliderSb.value),
                num_ctx: parseInt(numCtxSelectSb.value),
                num_predict: parseInt(numPredictSelectSb.value),
            },
            retriever: {
                top_k: parseInt(topKSelectSb.value),
                bm25_weight: parseFloat(bm25SliderSb.value),
                vector_weight: parseFloat(vectorSliderSb.value),
            },
            prompt: {
                include_history: includeHistoryCheckSb.checked,
                system_prompt: systemPromptTextareaSb.value || null,
            },
        };

        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updateData),
        });

        if (response.ok) {
            settingsSidebar.classList.add('translate-x-full');
        } else {
            console.error('Failed to apply settings');
        }
    } catch (e) {
        console.error("Failed to apply settings", e);
    }
});

// Reset settings
resetSettingsSbBtn.addEventListener('click', async () => {
    try {
        const response = await fetch('/api/settings/reset', { method: 'POST' });
        if (response.ok) {
            loadSettings();
        }
    } catch (e) {
        console.error("Failed to reset settings", e);
    }
});

// Clear chat
clearChatBtn.addEventListener('click', () => {
    chatContainer.innerHTML = `
        <div class="flex flex-col items-start gap-2 max-w-[90%] sm:max-w-[85%] bot-message">
            <div class="flex items-center gap-3 mb-1">
                <div class="w-8 h-8 rounded-full bg-white flex items-center justify-center shadow overflow-hidden border border-slate-200 dark:border-slate-800 shrink-0">
                    <img src="/resources/nust_png.png" class="w-5 h-5 object-contain" alt="NUST">
                </div>
                <span class="text-[10px] font-label font-bold uppercase tracking-widest text-blue-700 dark:text-yellow-500">NUST Assistant</span>
            </div>
            <div class="glass-panel p-4 rounded-2xl rounded-tl-none border border-slate-200 dark:border-slate-800/50 shadow-md bg-white/90 dark:bg-slate-800/80 text-slate-800 dark:text-slate-200">
                <p class="text-body-lg leading-relaxed">Assalam-o-Alaikum! I am the official NUST Admission Assistant. What information are you looking for regarding your academic journey?</p>
            </div>
        </div>
    `;
    scrollToBottom();
});

// Load settings on startup
loadSettings();
