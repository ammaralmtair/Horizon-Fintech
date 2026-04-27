"""
Backend for Horizon Fintech MVP using FastAPI.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict

app = FastAPI(title="Horizon Fintech API", version="1.0.0")

# --- In-memory Database Simulation ---
# For the hackathon, we'll use a simple dictionary to simulate a user's wallet.
# In a real-world scenario, this would be a proper database.
virtual_wallet = {
    "USD": 10000.0,
    "GOLD_OZ": 5.0,
    "BTC": 0.2
}

# --- Fixed Exchange Rates for Demo ---
EXCHANGE_RATES = {
    "USD_GOLD_OZ": 2300.0,
    "USD_BTC": 65000.0
}

# --- Pydantic Models for Request/Response ---
class Wallet(BaseModel):
    balances: Dict[str, float]

class SwapRequest(BaseModel):
    from_asset: str
    to_asset: str
    amount: float

class Invoice(BaseModel):
    amount: float
    currency: str
    recipient: str

class SmsRequest(BaseModel):
    message: str

# --- API Endpoints ---

@app.get("/wallet", response_model=Wallet, summary="Get User Wallet Balances")
async def get_wallet():
    """
    Retrieves the current balances of all assets in the user's virtual wallet.
    """
    return {"balances": virtual_wallet}

@app.post("/swap", response_model=Wallet, summary="Swap Between Assets")
async def swap_assets(request: SwapRequest):
    """
    Performs a conversion between two assets based on a fixed exchange rate.
    Example: Convert 100 USD to Gold.
    """
    from_asset, to_asset, amount = request.from_asset.upper(), request.to_asset.upper(), request.amount

    if from_asset not in virtual_wallet or to_asset not in virtual_wallet:
        raise HTTPException(status_code=400, detail="Invalid asset specified.")
    
    if virtual_wallet[from_asset] < amount:
        raise HTTPException(status_code=400, detail=f"Insufficient balance for {from_asset}.")

    # Perform the swap
    virtual_wallet[from_asset] -= amount
    
    # USD to Gold/BTC
    if from_asset == 'USD':
        if to_asset == 'GOLD_OZ':
            converted_amount = amount / EXCHANGE_RATES['USD_GOLD_OZ']
        elif to_asset == 'BTC':
            converted_amount = amount / EXCHANGE_RATES['USD_BTC']
        else: # USD to USD
            converted_amount = amount
    # Gold/BTC to USD
    elif to_asset == 'USD':
        if from_asset == 'GOLD_OZ':
            converted_amount = amount * EXCHANGE_RATES['USD_GOLD_OZ']
        elif from_asset == 'BTC':
            converted_amount = amount * EXCHANGE_RATES['USD_BTC']
        else: # Should not happen with current logic
            raise HTTPException(status_code=400, detail="Direct swap not supported.")
    else:
        raise HTTPException(status_code=400, detail="Direct swap between non-USD assets not supported in this MVP.")

    virtual_wallet[to_asset] += converted_amount
    
    # --- Round-up Savings Feature ---
    if from_asset == 'USD':
        transaction_cost = amount
        rounded_up_amount = (transaction_cost // 1) + 1 # Ceil to next dollar
        difference = rounded_up_amount - transaction_cost
        
        if difference > 0 and virtual_wallet['USD'] >= difference:
            virtual_wallet['USD'] -= difference
            gold_to_add = difference / EXCHANGE_RATES['USD_GOLD_OZ']
            virtual_wallet['GOLD_OZ'] += gold_to_add

    return {"balances": virtual_wallet}

@app.post("/simulate-sms-transfer", response_model=Wallet, summary="Simulate Transfer via SMS command")
async def simulate_sms_transfer(sms: SmsRequest):
    """
    Parses a string command like "SEND 100 USD TO GOLD" to perform a swap.
    """
    parts = sms.message.upper().split()
    # Expected format: "SEND <amount> <from_asset> TO <to_asset>"
    if len(parts) != 5 or parts[0] != 'SEND' or parts[3] != 'TO':
        raise HTTPException(status_code=400, detail="Invalid SMS format. Use 'SEND <amount> <from_asset> TO <to_asset>'.")
    
    try:
        amount = float(parts[1])
        from_asset = parts[2]
        # Map common terms to our asset keys
        if from_asset == "GOLD": from_asset = "GOLD_OZ"
        if from_asset == "BITCOIN": from_asset = "BTC"

        to_asset = parts[4]
        if to_asset == "GOLD": to_asset = "GOLD_OZ"
        if to_asset == "BITCOIN": to_asset = "BTC"

        swap_request = SwapRequest(from_asset=from_asset, to_asset=to_asset, amount=amount)
        return await swap_assets(swap_request)
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="Invalid amount or assets in SMS command.")

# To run this app:
# 1. Install fastapi and uvicorn: pip install fastapi "uvicorn[standard]"
# 2. Save the code as main.py
# 3. Run in terminal: uvicorn main:app --reload
