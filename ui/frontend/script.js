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
            <div class="text-body-lg leading-relaxed markdown-content">${parseMarkdown(message)}</div>
        </div>
    `;
    scrollToBottom();
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
    const loader = addBotMessageLoader();
    chatInput.value = '';
    
    // Lock input
    chatInput.disabled = true;
    submitBtn.disabled = true;
    submitBtn.classList.add('opacity-50', 'cursor-not-allowed');

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
                                    // 50ms Render Throttling for smoother UI
                                    if (now - lastUpdateTime > 50) {
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
        
        // Final UI render flush
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
