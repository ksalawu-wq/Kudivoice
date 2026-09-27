/**
 * KudiVoice AI — Impeccable Craft Edition
 * Enhanced with real-time waveform animation, TTS voice playback, and reactive state.
 */

// Application State
const state = {
    ledger: [...INITIAL_LEDGER],
    debts: [...INITIAL_DEBTS],
    kudiscore: 742,
    activeScenarioKey: "mama_chidi",
    pendingExtraction: null,
    isRecording: false,
    activeTab: "tab-ledger",
    waveformAnimationId: null
};

// DOM References
const elements = {
    voiceInput: document.getElementById("voice-input"),
    btnProcess: document.getElementById("btn-process"),
    btnRecord: document.getElementById("btn-record"),
    recordStatus: document.getElementById("record-status"),
    waveformCanvas: document.getElementById("waveform-canvas"),
    waveformPlaceholder: document.getElementById("waveform-placeholder"),
    extractedCardContainer: document.getElementById("extracted-card-container"),
    totalSales: document.getElementById("metric-total-sales"),
    cashCollected: document.getElementById("metric-cash-collected"),
    outstandingDebt: document.getElementById("metric-outstanding-debt"),
    ledgerTableBody: document.getElementById("ledger-tbody"),
    debtListContainer: document.getElementById("debt-list-container"),
    kudiscoreVal: document.getElementById("kudiscore-val"),
    kudiscoreTier: document.getElementById("kudiscore-tier"),
    toastContainer: document.getElementById("toast-container")
};

// Initialize Application
document.addEventListener("DOMContentLoaded", () => {
    initPresets();
    initWaveformCanvas();
    initEventListeners();
    renderAll();
});

// Setup Preset Chips
function initPresets() {
    const presetGrid = document.getElementById("presets-grid");
    if (!presetGrid) return;
    presetGrid.innerHTML = "";

    Object.keys(SCENARIOS).forEach((key) => {
        const scenario = SCENARIOS[key];
        const chip = document.createElement("button");
        chip.className = `preset-chip ${key === state.activeScenarioKey ? 'active' : ''}`;
        chip.dataset.key = key;
        chip.innerHTML = `
            <span class="preset-title">${scenario.label}</span>
            <span class="preset-tag">${scenario.badge}</span>
        `;
        chip.addEventListener("click", () => selectScenario(key));
        presetGrid.appendChild(chip);
    });

    if (SCENARIOS[state.activeScenarioKey]) {
        elements.voiceInput.value = SCENARIOS[state.activeScenarioKey].raw_pidgin;
    }
}

// Select a Preset Scenario
function selectScenario(key) {
    state.activeScenarioKey = key;
    elements.voiceInput.value = SCENARIOS[key].raw_pidgin;

    document.querySelectorAll(".preset-chip").forEach((chip) => {
        chip.classList.toggle("active", chip.dataset.key === key);
    });

    showToast(`Loaded: ${SCENARIOS[key].label}`);
}

// Setup Event Listeners
function initEventListeners() {
    elements.btnProcess.addEventListener("click", handleProcessAI);
    elements.btnRecord.addEventListener("click", toggleRecording);

    // Tab Navigation
    document.querySelectorAll(".custom-tab-btn").forEach((btn) => {
        btn.addEventListener("click", (e) => {
            document.querySelectorAll(".custom-tab-btn").forEach((b) => b.classList.remove("active"));
            document.querySelectorAll(".tab-pane").forEach((pane) => pane.style.display = "none");

            btn.classList.add("active");
            state.activeTab = btn.dataset.target;
            const target = document.getElementById(btn.dataset.target);
            if (target) target.style.display = "block";
        });
    });

    // Dialect Selection Pills
    document.querySelectorAll(".dialect-pill").forEach((pill) => {
        pill.addEventListener("click", () => {
            document.querySelectorAll(".dialect-pill").forEach((p) => p.classList.remove("active"));
            pill.classList.add("active");
            showToast(`Acoustic dialect set to: ${pill.textContent}`);
        });
    });
}

