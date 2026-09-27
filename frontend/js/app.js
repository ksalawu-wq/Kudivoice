/**
 * KudiVoice AI - Core Application Logic
 * Pure JavaScript web client with reactive ledger state & WhatsApp integration.
 */

// Application State
const state = {
    ledger: [...INITIAL_LEDGER],
    debts: [...INITIAL_DEBTS],
    kudiscore: 742,
    activeScenarioKey: "mama_chidi",
    pendingExtraction: null,
    isRecording: false
};

// DOM Elements
const elements = {
    voiceInput: document.getElementById("voice-input"),
    btnProcess: document.getElementById("btn-process"),
    btnRecord: document.getElementById("btn-record"),
    recordStatus: document.getElementById("record-status"),
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
    initEventListeners();
    renderAll();
});

// Setup Preset Chips
function initPresets() {
    const presetGrid = document.getElementById("presets-grid");
    presetGrid.innerHTML = "";

    Object.keys(SCENARIOS).forEach((key) => {
        const scenario = SCENARIOS[key];
        const chip = document.createElement("button");
        chip.className = `preset-chip ${key === state.activeScenarioKey ? 'active' : ''}`;
        chip.dataset.key = key;
        chip.innerHTML = `
            <span>${scenario.label}</span>
            <span class="preset-chip-sub">${scenario.badge}</span>
        `;
        chip.addEventListener("click", () => selectScenario(key));
        presetGrid.appendChild(chip);
    });

    // Populate initial text
    if (SCENARIOS[state.activeScenarioKey]) {
        elements.voiceInput.value = SCENARIOS[state.activeScenarioKey].raw_pidgin;
    }
}

// Select a Preset Scenario
function selectScenario(key) {
    state.activeScenarioKey = key;
    elements.voiceInput.value = SCENARIOS[key].raw_pidgin;

    // Update active UI classes
    document.querySelectorAll(".preset-chip").forEach((chip) => {
        chip.classList.toggle("active", chip.dataset.key === key);
    });

    showToast(`Loaded scenario: ${SCENARIOS[key].label}`);
}

// Event Listeners
function initEventListeners() {
    // Process Button
    elements.btnProcess.addEventListener("click", handleProcessAI);

    // Record Audio Button (Web Audio mic or simulation)
    elements.btnRecord.addEventListener("click", toggleRecording);

    // Tab Navigation
    document.querySelectorAll(".tab-btn").forEach((btn) => {
        btn.addEventListener("click", (e) => {
            document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
            document.querySelectorAll(".tab-pane").forEach((pane) => pane.style.display = "none");

            btn.classList.add("active");
            const target = document.getElementById(btn.dataset.target);
            if (target) target.style.display = "block";
        });
    });
}

// Simulate / Toggle Voice Recording
function toggleRecording() {
    state.isRecording = !state.isRecording;
    if (state.isRecording) {
        elements.btnRecord.style.background = "#DC2626";
        elements.btnRecord.innerHTML = "⏹️ Stop Recording";
        elements.recordStatus.innerHTML = "<span style='color: #DC2626; font-weight: 700;'>● Listening in Nigerian Pidgin...</span>";
    } else {
        elements.btnRecord.style.background = "var(--slate-800)";
        elements.btnRecord.innerHTML = "🎙️ Record Spoken Voice";
        elements.recordStatus.innerHTML = "<span style='color: #00875A;'>✓ Voice captured</span>";
        showToast("Audio captured successfully");
    }
}

// Process with AI Engine
function handleProcessAI() {
    const rawText = elements.voiceInput.value.trim();
    if (!rawText) {
        showToast("Please enter or record a transaction first.");
        return;
    }

    elements.btnProcess.disabled = true;
    elements.btnProcess.innerHTML = "⚡ Extracting with NVIDIA NIM...";

    setTimeout(() => {
        // Find matching preset or use generic structure
        let extractedData;
        if (state.activeScenarioKey && SCENARIOS[state.activeScenarioKey]) {
            extractedData = SCENARIOS[state.activeScenarioKey].extracted;
        } else {
            extractedData = SCENARIOS.mama_chidi.extracted;
        }

        state.pendingExtraction = extractedData;
        renderExtractedCard(extractedData);

        elements.btnProcess.disabled = false;
        elements.btnProcess.innerHTML = "🚀 Process with NVIDIA NIM / Dual Engine";
        showToast(`⚡ Extracted via ${extractedData.engine}`);
    }, 450);
}

