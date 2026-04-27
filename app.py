"""
Streamlit Frontend for Horizon Fintech MVP.
"""
import streamlit as st
import requests
import pandas as pd
import math

# --- Configuration ---
API_URL = "http://127.0.0.1:8000"  # URL of the FastAPI backend

# --- Page Setup ---
st.set_page_config(page_title="Horizon Fintech", layout="wide", initial_sidebar_state="expanded")

# --- Helper Functions ---
def get_wallet_data():
    """Fetches wallet data from the backend."""
    try:
        response = requests.get(f"{API_URL}/wallet")
        response.raise_for_status()
        return response.json().get("balances", {})
    except requests.exceptions.RequestException as e:
        st.error(f"لا يمكن الاتصال بالخادم: {e}")
        return None

def display_wallet(balances):
    """Displays wallet balances in a visually appealing way."""
    if not balances:
        st.warning("لم يتم العثور على بيانات المحفظة.")
        return

    st.subheader("💳 محفظتك الافتراضية")
    
    # Exchange rates for display
    gold_price_usd = 2300
    btc_price_usd = 65000
    
    usd_balance = balances.get("USD", 0)
    gold_balance_oz = balances.get("GOLD_OZ", 0)
    btc_balance = balances.get("BTC", 0)
    
    gold_balance_usd = gold_balance_oz * gold_price_usd
    btc_balance_usd = btc_balance * btc_price_usd
    
    total_balance_usd = usd_balance + gold_balance_usd + btc_balance_usd

    st.metric(label="💰 الرصيد الإجمالي (بالدولار الأمريكي)", value=f"${total_balance_usd:,.2f}")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.info(f"💵 **الدولار الأمريكي**\n\n`{usd_balance:,.2f} USD`")
    with col2:
        st.warning(f"🌟 **الذهب الرقمي**\n\n`{gold_balance_oz:,.4f} أونصة`\n\n*ما يعادل ${gold_balance_usd:,.2f}*")
    with col3:
        st.success(f"🪙 **البيتكوين**\n\n`{btc_balance:,.6f} BTC`\n\n*ما يعادل ${btc_balance_usd:,.2f}*")


# --- Main Application ---
st.title("Horizon | أفق")
st.markdown("منصة Fintech متكاملة للتحويل بين العملات، الذهب الرقمي، والعملات المشفرة.")
st.markdown("---")

# --- Display Wallet ---
wallet_data = get_wallet_data()
if wallet_data:
    display_wallet(wallet_data)
    st.markdown("---")

# --- Swap Engine ---
st.header("🔄 محرك التحويل (Swap Engine)")
assets = ["USD", "GOLD_OZ", "BTC"]
col_swap1, col_swap2, col_swap3 = st.columns([2, 1, 2])

with col_swap1:
    from_asset = st.selectbox("من أصل:", options=assets, key="from_asset")
    amount = st.number_input("المبلغ:", min_value=0.01, step=0.01, format="%.2f")

with col_swap2:
    st.markdown("<br/><br/><br/>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center;'>→</h1>", unsafe_allow_html=True)

with col_swap3:
    to_asset = st.selectbox("إلى أصل:", options=[a for a in assets if a != from_asset], key="to_asset")
    if st.button("تنفيذ التحويل", use_container_width=True):
        if amount > 0:
            payload = {"from_asset": from_asset, "to_asset": to_asset, "amount": amount}
            try:
                response = requests.post(f"{API_URL}/swap", json=payload)
                if response.status_code == 200:
                    st.success("تم التحويل بنجاح!")
                    st.rerun()
                else:
                    st.error(f"خطأ: {response.json().get('detail')}")
            except requests.exceptions.RequestException as e:
                st.error(f"فشل الاتصال بالخادم: {e}")
        else:
            st.warning("الرجاء إدخال مبلغ صحيح.")

st.markdown("---")

# --- Other Features in Sidebar ---
with st.sidebar:
    st.header("✨ ميزات إضافية")

    # --- Freelancer Invoicing ---
    with st.expander("🧾 نظام الفواتير للمستقلين"):
        st.subheader("إنشاء فاتورة جديدة")
        recipient = st.text_input("اسم المستلم:")
        invoice_amount = st.number_input("مبلغ الفاتورة:", min_value=0.01, format="%.2f", key="invoice_amount")
        invoice_currency = st.selectbox("عملة الفاتورة:", options=["USD", "GOLD_OZ", "BTC"], key="invoice_currency")
        if st.button("إنشاء رابط الفاتورة", key="invoice_btn"):
            if recipient and invoice_amount > 0:
                st.success("تم إنشاء الفاتورة بنجاح!")
                st.code(f"https://horizon.finance/pay?to={recipient}&amount={invoice_amount}&currency={invoice_currency}", language=None)
            else:
                st.warning("الرجاء ملء جميع الحقول.")

    # --- SMS Simulation ---
    with st.expander("📱 محاكاة التحويل عبر SMS"):
        st.subheader("أرسل أمر تحويل")
        sms_command = st.text_input("رسالة SMS:", placeholder="SEND 100 USD TO GOLD")
        if st.button("تنفيذ الأمر", key="sms_btn"):
            if sms_command:
                payload = {"message": sms_command}
                try:
                    response = requests.post(f"{API_URL}/simulate-sms-transfer", json=payload)
                    if response.status_code == 200:
                        st.success("تم تنفيذ الأمر بنجاح!")
                        st.rerun()
                    else:
                        st.error(f"خطأ: {response.json().get('detail')}")
                except requests.exceptions.RequestException as e:
                    st.error(f"فشل الاتصال بالخادم: {e}")
            else:
                st.warning("الرجاء إدخال أمر صحيح.")
    
    # --- Round-up Savings Info ---
    with st.expander("🏦 ميزة الادخار التلقائي (Round-up)"):
        st.info(
            """
            **كيف تعمل؟**
            عند إجراء أي عملية تحويل من رصيد الدولار (USD)، يقوم النظام تلقائيًا بجبر المبلغ لأقرب دولار للأعلى.
            
            الفارق البسيط الناتج عن الجبر يتم تحويله مباشرة إلى رصيد الذهب الخاص بك كشكل من أشكال الادخار.
            
            **مثال:**
            - قمت بتحويل **$50.70**.
            - النظام يجبرها إلى **$51.00**.
            - الفارق وهو **$0.30** يتم شراؤه ذهبًا وإضافته لمحفظتك.
            """
        )