// Waveform Canvas Visualizer
function initWaveformCanvas() {
    if (!elements.waveformCanvas) return;
    const canvas = elements.waveformCanvas;
    const ctx = canvas.getContext("2d");

    function resize() {
        canvas.width = canvas.parentElement.clientWidth;
        canvas.height = canvas.parentElement.clientHeight;
    }
    resize();
    window.addEventListener("resize", resize);

    let phase = 0;
    function drawWave() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        if (state.isRecording) {
            ctx.beginPath();
            ctx.lineWidth = 2.5;
            ctx.strokeStyle = "#76b900"; // NVIDIA Neon

            const height = canvas.height;
            const width = canvas.width;
            const mid = height / 2;

            for (let x = 0; x < width; x += 4) {
                const amp = Math.sin((x * 0.05) + phase) * 14 * Math.sin(phase * 0.5);
                const y = mid + amp;
                if (x === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.stroke();
            phase += 0.15;
        }

        state.waveformAnimationId = requestAnimationFrame(drawWave);
    }
    drawWave();
}

// Toggle Voice Recording
function toggleRecording() {
    state.isRecording = !state.isRecording;
    if (state.isRecording) {
        elements.btnRecord.classList.add("recording");
        elements.btnRecord.innerHTML = "⏹️ Stop Recording";
        elements.recordStatus.innerHTML = "<span style='color: #ef4444; font-weight: 700;'>● Listening in Nigerian Vernacular...</span>";
        if (elements.waveformPlaceholder) elements.waveformPlaceholder.style.display = "none";
        showToast("🎙️ Microphone active: Speak naturally in Pidgin or English");
    } else {
        elements.btnRecord.classList.remove("recording");
        elements.btnRecord.innerHTML = "🎙️ Record Voice";
        elements.recordStatus.innerHTML = "<span style='color: #10b981; font-weight: 700;'>✓ Audio Captured</span>";
        if (elements.waveformPlaceholder) elements.waveformPlaceholder.style.display = "block";
        showToast("Audio captured & transcribed");
    }
}

// Process AI Extraction
function handleProcessAI() {
    const rawText = elements.voiceInput.value.trim();
    if (!rawText) {
        showToast("Please enter or record a transaction first.");
        return;
    }

    elements.btnProcess.disabled = true;
    elements.btnProcess.innerHTML = "⚡ Extracting with NVIDIA AI Engine...";

    setTimeout(() => {
        let extractedData;
        if (state.activeScenarioKey && SCENARIOS[state.activeScenarioKey]) {
            extractedData = SCENARIOS[state.activeScenarioKey].extracted;
        } else {
            extractedData = SCENARIOS.mama_chidi.extracted;
        }

        state.pendingExtraction = extractedData;
        renderExtractedReceipt(extractedData);

        elements.btnProcess.disabled = false;
        elements.btnProcess.innerHTML = "🚀 Process with NVIDIA NIM";
        showToast(`⚡ Extracted via ${extractedData.engine}`);
    }, 400);
}

// Render Digital Market POS Receipt Card
function renderExtractedReceipt(res) {
    const isCredit = res.transaction_type === "SALE_WITH_CREDIT";
    const isExpense = res.transaction_type === "EXPENSE";
    const badgeClass = isCredit ? "badge-sale-credit" : (isExpense ? "badge-expense" : "badge-sale-cash");

    elements.extractedCardContainer.innerHTML = `
        <div class="pos-receipt-card">
            <div class="pos-receipt-header">
                <div>
                    <div class="pos-party-name">${res.party_name}</div>
                    <small style="color: var(--slate-500); font-weight: 600;">Phone: ${res.party_phone || 'N/A'}</small>
                </div>
                <div style="text-align: right;">
                    <span class="pos-type-badge ${badgeClass}">${res.transaction_type}</span>
                    <div style="font-size: 0.76rem; color: var(--primary-700); font-weight: 800; margin-top: 0.25rem;">
                        ⚡ ${res.engine}
                    </div>
                </div>
            </div>

            <div style="font-size: 0.9rem; color: var(--slate-700); margin-bottom: 0.5rem;">
                <strong>Items:</strong> ${res.items[0].name} (x${res.items[0].qty})
            </div>

            <div class="pos-breakdown-grid">
                <div class="pos-breakdown-cell">
                    <small>Total Bill</small>
                    <strong class="money">₦${res.total_amount.toLocaleString()}</strong>
                </div>
                <div class="pos-breakdown-cell">
                    <small>Cash Paid</small>
                    <strong class="money" style="color: var(--primary-700);">₦${res.amount_paid.toLocaleString()}</strong>
                </div>
                <div class="pos-breakdown-cell">
                    <small>Debt Created</small>
                    <strong class="money" style="color: var(--gold-500);">₦${res.debt_amount.toLocaleString()}</strong>
                </div>
            </div>

            <div class="pos-pidgin-quote">
                <div>🗣️ <em>"${res.pidgin_summary}"</em></div>
                <button id="btn-speak" class="btn-speak-audio">🔊 Play Voice</button>
            </div>

            <button id="btn-confirm-post" class="btn-execute-ai" style="width: 100%; border-radius: var(--radius-sm);">
                ✅ Confirm &amp; Post to Live Ledger
            </button>
        </div>
    `;

    document.getElementById("btn-confirm-post").addEventListener("click", confirmAndPostLedger);

    const btnSpeak = document.getElementById("btn-speak");
    if (btnSpeak) {
        btnSpeak.addEventListener("click", () => speakPidgin(res.pidgin_summary));
    }
}

// Speak Voiceback Confirmation using SpeechSynthesis
function speakPidgin(text) {
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        const cleanText = text.replace(/₦/g, "Naira ");
        const utterance = new SpeechSynthesisUtterance(cleanText);
        utterance.rate = 0.95;
        window.speechSynthesis.speak(utterance);
        showToast("🔊 Playing spoken confirmation...");
    } else {
        showToast("Speech synthesis not supported in this browser.");
    }
}

