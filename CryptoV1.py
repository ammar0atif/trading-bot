import requests
import yaml
import time
import logging
from pathlib import Path
from decimal import Decimal, getcontext

# Configuration
getcontext().prec = 18
CONFIG_FILE = Path("config.yaml")
logging.basicConfig(level=logging.INFO)

class CryptoTrader:
    def __init__(self):
        self.config = self._load_config()
        self.session = requests.Session()
        
    def _load_config(self):
        """Load YAML configuration"""
        with open(CONFIG_FILE, "r") as f:
            return yaml.safe_load(f)

    # add test versions of the analyze_and_trade method in order to test that they work (instead of api called or actual buys, just print a message aka log it to the console)
    # print the time, message, and buy/sell status that way you can tell if you bot would make money if it was a real trade before you use real money

    def analyze_and_trade(self, pair_address: str):
        """Complete trading workflow"""
        try:
            # 1. Fetch pair data
            pair_data = self._get_dexscreener_data(pair_address)
            if not pair_data:
                return {"status": "error", "message": "Data fetch failed"}

            # 2. Security analysis
            security_check = self._security_analysis(pair_data)
            if not security_check["approved"]:
                return security_check

            # 3. Execute GMGN trade
            return self._execute_gmgn_order(pair_data)
            
        except Exception as e:
            logging.error(f"Workflow failed: {str(e)}")
            return {"status": "error", "message": str(e)}

    def _security_analysis(self, data: dict) -> dict:
        """Multi-layered security checks"""
        checks = [
            self._check_blacklists,
            self._check_rug_pull_risk,
            self._check_liquidity,
            self._validate_volume,
            self._analyze_holders
        ]
        
        for check in checks:
            result = check(data)
            if not result["passed"]:
                return result
        return {"approved": True, "message": "Security checks passed"}

    def _execute_gmgn_order(self, data: dict) -> dict:
        """Execute trade on GMGN"""
        try:
            # Calculate position size
            balance = self._get_gmgn_balance()
            position_size = balance * Decimal(self.config["trading"]["position_size_pct"])
            
            # Prepare order payload
            order = {
                "pair": data["pairAddress"],
                "baseToken": data["baseToken"]["address"],
                "quoteToken": data["quoteToken"]["address"],
                "amount": str(position_size),
                "price": data["priceUsd"],
                "side": "BUY",
                "leverage": self.config["trading"]["leverage"],
                "stopLoss": self.config["risk"]["stop_loss_pct"],
                "takeProfit": self.config["risk"]["take_profit_pct"]
            }
            
            response = self.session.post(
                f"{self.config['gmgn']['endpoint']}/orders",
                headers={"X-API-KEY": self.config["gmgn"]["api_key"]},
                json=order,
                timeout=10
            )
            
            if response.status_code == 201:
                logging.info(f"Order executed: {response.json()}")
                return {"status": "success", "order": response.json()}
                
            logging.error(f"Order failed: {response.text}")
            return {"status": "error", "message": response.text}
            
        except Exception as e:
            logging.error(f"Trading error: {str(e)}")
            return {"status": "error", "message": str(e)}

    # Security check implementations
    def _check_blacklists(self, data: dict) -> dict:
        """Verify against blacklists"""
        pair_addr = data["pairAddress"].lower()
        creator_addr = data.get("creator", "").lower()
        
        if pair_addr in self.config["blacklists"]["tokens"]:
            return {"passed": False, "reason": "Token blacklisted"}
        if creator_addr in self.config["blacklists"]["developers"]:
            return {"passed": False, "reason": "Developer blacklisted"}
        return {"passed": True}

    def _check_rug_pull_risk(self, data: dict) -> dict:
        """RugCheck.xyz audit verification"""
        try:
            response = self.session.get(
                f"{self.config['rugcheck']['endpoint']}/audit/{data['baseToken']['address']}",
                timeout=10
            )
            audit = response.json()
            
            if audit.get("auditStatus") != "GOOD":
                return {"passed": False, "reason": "Failed security audit"}
            if audit.get("auditScore", 0) < self.config["rugcheck"]["min_score"]:
                return {"passed": False, "reason": f"Low audit score: {audit['auditScore']}"}
            return {"passed": True}
        except Exception as e:
            logging.error(f"Audit check failed: {str(e)}")
            return {"passed": False, "reason": "Audit verification error"}

    # Additional security checks
    # Finish these security check and confirm that they work
    def _check_liquidity(self, data: dict) -> dict: ...
    def _validate_volume(self, data: dict) -> dict: ...
    def _analyze_holders(self, data: dict) -> dict: ...

    # Utility methods
    def _get_dexscreener_data(self, pair_address: str) -> dict:
        """Fetch pair data from DexScreener"""
        try:
            response = self.session.get(
                f"https://api.dexscreener.com/latest/dex/pairs/{pair_address}", # update the URL to the correct one (V1) https://docs.dexscreener.com/api/reference
                timeout=10
            )
            return response.json()
        except Exception as e:
            logging.error(f"DexScreener error: {str(e)}")
            return None

    def _get_gmgn_balance(self) -> Decimal:
        """Fetch available trading balance"""
        try:
            response = self.session.get(
                f"{self.config['gmgn']['endpoint']}/account/balance",
                headers={"X-API-KEY": self.config["gmgn"]["api_key"]},
                timeout=5
            )
            return Decimal(response.json()["available"])
        except Exception as e:
            logging.error(f"Balance check failed: {str(e)}")
            return Decimal(0)

if __name__ == "__main__":
    trader = CryptoTrader()
    result = trader.analyze_and_trade("0xYourTokenPairAddress")
    print("Trade Result:", result)