// Render Extracted Transaction Review Card
function renderExtractedCard(res) {
    const typeColor = res.transaction_type === "SALE_CASH" ? "#00875A" : 
                     (res.transaction_type === "SALE_WITH_CREDIT" ? "#D97706" : "#2563EB");

    elements.extractedCardContainer.innerHTML = `
        <div class="extracted-card" style="border-color: ${typeColor};">
            <div class="extracted-header">
                <span class="badge-pill" style="background: ${typeColor}; color: white;">
                    ${res.transaction_type}
                </span>
                <span style="font-size: 0.8rem; color: var(--nvidia); font-weight: 700;">
                    ⚡ ${res.engine} · ${Math.round(res.confidence * 100)}% Confidence
                </span>
            </div>
            <div class="extracted-party">${res.party_name}</div>
            <div style="font-size: 0.88rem; color: var(--slate-600); margin: 0.35rem 0;">
                <strong>Items:</strong> ${res.items[0].name} (x${res.items[0].qty})
            </div>
            <div class="extracted-breakdown">
                <div class="breakdown-item">
                    <small>Total Amount</small>
                    <strong class="money">₦${res.total_amount.toLocaleString()}</strong>
                </div>
                <div class="breakdown-item">
                    <small>Cash Paid</small>
                    <strong class="money" style="color: var(--primary);">₦${res.amount_paid.toLocaleString()}</strong>
                </div>
                <div class="breakdown-item">
                    <small>Debt Created</small>
                    <strong class="money" style="color: var(--warning);">₦${res.debt_amount.toLocaleString()}</strong>
                </div>
            </div>
            <div class="voiceback-quote">
                🗣️ <em>"${res.pidgin_summary}"</em>
            </div>
            <button id="btn-confirm-post" class="btn-primary" style="background: ${typeColor};">
                ✅ Confirm &amp; Post to Live Ledger
            </button>
        </div>
    `;

    document.getElementById("btn-confirm-post").addEventListener("click", confirmAndPostLedger);
}

// Confirm & Post to Live Ledger
function confirmAndPostLedger() {
    if (!state.pendingExtraction) return;

    const res = state.pendingExtraction;

    // 1. Add to Ledger
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

    // 2. If Debt Created, Add to Customer Debts
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

    // 3. Increment KudiScore for proactive bookkeeping
    state.kudiscore = Math.min(850, state.kudiscore + 4);

    // 4. Reset pending state & refresh UI
    state.pendingExtraction = null;
    elements.extractedCardContainer.innerHTML = "";
    renderAll();
    showToast("🎉 Transaction posted! Ledger & KudiScore updated.");
}

// Calculate Metrics & Render All Views
function renderAll() {
    // 1. Calculate KPI Totals
    const totalSales = state.ledger
        .filter(t => t.type.includes("Sale"))
        .reduce((sum, t) => sum + t.total, 0);

    const cashCollected = state.ledger.reduce((sum, t) => sum + t.paid, 0);
    const outstandingDebt = state.debts.reduce((sum, d) => sum + d.amount, 0);

    elements.totalSales.textContent = `₦${totalSales.toLocaleString()}`;
    elements.cashCollected.textContent = `₦${cashCollected.toLocaleString()}`;
    elements.outstandingDebt.textContent = `₦${outstandingDebt.toLocaleString()}`;

    // 2. Render Ledger Table
    elements.ledgerTableBody.innerHTML = state.ledger.map(t => `
        <tr>
            <td style="color: var(--slate-500); font-size: 0.82rem;">${t.time}</td>
            <td><strong>${t.party}</strong></td>
            <td><span class="badge-pill" style="background: ${t.debt > 0 ? '#FEF3C7' : '#DCFCE7'}; color: ${t.debt > 0 ? '#D97706' : '#15803D'};">${t.type}</span></td>
            <td>${t.items}</td>
            <td class="money"><strong>₦${t.total.toLocaleString()}</strong></td>
            <td class="money" style="color: var(--primary);">₦${t.paid.toLocaleString()}</td>
            <td class="money" style="color: var(--warning);">₦${t.debt.toLocaleString()}</td>
            <td><span style="font-size: 0.8rem; font-weight: 600; color: ${t.status === 'Paid' ? '#16A34A' : '#D97706'};">● ${t.status}</span></td>
        </tr>
    `).join("");

    // 3. Render Debt List with WhatsApp Links
    elements.debtListContainer.innerHTML = state.debts.map(d => {
        const rawPhone = d.phone.replace(/[^0-9]/g, "");
        const message = `Good day ${d.customer}, this is Mama Ngozi from Balogun Market. Trust business is moving well! Just a friendly reminder of your balance of ₦${d.amount.toLocaleString()} for the ${d.item}, due on ${d.due_date}. Thank you so much!`;
        const whatsappUrl = `https://wa.me/${rawPhone}?text=${encodeURIComponent(message)}`;

        return `
            <div class="debt-item-card">
                <div>
                    <div class="debt-customer">
                        ${d.customer}
                        <span class="${d.isOverdue ? 'badge-overdue' : 'badge-pending'}">
                            ${d.days_left}
                        </span>
                    </div>
                    <div class="debt-meta">
                        Owes: <strong style="color: var(--slate-900);">₦${d.amount.toLocaleString()}</strong> · Items: ${d.item} · Due: ${d.due_date}
                    </div>
                </div>
                <div>
                    <a href="${whatsappUrl}" target="_blank" class="btn-whatsapp">
                        💬 Send WhatsApp Reminder
                    </a>
                </div>
            </div>
        `;
    }).join("");

    // 4. Update KudiScore Gauge
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
    toast.className = "toast";
    toast.innerHTML = `<span>⚡</span> <span>${message}</span>`;
    elements.toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "0";
        setTimeout(() => toast.remove(), 300);
    }, 3200);
}
