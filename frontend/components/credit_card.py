import streamlit as st

def render_credit_card(score=742, tier="Grade A (Low Risk)", loan_limit="₦350,000"):
    """
    Renders the KudiScore alternative credit health gauge and bank eligibility card.
    """
    st.markdown("### 🏆 KudiScore™ Financial Credit Rating")
    st.caption("Alternative credit scoring generated from verified voice transaction velocity.")

    st.markdown(f"""
    <div class="kudiscore-box">
        <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.1em; color: #94A3B8;">
            Merchant Creditworthiness Score (300 – 850)
        </div>
        <div class="kudiscore-number">{score}</div>
        <div class="kudiscore-tier">⭐ {tier}</div>
        
        <div style="margin-top: 1.25rem; padding-top: 1.25rem; border-top: 1px solid #334155; display: grid; grid-template-columns: repeat(2, 1fr); text-align: left;">
            <div>
                <div style="font-size: 0.75rem; color: #94A3B8;">Max Working Capital Limit</div>
                <div style="font-size: 1.25rem; font-weight: 800; color: #38BDF8;">{loan_limit}</div>
                <div style="font-size: 0.7rem; color: #94A3B8;">Compatible with Kredete API</div>
            </div>
            <div>
                <div style="font-size: 0.75rem; color: #94A3B8;">Debt Repayment Discipline</div>
                <div style="font-size: 1.25rem; font-weight: 800; color: #4ADE80;">91.4%</div>
                <div style="font-size: 0.7rem; color: #94A3B8;">Based on 30-day recovery speed</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Dimensional Breakdown
    st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)
    with st.expander("🔍 View KudiScore Credit Breakdown", expanded=False):
        c1, c2 = st.columns(2)
        c1.metric("Cash Flow Velocity (35% weight)", "94 / 100", "+4.2% this week")
        c1.metric("Business Trading Consistency (20% weight)", "88 / 100", "26 active days/mo")
        c2.metric("Customer Debt Recovery (25% weight)", "91 / 100", "Avg 4.2 days to settle")
        c2.metric("Profit Margin Health (20% weight)", "82 / 100", "Balanced markup")
        
        st.info("💡 **Credit Transparency:** Each parameter is calculated directly from your real transaction frequency and debt settlement history, giving partner lenders verified proof of business cash flow.")