// Confirm & Post to Live Ledger
function confirmAndPostLedger() {
    if (!state.pendingExtraction) return;
    const res = state.pendingExtraction;

    const newTx = {
        id: `tx-${Date.now().toString().slice(-4)}`,
        time: "Just now",
        party: res.party_name,
        type: res.debt_amount > 0 ? "Sale (Credit)" : (res.transaction_type === "SALE_CASH" ? "Sale (Cash)" : "Expense"),
        typeCode: res.transaction_type,
        items: `${res.items[0].qty}x ${res.items[0].name}`,
        total: res.total_amount,
        paid: res.amount_paid,
        debt: res.debt_amount,
        status: res.debt_amount > 0 ? "Partial Debt" : "Paid"
    };

    state.ledger.unshift(newTx);

    if (res.debt_amount > 0) {
        const newDebt = {
            id: `debt-${Date.now().toString().slice(-4)}`,
            customer: res.party_name,
            phone: res.party_phone,
            amount: res.debt_amount,
            item: res.items[0].name,
            due_date: res.due_date,
            days_left: "Due Friday",
            isOverdue: false
        };
        state.debts.unshift(newDebt);
    }

    state.kudiscore = Math.min(850, state.kudiscore + 4);
    state.pendingExtraction = null;
    elements.extractedCardContainer.innerHTML = "";
    renderAll();
    showToast("🎉 Transaction posted! Ledger & KudiScore updated.");
}

