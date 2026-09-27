"""
KudiVoice AI - Main Streamlit Application
Frontend isolated in frontend/ directory for clean modular team collaboration.
"""

import os
import sys
import streamlit as st

# Ensure project root is in sys.path so modules can be imported cleanly
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from frontend.presets import SCENARIOS, INITIAL_LEDGER, INITIAL_DEBTS
from frontend.components.header import render_header
from frontend.components.voice_dock import render_voice_dock
from frontend.components.ledger_view import render_ledger_view
from frontend.components.credit_card import render_credit_card

# 1. Page Configuration
st.set_page_config(
    page_title="KudiVoice AI · Voice-to-Ledger for Africa",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2. Inject Custom African FinTech CSS
css_path = os.path.join(os.path.dirname(__file__), "styles", "theme.css")
if os.path.exists(css_path):
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# 3. Session State Initialization
if "ledger" not in st.session_state:
    st.session_state["ledger"] = list(INITIAL_LEDGER)

if "debts" not in st.session_state:
    st.session_state["debts"] = list(INITIAL_DEBTS)

if "kudiscore" not in st.session_state:
    st.session_state["kudiscore"] = 742

if "extracted_result" not in st.session_state:
    st.session_state["extracted_result"] = None

# 4. Render Brand Header
render_header(merchant_name="Mama Ngozi Provisions", location="Balogun Market, Lagos")

# 5. Main 2-Column Dashboard Layout
col_left, col_right = st.columns([1.1, 1.3], gap="large")

with col_left:
    # Voice & Scenario Input Dock
    process_clicked, transcript, active_scenario_key = render_voice_dock()

    # Trigger extraction logic when button clicked
    if process_clicked:
        if active_scenario_key and active_scenario_key in SCENARIOS:
            extracted = SCENARIOS[active_scenario_key]["extracted"]
        else:
            extracted = SCENARIOS["mama_chidi"]["extracted"]
            
        st.session_state["extracted_result"] = extracted
        st.toast(f"⚡ Extracted via {extracted['engine']}", icon="✅")

    # Extracted Transaction Review Card
    if st.session_state["extracted_result"]:
        res = st.session_state["extracted_result"]
        st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)
        st.markdown("### 📝 Extracted Transaction Card")
        
        type_color = "#00875A" if res["transaction_type"] == "SALE_CASH" else ("#D97706" if res["transaction_type"] == "SALE_WITH_CREDIT" else "#2563EB")
        
        with st.container():
            st.markdown(f"""
            <div style="background: white; border: 2px solid {type_color}; border-radius: 12px; padding: 1.25rem; margin-bottom: 0.75rem;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                    <span style="background: {type_color}; color: white; padding: 0.2rem 0.6rem; border-radius: 6px; font-weight: 700; font-size: 0.8rem;">
                        {res['transaction_type']}
                    </span>
                    <span style="font-size: 0.8rem; color: #76B900; font-weight: 700;">
                        ⚡ {res['engine']} · {int(res['confidence']*100)}% Confidence
                    </span>
                </div>
                <div style="font-size: 1.2rem; font-weight: 800; color: #0F172A;">
                    {res['party_name']}
                </div>
                <div style="font-size: 0.9rem; color: #475569; margin: 0.4rem 0;">
                    <strong>Items:</strong> {res['items'][0]['name']} (x{res['items'][0]['qty']})
                </div>
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); background: #F8FAFC; padding: 0.75rem; border-radius: 8px; margin: 0.5rem 0;">
                    <div><small style="color: #64748B;">Total Amount</small><br/><strong>₦{res['total_amount']:,.0f}</strong></div>
                    <div><small style="color: #64748B;">Cash Collected</small><br/><strong style="color: #00875A;">₦{res['amount_paid']:,.0f}</strong></div>
                    <div><small style="color: #64748B;">Debt Created</small><br/><strong style="color: #D97706;">₦{res['debt_amount']:,.0f}</strong></div>
                </div>
                <div style="background: #ECFDF5; border-left: 3px solid #00875A; padding: 0.5rem 0.75rem; border-radius: 4px; font-size: 0.85rem; color: #065F46; margin: 0.5rem 0;">
                    🗣️ <em>"{res['pidgin_summary']}"</em>
                </div>
            </div>
            """, unsafe_allow_html=True)

            if st.button("✅ Confirm & Post to Live Ledger", type="primary", use_container_width=True):
                # Add to ledger
                new_entry = {
                    "time": "Just now",
                    "party": res["party_name"],
                    "type": "Sale (Credit)" if res["debt_amount"] > 0 else ("Sale (Cash)" if res["transaction_type"] == "SALE_CASH" else "Expense"),
                    "items": f"{res['items'][0]['qty']}x {res['items'][0]['name']}",
                    "total": f"₦{res['total_amount']:,.0f}",
                    "paid": f"₦{res['amount_paid']:,.0f}",
                    "debt": f"₦{res['debt_amount']:,.0f}",
                    "status": "Partial Debt" if res["debt_amount"] > 0 else "Paid"
                }
                st.session_state["ledger"].insert(0, new_entry)

                # If customer debt was created, add to active debts
                if res["debt_amount"] > 0:
                    new_debt = {
                        "id": len(st.session_state["debts"]) + 1,
                        "customer": res["party_name"],
                        "phone": res["party_phone"],
                        "amount": res["debt_amount"],
                        "formatted_amount": f"₦{res['debt_amount']:,.0f}",
                        "item": res["items"][0]["name"],
                        "due_date": res["due_date"],
                        "days_left": "Due Friday",
                        "status": "Pending"
                    }
                    st.session_state["debts"].insert(0, new_debt)

                # Increment KudiScore for proactive bookkeeping
                st.session_state["kudiscore"] = min(850, st.session_state["kudiscore"] + 3)
                st.session_state["extracted_result"] = None
                st.success("🎉 Transaction posted! Ledger, Debt Register, and KudiScore updated.", icon="✅")
                st.rerun()

    # Credit Health Card
    st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
    render_credit_card(score=st.session_state["kudiscore"])

with col_right:
    # Live Financial Ledger & Customer Debts with WhatsApp
    render_ledger_view(st.session_state["ledger"], st.session_state["debts"])
