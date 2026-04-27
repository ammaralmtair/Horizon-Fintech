"""
Backend for Horizon Fintech MVP using FastAPI.
Version 3.0 - Production-Ready: SQLite Persistence, User Auth, Invoices & Virtual Cards
"""
import sqlite3
import hashlib
import secrets
import math
import datetime
import random
import uuid
from typing import Optional, Dict, List

from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel

app = FastAPI(
    title="Horizon Fintech API",
    description="Production-grade API with SQLite persistence, user auth, invoices, and virtual cards.",
    version="3.0.0"
)

# ─────────────────────────────────────────────
# DATABASE LAYER
# ─────────────────────────────────────────────
DB_PATH = "horizon.db"

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Create all tables on first startup if they don't exist."""
    conn = get_db()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    UNIQUE NOT NULL,
            password_hash TEXT    NOT NULL,
            created_at    TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            token   TEXT    PRIMARY KEY,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS wallets (
            user_id INTEGER PRIMARY KEY,
            usd     REAL    DEFAULT 10000.0,
            gold_oz REAL    DEFAULT 5.0,
            btc     REAL    DEFAULT 0.2,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id          INTEGER NOT NULL,
            timestamp        TEXT    NOT NULL,
            from_asset       TEXT    NOT NULL,
            to_asset         TEXT    NOT NULL,
            amount           REAL    NOT NULL,
            converted_amount REAL    NOT NULL,
            fee              REAL    NOT NULL,
            status           TEXT    NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS invoices (
            id           TEXT    PRIMARY KEY,
            user_id      INTEGER NOT NULL,
            recipient    TEXT    NOT NULL,
            amount       REAL    NOT NULL,
            currency     TEXT    NOT NULL,
            pref_asset   TEXT    NOT NULL,
            status       TEXT    DEFAULT 'pending',
            created_at   TEXT    NOT NULL,
            paid_at      TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS virtual_cards (
            id          TEXT    PRIMARY KEY,
            user_id     INTEGER UNIQUE NOT NULL,
            card_number TEXT    NOT NULL,
            holder_name TEXT    NOT NULL,
            expiry      TEXT    NOT NULL,
            cvv         TEXT    NOT NULL,
            status      TEXT    DEFAULT 'active',
            created_at  TEXT    NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    conn.commit()
    conn.close()

init_db()

# ─────────────────────────────────────────────
# PRICE ENGINE
# ─────────────────────────────────────────────
FEE_PERCENTAGE = 0.001  # 0.1% per transaction

# ── Fixed Hackathon Rates (Sandbox 2026) ──────────────────────
HACKATHON_RATES = {
    "USD_GOLD_OZ": 2000.0,    # 1 USD = 0.0005 oz  →  1 oz = $2,000
    "USD_BTC":     66666.67,  # 1 USD = 0.000015 BTC → 1 BTC ≈ $66,667
    "USD_SAR":     3.75,      # 1 USD = 3.75 SAR
}

price_history: Dict[str, List[float]] = {
    "GOLD_OZ": [2000.0] * 10,
    "BTC":     [66666.67] * 10
}

def get_live_prices() -> Dict[str, float]:
    """Return fixed hackathon sandbox rates. No external API needed."""
    return {"USD_GOLD_OZ": HACKATHON_RATES["USD_GOLD_OZ"], "USD_BTC": HACKATHON_RATES["USD_BTC"]}

# ─────────────────────────────────────────────
# AUTH HELPERS
# ─────────────────────────────────────────────
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def get_current_user(authorization: str = Header(...)) -> int:
    """Dependency — validates Bearer token and returns user_id."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header format.")
    token = authorization.split(" ", 1)[1]
    conn  = get_db()
    row   = conn.execute("SELECT user_id FROM sessions WHERE token = ?", (token,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid or expired session token. Please login again.")
    return int(row["user_id"])

def check_amount(amount: float):
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be a positive number.")

def load_wallet(user_id: int, conn: sqlite3.Connection) -> Dict[str, float]:
    row = conn.execute("SELECT usd, gold_oz, btc FROM wallets WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Wallet not found.")
    return {"USD": float(row["usd"]), "GOLD_OZ": float(row["gold_oz"]), "BTC": float(row["btc"])}

def save_wallet(user_id: int, balances: Dict[str, float], conn: sqlite3.Connection):
    conn.execute(
        "UPDATE wallets SET usd = ?, gold_oz = ?, btc = ? WHERE user_id = ?",
        (balances["USD"], balances["GOLD_OZ"], balances["BTC"], user_id)
    )

def generate_digital_signature(data: str) -> str:
    """Simulate a digital signature for transaction verification (SHA-256 simulation)."""
    timestamp = datetime.datetime.now().isoformat()
    payload   = f"{data}|{timestamp}|HORIZON_SANDBOX_KEY_2026"
    return "SIG-" + hashlib.sha256(payload.encode()).hexdigest()[:16].upper()

# ─────────────────────────────────────────────
# PYDANTIC MODELS
# ─────────────────────────────────────────────
class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class SwapRequest(BaseModel):
    from_asset: str
    to_asset:   str
    amount:     float

class SmsRequest(BaseModel):
    message: str

class InvoiceCreateRequest(BaseModel):
    recipient:            str
    amount:               float
    currency:             str
    preferred_receive_asset: str  # USD, GOLD_OZ, or BTC

class CardCreateRequest(BaseModel):
    holder_name: str

# ─────────────────────────────────────────────
# AUTH ENDPOINTS
# ─────────────────────────────────────────────
@app.post("/auth/register", summary="Register a New User")
async def register(req: RegisterRequest):
    if len(req.username.strip()) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters.")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    conn = get_db()
    try:
        now = datetime.datetime.now().isoformat()
        conn.execute(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
            (req.username.strip(), hash_password(req.password), now)
        )
        conn.commit()
        user_id = conn.execute(
            "SELECT id FROM users WHERE username = ?", (req.username.strip(),)
        ).fetchone()["id"]
        conn.execute("INSERT INTO wallets (user_id) VALUES (?)", (user_id,))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=409, detail="Username already exists.")
    conn.close()
    return {"message": "Registration successful. You can now login."}

@app.post("/auth/login", summary="Login and Receive a Session Token")
async def login(req: LoginRequest):
    conn = get_db()
    row  = conn.execute(
        "SELECT id, password_hash FROM users WHERE username = ?", (req.username.strip(),)
    ).fetchone()

    if not row or row["password_hash"] != hash_password(req.password):
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    token = secrets.token_hex(32)
    conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, row["id"]))
    conn.commit()
    conn.close()
    return {"token": token, "username": req.username.strip()}

@app.post("/auth/logout", summary="Logout and Invalidate Token")
async def logout(authorization: str = Header(...), user_id: int = Depends(get_current_user)):
    token = authorization.split(" ", 1)[1]
    conn  = get_db()
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()
    return {"message": "Logged out successfully."}

# ─────────────────────────────────────────────
# WALLET & PRICES
# ─────────────────────────────────────────────
@app.get("/wallet", summary="Get Current User Wallet Balances")
async def get_wallet(user_id: int = Depends(get_current_user)):
    conn     = get_db()
    balances = load_wallet(user_id, conn)
    conn.close()
    return {"balances": balances}

@app.get("/prices", summary="Get Live Asset Prices and Chart History")
async def get_prices():
    live_prices = get_live_prices()
    return {"live_prices": live_prices, "history": price_history}

# ─────────────────────────────────────────────
# SWAP ENGINE
# ─────────────────────────────────────────────
@app.post("/swap", summary="Swap Between Assets with Real-Time Pricing")
async def swap_assets(request: SwapRequest, user_id: int = Depends(get_current_user)):
    check_amount(request.amount)
    from_asset = request.from_asset.upper()
    to_asset   = request.to_asset.upper()
    amount     = request.amount
    valid      = {"USD", "GOLD_OZ", "BTC"}

    if from_asset not in valid or to_asset not in valid:
        raise HTTPException(status_code=400, detail="Invalid asset. Accepted: USD, GOLD_OZ, BTC.")
    if from_asset == to_asset:
        raise HTTPException(status_code=400, detail="Source and destination assets must differ.")

    conn     = get_db()
    balances = load_wallet(user_id, conn)

    if balances[from_asset] < amount:
        conn.close()
        raise HTTPException(status_code=400, detail=f"Insufficient {from_asset} balance.")

    RATES = get_live_prices()

    # Normalise everything through USD
    if from_asset == "USD":       usd_value = amount
    elif from_asset == "GOLD_OZ": usd_value = amount * RATES["USD_GOLD_OZ"]
    else:                         usd_value = amount * RATES["USD_BTC"]

    if to_asset == "USD":         converted = usd_value
    elif to_asset == "GOLD_OZ":   converted = usd_value / RATES["USD_GOLD_OZ"]
    else:                         converted = usd_value / RATES["USD_BTC"]

    fee        = converted * FEE_PERCENTAGE
    net_amount = converted - fee

    # Apply swap
    balances[from_asset] -= amount
    balances[to_asset]   += net_amount

    # Round-up auto-savings (USD → other assets only)
    roundup_gold = 0.0
    if from_asset == "USD" and amount > 1:
        diff = math.ceil(amount) - amount  # e.g. 50.70 → 0.30
        if diff > 0 and balances["USD"] >= diff:
            balances["USD"]     -= diff
            roundup_gold         = diff / RATES["USD_GOLD_OZ"]
            balances["GOLD_OZ"] += roundup_gold

    save_wallet(user_id, balances, conn)

    # Persist transaction record
    conn.execute(
        """INSERT INTO transactions
           (user_id, timestamp, from_asset, to_asset, amount, converted_amount, fee, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id,
         datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         from_asset, to_asset,
         round(amount, 6), round(net_amount, 6), round(fee, 6),
         "✅ Completed")
    )
    conn.commit()
    conn.close()
    sig_data       = f"{user_id}|{from_asset}|{to_asset}|{round(amount,6)}|{round(net_amount,6)}"
    signature_code = generate_digital_signature(sig_data)
    return {"balances": balances, "signature_code": signature_code}

# ─────────────────────────────────────────────
# SMS SIMULATION
# ─────────────────────────────────────────────
@app.post("/simulate-sms-transfer", summary="Simulate Encrypted SMS Transfer Command")
async def simulate_sms_transfer(sms: SmsRequest, user_id: int = Depends(get_current_user)):
    decrypted = sms.message.replace("[ENCRYPTED]", "").strip()
    parts     = decrypted.upper().split()

    if len(parts) != 5 or parts[0] != "SEND" or parts[3] != "TO":
        raise HTTPException(
            status_code=400,
            detail="Invalid SMS format. Use: SEND <amount> <FROM_ASSET> TO <TO_ASSET>"
        )
    try:
        amount     = float(parts[1])
        from_asset = parts[2].replace("GOLD", "GOLD_OZ").replace("BITCOIN", "BTC")
        to_asset   = parts[4].replace("GOLD", "GOLD_OZ").replace("BITCOIN", "BTC")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid amount in SMS command.")

    return await swap_assets(SwapRequest(from_asset=from_asset, to_asset=to_asset, amount=amount), user_id)

# ─────────────────────────────────────────────
# FINANCIAL ADVISOR
# ─────────────────────────────────────────────
@app.get("/financial-advice", summary="Get AI-Powered Portfolio Advice")
async def get_financial_advice(user_id: int = Depends(get_current_user)):
    conn     = get_db()
    balances = load_wallet(user_id, conn)
    conn.close()
    RATES = get_live_prices()

    total = (balances["USD"]
             + balances["GOLD_OZ"] * RATES["USD_GOLD_OZ"]
             + balances["BTC"]     * RATES["USD_BTC"])

    if total == 0:
        return {"advice": "محفظتك فارغة. ابدأ بإضافة رصيد للاستفادة من النظام.", "priority": "High"}

    usd_pct  = (balances["USD"]                                / total) * 100
    gold_pct = (balances["GOLD_OZ"] * RATES["USD_GOLD_OZ"]    / total) * 100

    if usd_pct > 70:
        return {
            "advice": f"رصيدك النقدي مرتفع ({usd_pct:.0f}%). فكّر في تحويل جزء منه إلى ذهب أو بيتكوين للتحوط من التضخم.",
            "priority": "High"
        }
    if usd_pct < 10:
        return {
            "advice": "رصيدك النقدي منخفض جداً. احتفظ بسيولة كافية لتغطية المعاملات اليومية.",
            "priority": "Medium"
        }
    if gold_pct < 5:
        return {
            "advice": "نسبة الذهب في محفظتك منخفضة. تخصيص جزء بسيط للذهب يضيف استقراراً لمحفظتك.",
            "priority": "Low"
        }
    return {"advice": "محفظتك متوازنة بشكل جيد. استمر على هذا النهج!", "priority": "Low"}

# ─────────────────────────────────────────────
# OPEN BANKING  (Track 2 — محاكاة الخدمات المصرفية المفتوحة)
# ─────────────────────────────────────────────
MOCK_BANK_TRANSACTIONS = [
    {"id": "TXN001", "merchant": "Carrefour KSA",  "amount": 47.30,  "currency": "SAR", "date": "2026-04-25", "category": "Groceries"},
    {"id": "TXN002", "merchant": "Amazon.sa",       "amount": 120.75, "currency": "SAR", "date": "2026-04-24", "category": "Shopping"},
    {"id": "TXN003", "merchant": "STC Pay",         "amount": 85.00,  "currency": "SAR", "date": "2026-04-23", "category": "Telecom"},
    {"id": "TXN004", "merchant": "Jarir Bookstore", "amount": 215.50, "currency": "SAR", "date": "2026-04-22", "category": "Education"},
    {"id": "TXN005", "merchant": "McDonald's",      "amount": 38.90,  "currency": "SAR", "date": "2026-04-21", "category": "Food & Dining"},
]

@app.post("/open-banking/connect", summary="Simulate Open Banking: Pull Transactions & Auto Round-up to Gold")
async def open_banking_connect(user_id: int = Depends(get_current_user)):
    """محاكاة Open Banking API — سحب معاملات خارجية وتفعيل Round-up بالذهب تلقائياً."""
    RATES             = get_live_prices()
    sar_to_usd        = 1.0 / HACKATHON_RATES["USD_SAR"]
    total_roundup_sar = 0.0
    enriched_txns     = []

    for txn in MOCK_BANK_TRANSACTIONS:
        roundup = round(math.ceil(txn["amount"]) - txn["amount"], 2)
        total_roundup_sar += roundup
        enriched_txns.append({**txn, "roundup_sar": roundup})

    total_roundup_usd = total_roundup_sar * sar_to_usd
    gold_saved        = total_roundup_usd / RATES["USD_GOLD_OZ"]

    conn     = get_db()
    balances = load_wallet(user_id, conn)
    balances["GOLD_OZ"] += gold_saved
    save_wallet(user_id, balances, conn)

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """INSERT INTO transactions (user_id, timestamp, from_asset, to_asset, amount, converted_amount, fee, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, now, "SAR_ROUNDUP", "GOLD_OZ",
         round(total_roundup_sar, 4), round(gold_saved, 8), 0.0,
         "✅ Open Banking Round-up")
    )
    conn.commit()
    conn.close()

    return {
        "bank_name":         "Al Rajhi Bank (محاكاة / Simulated)",
        "transactions":      enriched_txns,
        "total_roundup_sar": round(total_roundup_sar, 2),
        "total_roundup_usd": round(total_roundup_usd, 6),
        "gold_saved_oz":     round(gold_saved, 8),
        "new_gold_balance":  round(balances["GOLD_OZ"], 8),
        "message":           f"تم ربط حسابك بنجاح! وفّرت {gold_saved:.8f} أونصة ذهب عبر نظام Round-up التلقائي."
    }

# ─────────────────────────────────────────────
# TRANSACTION HISTORY
# ─────────────────────────────────────────────
@app.get("/transactions", summary="Get User Transaction History")
async def get_transactions(user_id: int = Depends(get_current_user)):
    conn = get_db()
    rows = conn.execute(
        """SELECT id, timestamp, from_asset, to_asset, amount, converted_amount, fee, status
           FROM transactions WHERE user_id = ?
           ORDER BY id DESC LIMIT 50""",
        (user_id,)
    ).fetchall()
    conn.close()
    return {"transactions": [dict(r) for r in rows]}

# ─────────────────────────────────────────────
# INVOICE SYSTEM  (المسار الثاني — فواتير المستقلين)
# ─────────────────────────────────────────────
@app.post("/invoice/create", summary="Create a Freelancer Invoice")
async def create_invoice(req: InvoiceCreateRequest, user_id: int = Depends(get_current_user)):
    check_amount(req.amount)
    valid_assets = {"USD", "GOLD_OZ", "BTC"}
    if req.currency.upper() not in valid_assets or req.preferred_receive_asset.upper() not in valid_assets:
        raise HTTPException(status_code=400, detail="Invalid currency or preferred asset.")

    invoice_id = str(uuid.uuid4())[:8].upper()
    now        = datetime.datetime.now().isoformat()
    conn       = get_db()
    conn.execute(
        """INSERT INTO invoices (id, user_id, recipient, amount, currency, pref_asset, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (invoice_id, user_id, req.recipient.strip(),
         req.amount, req.currency.upper(), req.preferred_receive_asset.upper(), now)
    )
    conn.commit()
    conn.close()

    payment_link = f"http://127.0.0.1:8501/?page=pay&invoice={invoice_id}"
    return {
        "invoice_id":   invoice_id,
        "payment_link": payment_link,
        "recipient":    req.recipient,
        "amount":       req.amount,
        "currency":     req.currency.upper(),
        "receive_as":   req.preferred_receive_asset.upper(),
        "status":       "pending"
    }

@app.get("/invoice/{invoice_id}", summary="View Invoice Details")
async def get_invoice(invoice_id: str):
    conn = get_db()
    row  = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id.upper(),)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    return dict(row)

@app.post("/invoice/{invoice_id}/pay", summary="Pay an Invoice (Payer pays in invoice currency → Freelancer receives preferred asset)")
async def pay_invoice(invoice_id: str, user_id: int = Depends(get_current_user)):
    conn = get_db()
    inv  = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id.upper(),)).fetchone()
    if not inv:
        conn.close()
        raise HTTPException(status_code=404, detail="Invoice not found.")
    if inv["status"] != "pending":
        conn.close()
        raise HTTPException(status_code=400, detail="Invoice is already paid or cancelled.")

    payer_balances = load_wallet(user_id, conn)
    pay_asset      = inv["currency"]
    pay_amount     = float(inv["amount"])

    if payer_balances[pay_asset] < pay_amount:
        conn.close()
        raise HTTPException(status_code=400, detail=f"Insufficient {pay_asset} to pay this invoice.")

    RATES         = get_live_prices()
    receive_asset = inv["pref_asset"]
    freelancer_id = int(inv["user_id"])

    # Deduct from payer
    payer_balances[pay_asset] -= pay_amount
    save_wallet(user_id, payer_balances, conn)

    # Convert to freelancer's preferred asset
    if pay_asset == "USD":         usd_value = pay_amount
    elif pay_asset == "GOLD_OZ":   usd_value = pay_amount * RATES["USD_GOLD_OZ"]
    else:                          usd_value = pay_amount * RATES["USD_BTC"]

    if receive_asset == "USD":     credit_amount = usd_value
    elif receive_asset == "GOLD_OZ": credit_amount = usd_value / RATES["USD_GOLD_OZ"]
    else:                          credit_amount = usd_value / RATES["USD_BTC"]

    fee          = credit_amount * FEE_PERCENTAGE
    net_credit   = credit_amount - fee

    # Credit freelancer's wallet
    freelancer_balances = load_wallet(freelancer_id, conn)
    freelancer_balances[receive_asset] += net_credit
    save_wallet(freelancer_id, freelancer_balances, conn)

    # Mark invoice paid
    conn.execute(
        "UPDATE invoices SET status = 'paid', paid_at = ? WHERE id = ?",
        (datetime.datetime.now().isoformat(), invoice_id.upper())
    )

    # Log transaction for payer
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """INSERT INTO transactions (user_id, timestamp, from_asset, to_asset, amount, converted_amount, fee, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, now, pay_asset, receive_asset, round(pay_amount, 6), round(net_credit, 6), round(fee, 6),
         f"✅ Invoice #{invoice_id} Paid")
    )
    conn.commit()
    conn.close()

    return {
        "message":        f"Invoice {invoice_id} paid successfully.",
        "paid_amount":    pay_amount,
        "pay_asset":      pay_asset,
        "credited_asset": receive_asset,
        "net_credited":   round(net_credit, 6),
        "fee_charged":    round(fee, 6)
    }

@app.get("/my-invoices", summary="List All Invoices Created by the Logged-In User")
async def list_my_invoices(user_id: int = Depends(get_current_user)):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM invoices WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return {"invoices": [dict(r) for r in rows]}

# ─────────────────────────────────────────────
# VIRTUAL CARD  (البطاقة الافتراضية)
# ─────────────────────────────────────────────
def _generate_card_number() -> str:
    """Generate a Luhn-valid-looking 16-digit card number (for simulation)."""
    groups = [str(random.randint(1000, 9999)) for _ in range(4)]
    groups[0] = "4" + groups[0][1:]  # Visa prefix
    return " ".join(groups)

@app.post("/card/create", summary="Issue a Virtual Payment Card for the User")
async def create_virtual_card(req: CardCreateRequest, user_id: int = Depends(get_current_user)):
    if not req.holder_name.strip():
        raise HTTPException(status_code=400, detail="Holder name is required.")

    conn = get_db()
    existing = conn.execute("SELECT id FROM virtual_cards WHERE user_id = ?", (user_id,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=409, detail="A virtual card already exists for this account. Use GET /card to view it.")

    card_id = str(uuid.uuid4())
    now     = datetime.datetime.now()
    expiry  = f"{now.month:02d}/{(now.year + 3) % 100:02d}"
    cvv     = str(random.randint(100, 999))
    number  = _generate_card_number()

    conn.execute(
        """INSERT INTO virtual_cards (id, user_id, card_number, holder_name, expiry, cvv, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (card_id, user_id, number, req.holder_name.strip(), expiry, cvv, now.isoformat())
    )
    conn.commit()
    conn.close()

    return {
        "card_id":     card_id,
        "card_number": number,
        "holder_name": req.holder_name.strip(),
        "expiry":      expiry,
        "cvv":         cvv,
        "status":      "active",
        "network":     "Visa (Virtual)",
        "message":     "Your Horizon Virtual Card has been issued successfully."
    }

@app.get("/card", summary="View the User's Virtual Card Details")
async def get_virtual_card(user_id: int = Depends(get_current_user)):
    conn = get_db()
    row  = conn.execute("SELECT * FROM virtual_cards WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="No virtual card found. Use POST /card/create to issue one.")
    return dict(row)

@app.delete("/card/freeze", summary="Freeze / Unfreeze the Virtual Card")
async def toggle_card_status(user_id: int = Depends(get_current_user)):
    conn = get_db()
    row  = conn.execute("SELECT status FROM virtual_cards WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="No virtual card found.")
    new_status = "frozen" if row["status"] == "active" else "active"
    conn.execute("UPDATE virtual_cards SET status = ? WHERE user_id = ?", (new_status, user_id))
    conn.commit()
    conn.close()
    return {"message": f"Card is now {new_status}.", "status": new_status}

# ─────────────────────────────────────────────
# Run instructions:
#   pip install -r requirements.txt
#   python -m uvicorn main:app --reload
# ─────────────────────────────────────────────
