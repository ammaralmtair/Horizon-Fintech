"""
Streamlit Frontend for Horizon Fintech MVP.
Version 3.0 - With Auth, Virtual Card, Full Invoice System & Persistent Data
"""
import streamlit as st
import requests
import pandas as pd

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
API_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="Horizon | أفق",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🌐"
)

# ─────────────────────────────────────────────
# SESSION STATE INIT
# ─────────────────────────────────────────────
for key, default in [
    ("token", None),
    ("username", None),
    ("lang", "ar"),
    ("page", "dashboard"),
    ("last_msg", ("", "")),   # (type, text)  type = success|error|warning
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ─────────────────────────────────────────────
# TRANSLATIONS
# ─────────────────────────────────────────────
T = {
    "ar": {
        "login": "تسجيل الدخول", "register": "إنشاء حساب",
        "logout": "تسجيل الخروج", "username": "اسم المستخدم",
        "password": "كلمة المرور", "login_btn": "دخول",
        "register_btn": "إنشاء حساب", "welcome": "مرحباً",
        "dashboard": "لوحة التحكم", "swap": "التحويل",
        "invoices": "الفواتير", "card": "البطاقة الافتراضية",
        "history": "السجل", "sms": "SMS",
        "wallet": "محفظتي", "total": "الرصيد الإجمالي (USD)",
        "usd": "💵 دولار", "gold": "🌟 ذهب", "btc": "🪙 بيتكوين",
        "eq": "يعادل", "from_asset": "من", "to_asset": "إلى",
        "amount": "المبلغ", "execute": "تنفيذ التحويل",
        "success": "تمت العملية بنجاح", "fee_est": "رسوم متوقعة (0.1%)",
        "inv_recipient": "اسم العميل / المستلم",
        "inv_amount": "مبلغ الفاتورة", "inv_currency": "عملة الدفع",
        "inv_receive": "أصل الاستلام المفضل",
        "create_inv": "إنشاء الفاتورة",
        "inv_list": "فواتيري", "pay_inv": "دفع فاتورة",
        "inv_id_label": "رقم الفاتورة",
        "card_holder": "اسم حامل البطاقة",
        "issue_card": "إصدار بطاقة افتراضية",
        "card_number": "رقم البطاقة", "expiry": "تاريخ الانتهاء",
        "cvv": "CVV", "card_status": "حالة البطاقة",
        "freeze": "تجميد / تفعيل البطاقة",
        "sms_label": "أمر الرسالة", "sms_ph": "SEND 100 USD TO GOLD",
        "sms_exec": "تنفيذ", "sms_hint": "الصيغة: SEND <مبلغ> <من> TO <إلى>",
        "charts": "📈 أسعار الأصول",
        "advisor": "🤖 المستشار المالي",
        "no_tx": "لا توجد معاملات بعد.", "oz": "أونصة",
        "lang_label": "Language / اللغة",
        "login_err": "اسم المستخدم أو كلمة المرور غير صحيحة.",
        "fill_all": "يرجى ملء جميع الحقول.",
        "pay_success": "تم دفع الفاتورة بنجاح!",
        "nav": "التنقل",
    },
    "en": {
        "login": "Login", "register": "Register",
        "logout": "Logout", "username": "Username",
        "password": "Password", "login_btn": "Login",
        "register_btn": "Create Account", "welcome": "Welcome",
        "dashboard": "Dashboard", "swap": "Swap",
        "invoices": "Invoices", "card": "Virtual Card",
        "history": "History", "sms": "SMS",
        "wallet": "My Wallet", "total": "Total Balance (USD)",
        "usd": "💵 USD", "gold": "🌟 Gold", "btc": "🪙 Bitcoin",
        "eq": "Equivalent to", "from_asset": "From", "to_asset": "To",
        "amount": "Amount", "execute": "Execute Swap",
        "success": "Operation successful", "fee_est": "Est. fee (0.1%)",
        "inv_recipient": "Client / Recipient Name",
        "inv_amount": "Invoice Amount", "inv_currency": "Payment Currency",
        "inv_receive": "Preferred Receive Asset",
        "create_inv": "Create Invoice",
        "inv_list": "My Invoices", "pay_inv": "Pay Invoice",
        "inv_id_label": "Invoice ID",
        "card_holder": "Cardholder Name",
        "issue_card": "Issue Virtual Card",
        "card_number": "Card Number", "expiry": "Expiry",
        "cvv": "CVV", "card_status": "Card Status",
        "freeze": "Freeze / Activate Card",
        "sms_label": "SMS Command", "sms_ph": "SEND 100 USD TO GOLD",
        "sms_exec": "Execute", "sms_hint": "Format: SEND <amount> <FROM> TO <TO>",
        "charts": "📈 Asset Price Charts",
        "advisor": "🤖 AI Financial Advisor",
        "no_tx": "No transactions yet.", "oz": "oz",
        "lang_label": "Language / اللغة",
        "login_err": "Invalid username or password.",
        "fill_all": "Please fill in all fields.",
        "pay_success": "Invoice paid successfully!",
        "nav": "Navigation",
    }
}

def t(key: str) -> str:
    return T[st.session_state.lang].get(key, key)

# ─────────────────────────────────────────────
# API HELPER
# ─────────────────────────────────────────────
def api(method: str, endpoint: str, json=None, token: str = None, public: bool = False):
    """Centralised API request. Injects auth header automatically."""
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif st.session_state.token and not public:
        headers["Authorization"] = f"Bearer {st.session_state.token}"
    try:
        url = f"{API_URL}/{endpoint}"
        if method == "get":
            r = requests.get(url, headers=headers, timeout=10)
        elif method == "post":
            r = requests.post(url, json=json, headers=headers, timeout=10)
        elif method == "delete":
            r = requests.delete(url, headers=headers, timeout=10)
        else:
            return None
        r.raise_for_status()
        return r
    except requests.exceptions.HTTPError as e:
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        st.session_state.last_msg = ("error", detail)
        return None
    except requests.exceptions.ConnectionError:
        st.session_state.last_msg = ("error", "⚠️ Cannot connect to backend. Is uvicorn running?")
        return None

def show_msg():
    kind, text = st.session_state.last_msg
    if text:
        if kind == "success": st.success(text)
        elif kind == "error": st.error(text)
        elif kind == "warning": st.warning(text)
        elif kind == "info": st.info(text)
        st.session_state.last_msg = ("", "")

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.image("https://i.imgur.com/M5sS4Hk.png", width=80)
    st.title("Horizon | أفق")

    lang_sel = st.radio(t("lang_label"), ["العربية", "English"],
                        index=0 if st.session_state.lang == "ar" else 1)
    st.session_state.lang = "ar" if lang_sel == "العربية" else "en"

    st.markdown("---")

    if st.session_state.token:
        st.success(f"👤 {t('welcome')}, **{st.session_state.username}**")
        st.markdown(f"### {t('nav')}")
        pages = {
            "dashboard": t("dashboard"),
            "swap":      t("swap"),
            "invoices":  t("invoices"),
            "card":      t("card"),
            "history":   t("history"),
            "sms":       t("sms"),
        }
        for pg, label in pages.items():
            if st.button(label, key=f"nav_{pg}", use_container_width=True):
                st.session_state.page = pg
                st.rerun()

        st.markdown("---")
        if st.button(f"🚪 {t('logout')}", use_container_width=True):
            api("post", "auth/logout")
            st.session_state.token    = None
            st.session_state.username = None
            st.session_state.page     = "dashboard"
            st.rerun()

# ─────────────────────────────────────────────
# AUTH PAGES  (shown when not logged in)
# ─────────────────────────────────────────────
def page_auth():
    st.title("🌐 Horizon Fintech | أفق")
    st.markdown("##### الجسر المالي الشامل — تحويل · ادخار · فواتير · بطاقة افتراضية")
    st.markdown("---")

    tab_login, tab_reg = st.tabs([t("login"), t("register")])

    with tab_login:
        st.subheader(t("login"))
        uname = st.text_input(t("username"), key="li_user")
        pwd   = st.text_input(t("password"), type="password", key="li_pwd")
        if st.button(t("login_btn"), use_container_width=True):
            if uname and pwd:
                r = api("post", "auth/login", json={"username": uname, "password": pwd}, public=True)
                if r:
                    data = r.json()
                    st.session_state.token    = data["token"]
                    st.session_state.username = data["username"]
                    st.session_state.page     = "dashboard"
                    st.rerun()
            else:
                st.warning(t("fill_all"))

    with tab_reg:
        st.subheader(t("register"))
        uname2 = st.text_input(t("username"), key="reg_user")
        pwd2   = st.text_input(t("password"), type="password", key="reg_pwd",
                               help="Minimum 6 characters / 6 أحرف على الأقل")
        if st.button(t("register_btn"), use_container_width=True):
            if uname2 and pwd2:
                r = api("post", "auth/register", json={"username": uname2, "password": pwd2}, public=True)
                if r:
                    st.success(r.json()["message"])
                    st.info("يمكنك الآن تسجيل الدخول / You can now login.")
            else:
                st.warning(t("fill_all"))

# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────
def page_dashboard():
    st.title(f"🌐 {t('dashboard')} — Horizon")
    show_msg()

    wallet_r = api("get", "wallet")
    prices_r = api("get", "prices", public=True)
    advice_r = api("get", "financial-advice")

    col_wallet, col_charts = st.columns([2, 1])

    with col_wallet:
        st.subheader(t("wallet"))
        if wallet_r and prices_r:
            balances    = wallet_r.json()["balances"]
            live_prices = prices_r.json().get("live_prices", {})
            gold_price  = live_prices.get("USD_GOLD_OZ", 2300)
            btc_price   = live_prices.get("USD_BTC", 65000)

            usd_val  = balances.get("USD", 0)
            gold_oz  = balances.get("GOLD_OZ", 0)
            btc_val  = balances.get("BTC", 0)
            gold_usd = gold_oz  * gold_price
            btc_usd  = btc_val  * btc_price
            total    = usd_val + gold_usd + btc_usd

            st.metric(t("total"), f"${total:,.2f}")
            c1, c2, c3 = st.columns(3)
            c1.info(f"**{t('usd')}**\n\n`{usd_val:,.2f} USD`")
            c2.warning(f"**{t('gold')}**\n\n`{gold_oz:,.4f} {t('oz')}`\n\n*{t('eq')}: ${gold_usd:,.2f}*")
            c3.success(f"**{t('btc')}**\n\n`{btc_val:,.6f} BTC`\n\n*{t('eq')}: ${btc_usd:,.2f}*")

        st.markdown("---")
        if advice_r:
            st.subheader(t("advisor"))
            adv      = advice_r.json()
            priority = adv.get("priority", "Low")
            text     = adv.get("advice", "")
            if priority == "High":   st.error(f"**{text}**")
            elif priority == "Medium": st.warning(f"**{text}**")
            else:                    st.info(f"**{text}**")

    with col_charts:
        st.subheader(t("charts"))
        if prices_r:
            history = prices_r.json().get("history", {})
            if history.get("GOLD_OZ"):
                st.markdown("**🌟 Gold (USD/oz)**")
                st.line_chart(pd.DataFrame(history["GOLD_OZ"], columns=["Price"]))
            if history.get("BTC"):
                st.markdown("**🪙 Bitcoin (USD)**")
                st.line_chart(pd.DataFrame(history["BTC"], columns=["Price"]))

# ─────────────────────────────────────────────
# SWAP PAGE
# ─────────────────────────────────────────────
def page_swap():
    st.title(f"🔄 {t('swap')}")
    show_msg()

    assets = ["USD", "GOLD_OZ", "BTC"]
    c1, arrow, c2 = st.columns([2, 0.5, 2])
    with c1:
        from_asset = st.selectbox(t("from_asset"), assets, key="sw_from")
        amount     = st.number_input(t("amount"), min_value=0.0, step=0.01, format="%.4f")
        if amount > 0:
            st.caption(f"🏷️ {t('fee_est')}: `{amount * 0.001:.6f} {from_asset}`")
    with arrow:
        st.markdown("<br><br><br><h2 style='text-align:center'>→</h2>", unsafe_allow_html=True)
    with c2:
        to_asset = st.selectbox(t("to_asset"), [a for a in assets if a != from_asset], key="sw_to")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button(t("execute"), use_container_width=True):
            if amount > 0:
                r = api("post", "swap", json={"from_asset": from_asset, "to_asset": to_asset, "amount": amount})
                if r:
                    st.session_state.last_msg = ("success", t("success") + " ✅")
                    st.rerun()
            else:
                st.warning(t("fill_all"))

# ─────────────────────────────────────────────
# INVOICE PAGE
# ─────────────────────────────────────────────
def page_invoices():
    st.title(f"🧾 {t('invoices')}")
    show_msg()

    tab_create, tab_list, tab_pay = st.tabs([t("create_inv"), t("inv_list"), t("pay_inv")])

    assets = ["USD", "GOLD_OZ", "BTC"]

    with tab_create:
        st.subheader(t("create_inv"))
        recipient  = st.text_input(t("inv_recipient"))
        inv_amount = st.number_input(t("inv_amount"), min_value=0.01, format="%.2f")
        inv_curr   = st.selectbox(t("inv_currency"), assets, key="inv_c")
        inv_recv   = st.selectbox(t("inv_receive"), assets, key="inv_r")
        if st.button(t("create_inv"), use_container_width=True):
            if recipient and inv_amount > 0:
                r = api("post", "invoice/create", json={
                    "recipient": recipient,
                    "amount": inv_amount,
                    "currency": inv_curr,
                    "preferred_receive_asset": inv_recv
                })
                if r:
                    data = r.json()
                    st.success(f"✅ Invoice **#{data['invoice_id']}** created!")
                    st.code(data["payment_link"], language="text")
                    st.json(data)
            else:
                st.warning(t("fill_all"))

    with tab_list:
        st.subheader(t("inv_list"))
        r = api("get", "my-invoices")
        if r:
            invs = r.json().get("invoices", [])
            if not invs:
                st.info("لا توجد فواتير بعد. / No invoices yet.")
            else:
                df = pd.DataFrame(invs)[["id", "recipient", "amount", "currency", "pref_asset", "status", "created_at", "paid_at"]]
                st.dataframe(df, use_container_width=True, hide_index=True)

    with tab_pay:
        st.subheader(t("pay_inv"))
        st.caption("أدخل رقم الفاتورة الذي أرسله لك صاحب الفاتورة / Enter the invoice ID shared with you.")
        inv_id = st.text_input(t("inv_id_label"), placeholder="e.g. A1B2C3D4").upper()
        if inv_id:
            r_info = api("get", f"invoice/{inv_id}", public=True)
            if r_info:
                data = r_info.json()
                st.info(
                    f"**{t('inv_recipient')}:** {data['recipient']}  |  "
                    f"**{t('inv_amount')}:** {data['amount']} {data['currency']}  |  "
                    f"**Status:** {data['status']}"
                )
                if data["status"] == "pending":
                    if st.button(f"💳 {t('pay_inv')} #{inv_id}", use_container_width=True):
                        r_pay = api("post", f"invoice/{inv_id}/pay")
                        if r_pay:
                            st.session_state.last_msg = ("success", t("pay_success"))
                            st.rerun()

# ─────────────────────────────────────────────
# VIRTUAL CARD PAGE
# ─────────────────────────────────────────────
def page_card():
    st.title(f"💳 {t('card')}")
    show_msg()

    r = api("get", "card")

    if r and r.status_code == 200:
        card = r.json()
        status_color = "🟢" if card["status"] == "active" else "🔴"

        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            border-radius: 16px;
            padding: 30px 36px;
            color: white;
            font-family: monospace;
            max-width: 440px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        ">
            <p style="font-size:1.1em; opacity:0.7; margin:0">Horizon Fintech</p>
            <h2 style="letter-spacing:4px; margin:18px 0 6px">{card['card_number']}</h2>
            <div style="display:flex; justify-content:space-between; margin-top:16px">
                <div>
                    <p style="opacity:0.6; font-size:0.75em; margin:0">CARD HOLDER</p>
                    <p style="margin:2px 0; font-size:1em">{card['holder_name']}</p>
                </div>
                <div>
                    <p style="opacity:0.6; font-size:0.75em; margin:0">EXPIRES</p>
                    <p style="margin:2px 0; font-size:1em">{card['expiry']}</p>
                </div>
                <div>
                    <p style="opacity:0.6; font-size:0.75em; margin:0">CVV</p>
                    <p style="margin:2px 0; font-size:1em">{card['cvv']}</p>
                </div>
            </div>
            <p style="margin-top:18px; opacity:0.8">🌐 Visa Virtual &nbsp;|&nbsp; {status_color} {card['status'].capitalize()}</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button(f"🔒 {t('freeze')}", use_container_width=False):
            r2 = api("delete", "card/freeze")
            if r2:
                new_status = r2.json()["status"]
                st.session_state.last_msg = ("success", f"Card is now **{new_status}**.")
                st.rerun()
    else:
        st.info("لم تصدر بطاقة افتراضية بعد. / No virtual card issued yet.")
        holder = st.text_input(t("card_holder"))
        if st.button(t("issue_card"), use_container_width=True):
            if holder:
                r2 = api("post", "card/create", json={"holder_name": holder})
                if r2:
                    st.session_state.last_msg = ("success", r2.json()["message"])
                    st.rerun()
            else:
                st.warning(t("fill_all"))

# ─────────────────────────────────────────────
# HISTORY PAGE
# ─────────────────────────────────────────────
def page_history():
    st.title(f"📋 {t('history')}")
    show_msg()

    r = api("get", "transactions")
    if r:
        txs = r.json().get("transactions", [])
        if not txs:
            st.info(t("no_tx"))
        else:
            df = pd.DataFrame(txs)
            st.dataframe(df, use_container_width=True, hide_index=True,
                         column_config={
                             "amount":           st.column_config.NumberColumn(format="%.6f"),
                             "converted_amount": st.column_config.NumberColumn(format="%.6f"),
                             "fee":              st.column_config.NumberColumn(format="%.6f"),
                         })
            st.caption("🔒 جميع الرسوم تُخصم من المبلغ المُستَلَم. / All fees deducted from received amount.")

# ─────────────────────────────────────────────
# SMS PAGE
# ─────────────────────────────────────────────
def page_sms():
    st.title(f"📱 {t('sms')}")
    show_msg()
    st.caption(t("sms_hint"))

    cmd = st.text_input(t("sms_label"), placeholder=t("sms_ph"))
    if st.button(t("sms_exec"), use_container_width=False):
        if cmd:
            encrypted = f"[ENCRYPTED] {cmd} [ENCRYPTED]"
            st.caption(f"Sending: `{encrypted}`")
            r = api("post", "simulate-sms-transfer", json={"message": encrypted})
            if r:
                st.session_state.last_msg = ("success", t("success") + " ✅")
                st.rerun()
        else:
            st.warning(t("fill_all"))

# ─────────────────────────────────────────────
# ROUTER
# ─────────────────────────────────────────────
if not st.session_state.token:
    page_auth()
else:
    page_map = {
        "dashboard": page_dashboard,
        "swap":      page_swap,
        "invoices":  page_invoices,
        "card":      page_card,
        "history":   page_history,
        "sms":       page_sms,
    }
    page_map.get(st.session_state.page, page_dashboard)()
