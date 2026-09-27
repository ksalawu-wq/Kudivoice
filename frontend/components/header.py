import streamlit as st

def render_header(merchant_name="Mama Ngozi Provisions", location="Balogun Market, Lagos"):
    """Renders the top branding and status banner for the merchant app."""
    st.markdown(f"""
    <div class="kudi-header-banner">
        <div>
            <div class="kudi-brand-title">
                <span>🎙️ KudiVoice AI</span>
                <span class="kudi-badge badge-nvidia">⚡ NVIDIA AI Active</span>
            </div>
            <p style="margin: 0.35rem 0 0 0; font-size: 0.95rem; opacity: 0.92;">
                Voice-to-Ledger &amp; Micro-Credit Profiler for African Merchants
            </p>
        </div>
        <div style="text-align: right; background: rgba(0,0,0,0.18); padding: 0.6rem 1rem; border-radius: 10px; border: 1px solid rgba(255,255,255,0.15);">
            <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; opacity: 0.8;">Active Merchant</div>
            <div style="font-weight: 700; font-size: 0.95rem;">{merchant_name}</div>
            <div style="font-size: 0.78rem; opacity: 0.85;">📍 {location}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
