import os
import time
import threading
from flask import Flask, jsonify
from web3 import Web3
from eth_account import Account

# 1. Enable HD wallet features for mnemonic derivation
Account.enable_unaudited_hdwallet_features()

app = Flask(__name__)

# 2. Configuration & Derivation
SEED_PHRASE = os.environ.get("SEED_PHRASE")
SAFE_ENV = os.environ.get("SAFE_ADDRESS")
SAFE_ADDRESS = Web3.to_checksum_address(SAFE_ENV) if SAFE_ENV else None

try:
    evm_account = Account.from_mnemonic(SEED_PHRASE)
    PRIVATE_KEY = evm_account.key.hex()
    WALLET_ADDRESS = evm_account.address
    print(f"[inf] [+] Derived EVM Address: {WALLET_ADDRESS}")
except Exception as e:
    print(f"[err] [-] Mnemonic Derivation Error: {str(e)}")
    PRIVATE_KEY, WALLET_ADDRESS = None, None

ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"constant": False, "inputs": [{"name": "_to", "type": "address"}, {"name": "_value", "type": "uint256"}], "name": "transfer", "outputs": [{"name": "", "type": "bool"}], "type": "function"}
]

# 3. Multi-Chain Configuration Dictionary
NETWORKS = {
    "Polygon": {
        "rpc_env": "POLY_RPC_URL", "chain_id": 137, "cooldown": 4,
        "tokens": {
            "USDT": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
            "USDC_NATIVE": "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
            "USDC_BRIDGED": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
        }
    },
    "Arbitrum": {
        "rpc_env": "ARB_RPC_URL", "chain_id": 42161, "cooldown": 1,
        "tokens": {
            "USDT": "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9",
            "USDC": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"
        }
    },
    "BSC": {
        "rpc_env": "BSC_RPC_URL", "chain_id": 56, "cooldown": 5,
        "tokens": {
            "USDT": "0x55d398326f99059fF77548524699902783197955",
            "USDC": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d"
        }
    },
    "Optimism": {
        "rpc_env": "OPT_RPC_URL", "chain_id": 10, "cooldown": 2,
        "tokens": {
            "USDT": "0x94b008aA00579c1307B0EF2c499aD98a8ce58e58",
            "USDC": "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85"
        }
    },
    "Base": {
        "rpc_env": "BASE_RPC_URL", "chain_id": 8453, "cooldown": 2,
        "tokens": {
            "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
        }
    },
    "Avalanche": {
        "rpc_env": "AVAX_RPC_URL", "chain_id": 43114, "cooldown": 2,
        "tokens": {
            "USDT": "0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7"
        }
    },
    "Ethereum": {
        "rpc_env": "ETH_RPC_URL", "chain_id": 1, "cooldown": 12,
        "tokens": {
            "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
            "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
        }
    }
}

# 4. Initialize Connections
connections = {}
if WALLET_ADDRESS and SAFE_ADDRESS:
    for name, config in NETWORKS.items():
        rpc_url = os.environ.get(config["rpc_env"])
        if rpc_url:
            w3 = Web3(Web3.HTTPProvider(rpc_url))
            if w3.is_connected():
                connections[name] = {"w3": w3, "config": config}
                print(f"[inf] [+] Connected to {name}")
            else:
                print(f"[err] [-] Failed to connect to {name}")
        else:
            print(f"[inf] [-] Skipping {name} (No RPC URL provided)")

# 5. Rapid Gas Calculator
def get_rapid_gas_dict(w3):
    try: 
        latest_block = w3.eth.get_block('latest')
        base_fee = latest_block['baseFeePerGas']
        priority_tip = int(w3.eth.max_priority_fee * 1.5)
        max_fee = int((base_fee * 2) + priority_tip)
        return {'maxFeePerGas': max_fee, 'maxPriorityFeePerGas': priority_tip}
    except Exception:
        return {'gasPrice': int(w3.eth.gas_price * 1.30)}

# 6. Sweep Logic
def sweep_token(name, w3, chain_id, token_name, token_address, nonce):
    try:
        token_contract = w3.eth.contract(address=Web3.to_checksum_address(token_address), abi=ERC20_ABI)
        balance = token_contract.functions.balanceOf(WALLET_ADDRESS).call()
        if balance > 0:
            tx = {
                'from': WALLET_ADDRESS,
                'nonce': nonce,
                'gas': 100000,
                'chainId': chain_id
            }
            tx.update(get_rapid_gas_dict(w3))
            contract_tx = token_contract.functions.transfer(SAFE_ADDRESS, balance).build_transaction(tx)
            signed_tx = w3.eth.account.sign_transaction(contract_tx, private_key=PRIVATE_KEY)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            print(f"[inf] [!] {name} - {token_name} swept! Tx: {w3.to_hex(tx_hash)}")
            return (True, True)
        return (False, False)
    except Exception as e:
        print(f"[err] [-] Error sweeping {token_name} on {name}: {str(e)}")
        return (True, False)

def sweep_native(name, w3, chain_id, nonce):
    try:
        balance = w3.eth.get_balance(WALLET_ADDRESS)
        if balance > 0:
            gas_limit = 21000
            gas_fees = get_rapid_gas_dict(w3)
            
            if 'maxFeePerGas' in gas_fees:
                max_tx_cost = gas_limit * gas_fees['maxFeePerGas']
            else:
                max_tx_cost = gas_limit * gas_fees['gasPrice']
                
            if balance > max_tx_cost:
                amount_to_send = balance - max_tx_cost
                tx = {
                    'nonce': nonce,
                    'to': SAFE_ADDRESS,
                    'value': amount_to_send,
                    'gas': gas_limit,
                    'chainId': chain_id
                }
                tx.update(gas_fees)
                signed_tx = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
                tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
                print(f"[inf] [!] {name} - Native token swept! Tx: {w3.to_hex(tx_hash)}")
                return True
    except Exception:
        pass
    return False

# 7. Sweeper Loop
def sweeper_loop():
    if not connections:
        print("[err] [-] Sweeper thread stopping: No networks configured.")
        return
    
    print(f"[inf] [+] Sweeper started monitoring {len(connections)} networks...")
    while True:
        for name, data in connections.items():
            w3 = data["w3"]
            config = data["config"]
            chain_id = config["chain_id"]
            try:
                nonce = w3.eth.get_transaction_count(WALLET_ADDRESS, 'pending')
                swept_anything = False
                unresolved_tokens = False
                
                # Sweep Tokens
                for token_name, token_address in config["tokens"].items():
                    has_balance, success = sweep_token(name, w3, chain_id, token_name, token_address, nonce)
                    if has_balance and success:
                        nonce += 1
                        swept_anything = True
                        time.sleep(1)
                    elif has_balance and not success:
                        unresolved_tokens = True
                
                # Sweep Native Token
                if not unresolved_tokens:
                    if sweep_native(name, w3, chain_id, nonce):
                        swept_anything = True
                        
                if swept_anything:
                    time.sleep(config.get("cooldown", 8))
                    
            except Exception:
                pass
                
        # Throttled 3-second cycle interval
        time.sleep(3)

if WALLET_ADDRESS:
    threading.Thread(target=sweeper_loop, daemon=True).start()

@app.route('/')
def health_check():
    return jsonify({"status": "running", "networks_monitored": list(connections.keys())}), 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8000)))