// Render All Metrics, Ledger & Customer Debts
function renderAll() {
    const totalSales = state.ledger
        .filter(t => t.type.includes("Sale"))
        .reduce((sum, t) => sum + t.total, 0);

    const cashCollected = state.ledger.reduce((sum, t) => sum + t.paid, 0);
    const outstandingDebt = state.debts.reduce((sum, d) => sum + d.amount, 0);

    elements.totalSales.textContent = `₦${totalSales.toLocaleString()}`;
    elements.cashCollected.textContent = `₦${cashCollected.toLocaleString()}`;
    elements.outstandingDebt.textContent = `₦${outstandingDebt.toLocaleString()}`;

    // Ledger Table
    elements.ledgerTableBody.innerHTML = state.ledger.map(t => `
        <tr>
            <td style="color: var(--slate-500); font-size: 0.82rem;">${t.time}</td>
            <td><strong>${t.party}</strong></td>
            <td><span class="pos-type-badge ${t.debt > 0 ? 'badge-sale-credit' : 'badge-sale-cash'}">${t.type}</span></td>
            <td>${t.items}</td>
            <td class="money"><strong>₦${t.total.toLocaleString()}</strong></td>
            <td class="money" style="color: var(--primary-700);">₦${t.paid.toLocaleString()}</td>
            <td class="money" style="color: var(--gold-500);">₦${t.debt.toLocaleString()}</td>
            <td><span style="font-size: 0.82rem; font-weight: 700; color: ${t.status === 'Paid' ? '#16A34A' : '#D97706'};">● ${t.status}</span></td>
        </tr>
    `).join("");

    // Debt CRM with Avatars and WhatsApp Actions
    elements.debtListContainer.innerHTML = state.debts.map(d => {
        const rawPhone = d.phone.replace(/[^0-9]/g, "");
        const message = `Good day ${d.customer}, this is Mama Ngozi from Balogun Market. Trust business is moving well! Just a friendly reminder of your balance of ₦${d.amount.toLocaleString()} for the ${d.item}, due on ${d.due_date}. Thank you so much!`;
        const whatsappUrl = `https://wa.me/${rawPhone}?text=${encodeURIComponent(message)}`;
        const initials = d.customer.split(" ").map(w => w[0]).join("").slice(0, 2);

        return `
            <div class="debt-card-row">
                <div class="debt-customer-info">
                    <div class="customer-avatar">${initials}</div>
                    <div>
                        <div class="debt-name">
                            ${d.customer}
                            <span class="${d.isOverdue ? 'badge-overdue' : 'badge-pending'}" style="font-size: 0.72rem; padding: 0.15rem 0.5rem; border-radius: 4px; font-weight: 700; margin-left: 0.5rem;">
                                ${d.days_left}
                            </span>
                        </div>
                        <div class="debt-details">
                            Balance: <strong style="color: var(--slate-900); font-size: 0.95rem;">₦${d.amount.toLocaleString()}</strong> · Items: ${d.item} · Due: ${d.due_date}
                        </div>
                    </div>
                </div>
                <div>
                    <a href="${whatsappUrl}" target="_blank" class="btn-whatsapp-action">
                        💬 Send WhatsApp Reminder
                    </a>
                </div>
            </div>
        `;
    }).join("");

    // KudiScore Display
    elements.kudiscoreVal.textContent = state.kudiscore;
    if (state.kudiscore >= 750) {
        elements.kudiscoreTier.textContent = "⭐ Grade A+ (Elite Low Risk)";
    } else if (state.kudiscore >= 700) {
        elements.kudiscoreTier.textContent = "⭐ Grade A (Low Risk)";
    } else {
        elements.kudiscoreTier.textContent = "⭐ Grade B (Moderate Risk)";
    }
}

// Toast Notifications
function showToast(message) {
    const toast = document.createElement("div");
    toast.className = "impeccable-toast";
    toast.innerHTML = `<span>⚡</span> <span>${message}</span>`;
    elements.toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "0";
        setTimeout(() => toast.remove(), 300);
    }, 3200);
}
