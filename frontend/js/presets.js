/**
 * KudiVoice AI - Nigerian Market Scenario Presets & Mock Data
 * Realistic Pidgin test data for rapid UI testing and judging demos.
 */

const SCENARIOS = {
    mama_chidi: {
        id: "scenario_1",
        label: "🌾 Mama Chidi (Rice + Debt)",
        badge: "Credit Sale",
        raw_pidgin: "I just sell three bags of mama gold rice to Mama Chidi for seventy-five thousand naira. She pay fifty thousand cash, she talk say she go pay the remaining twenty-five thousand balance next week Friday.",
        extracted: {
            transaction_type: "SALE_WITH_CREDIT",
            party_name: "Mama Chidi",
            party_phone: "+2348031234567",
            items: [
                { name: "Mama Gold Rice (50kg Bag)", qty: 3, unit_price: 25000, total: 75000 }
            ],
            total_amount: 75000,
            amount_paid: 50000,
            debt_amount: 25000,
            due_date: "Next Friday (02 Oct 2026)",
            pidgin_summary: "I don enter am: Mama Chidi pay ₦50,000 cash for 3 bags of rice. Balance na ₦25,000 due next Friday.",
            confidence: 0.98,
            engine: "NVIDIA Llama-3.3-70B NIM"
        }
    },
    baba_tunde: {
        id: "scenario_2",
        label: "⚡ Baba Tunde (Cash Sale)",
        badge: "Cash Sale",
        raw_pidgin: "Baba Tunde come buy two spark plug and one carburetor for his generator. Total money na forty-two thousand naira and he pay everything complete in cash with transfer.",
        extracted: {
            transaction_type: "SALE_CASH",
            party_name: "Baba Tunde",
            party_phone: "+2348029876543",
            items: [
                { name: "Generator Spark Plug", qty: 2, unit_price: 6000, total: 12000 },
                { name: "Carburetor Assy", qty: 1, unit_price: 30000, total: 30000 }
            ],
            total_amount: 42000,
            amount_paid: 42000,
            debt_amount: 0,
            due_date: "Paid in Full",
            pidgin_summary: "Payment complete! ₦42,000 cash entered for Baba Tunde. Zero debt balance.",
            confidence: 0.99,
            engine: "NVIDIA Llama-3.3-70B NIM"
        }
    },
    offloading_expense: {
        id: "scenario_3",
        label: "🚚 Truck Offload (Expense)",
        badge: "Store Expense",
        raw_pidgin: "I pay the motor driver and boys fifteen thousand naira cash for offloading the new stock wey arrive from warehouse this morning.",
        extracted: {
            transaction_type: "EXPENSE",
            party_name: "Logistics Boys / Driver",
            party_phone: "N/A",
            items: [
                { name: "Warehouse Offloading & Labour", qty: 1, unit_price: 15000, total: 15000 }
            ],
            total_amount: 15000,
            amount_paid: 15000,
            debt_amount: 0,
            due_date: "N/A (Expense Paid)",
            pidgin_summary: "Expense recorded: ₦15,000 cash paid for warehouse offloading.",
            confidence: 0.97,
            engine: "NVIDIA Llama-3.3-70B NIM"
        }
    },
    emeka_debt: {
        id: "scenario_4",
        label: "💰 Emeka (Debt Cleared)",
        badge: "Debt Recovery",
        raw_pidgin: "Brother Emeka don bring the twenty thousand naira wey he dey owe me since last week. He pay am cash finish.",
        extracted: {
            transaction_type: "DEBT_RECOVERY",
            party_name: "Brother Emeka",
            party_phone: "+2348055554321",
            items: [
                { name: "Debt Repayment (Provisions Balance)", qty: 1, unit_price: 20000, total: 20000 }
            ],
            total_amount: 20000,
            amount_paid: 20000,
            debt_amount: -20000,
            due_date: "Account Settled",
            pidgin_summary: "Debt cleared! ₦20,000 credited from Brother Emeka. Account balanced.",
            confidence: 0.99,
            engine: "NVIDIA Llama-3.3-70B NIM"
        }
    }
};

const INITIAL_LEDGER = [
    {
        id: "tx-101",
        time: "08:15 AM",
        party: "Mama Chidi",
        type: "Sale (Credit)",
        typeCode: "SALE_WITH_CREDIT",
        items: "3x Mama Gold Rice",
        total: 75000,
        paid: 50000,
        debt: 25000,
        status: "Partial Debt"
    },
    {
        id: "tx-102",
        time: "09:30 AM",
        party: "Baba Tunde",
        type: "Sale (Cash)",
        typeCode: "SALE_CASH",
        items: "2x Spark Plug, 1x Carburetor",
        total: 42000,
        paid: 42000,
        debt: 0,
        status: "Paid"
    },
    {
        id: "tx-103",
        time: "10:10 AM",
        party: "Logistics Offloading",
        type: "Expense",
        typeCode: "EXPENSE",
        items: "Warehouse Labour",
        total: 15000,
        paid: 15000,
        debt: 0,
        status: "Paid"
    }
];

const INITIAL_DEBTS = [
    {
        id: "debt-1",
        customer: "Mama Chidi",
        phone: "+2348031234567",
        amount: 25000,
        item: "3 bags of Mama Gold Rice",
        due_date: "02 Oct 2026",
        days_left: "5 days left",
        isOverdue: false
    },
    {
        id: "debt-2",
        customer: "Brother Emeka",
        phone: "+2348055554321",
        amount: 20000,
        item: "Provisions & Milk Cartons",
        due_date: "25 Sep 2026",
        days_left: "2 days OVERDUE",
        isOverdue: true
    },
    {
        id: "debt-3",
        customer: "Iya Basira",
        phone: "+2348077778899",
        amount: 12500,
        item: "Cooking Oil 5L",
        due_date: "05 Oct 2026",
        days_left: "8 days left",
        isOverdue: false
    }
];
