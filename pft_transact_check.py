"""
pft_transact_check_3.py

This module polls the XRP ledger for transactions incoming to a specific wallet address,
filtering for RippleState changes that transfer PFT tokens. It is designed to be invoked
on-demand by an agent, and stops after a specified timeout (default 5 minutes).

A transaction is considered valid if:
  - It transfers PFT tokens.
  - The transferred amount (amount_pft) is at least the specified min_amount.
  - The transaction memo (memo_data) contains the specified temp_id.

If a valid transaction is found, the module returns a VERIFIED response with the transaction details.
If no valid transaction is found within the timeout, it returns NO_TRANSACTION.

This version does not use caching; it directly queries the XRPL node using RpcClient.
"""

import os
import asyncio
import logging
import time
from decimal import Decimal
from typing import Dict, Any

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Import the basic RPC client (without caching) and errors from the PFT SDK
from postfiat.rpc.network import RpcClient
from postfiat.rpc.errors import RpcFetchError
from postfiat.models.transaction import Transaction

# For server info queries
from xrpl.asyncio.clients import AsyncJsonRpcClient
from xrpl.models.requests import ServerInfo

# Setup logging for this module
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Define response constants
VERIFIED = "VERIFIED"
NO_TRANSACTION = "NO_TRANSACTION"

# Load configuration from environment variables
RPC_ENDPOINT = os.getenv("XRPL_RPC_ENDPOINT", "https://xrplcluster.com")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")
MIN_AMOUNT = Decimal(os.getenv("MIN_AMOUNT", "1.0"))
TEMP_ID = os.getenv("TEMP_ID", "TEMP_ID")
TIMEOUT = int(os.getenv("TIMEOUT", "300"))
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "10"))
# LEDGER_OFFSET defines how many ledgers back to start the query from.
LEDGER_OFFSET = int(os.getenv("LEDGER_OFFSET", "5000"))

async def get_latest_ledger_index(rpc_endpoint: str) -> int:
    """
    Retrieves the latest validated ledger index from the XRPL node.
    """
    client = AsyncJsonRpcClient(rpc_endpoint)
    response = await client.request(ServerInfo())
    if hasattr(client, "close"):
        await client.close()
    # Access the latest ledger index from the response structure.
    latest_ledger = int(response.result["info"]["validated_ledger"]["seq"])
    return latest_ledger

async def fetch_latest_transactions(rpc_client: RpcClient, account: str, limit: int = 25) -> list:
    """
    Fetches transactions for the given wallet address by querying from a recent ledger.
    The starting ledger is defined as (latest ledger - LEDGER_OFFSET), ensuring a wide window.
    """
    latest_ledger = await get_latest_ledger_index(RPC_ENDPOINT)
    start_ledger = max(latest_ledger - LEDGER_OFFSET, 0)
    logger.info(f"Fetching transactions for {account} from ledger {start_ledger} to latest (latest: {latest_ledger})...")
    transactions = []
    async for txn in rpc_client.get_account_txns(account, start_ledger=start_ledger, end_ledger=-1):
        transactions.append(txn)
        if len(transactions) >= limit:
            break
    return transactions

def decode_memo(memo_str: str) -> str:
    """
    Decodes the memo field if it is hex-encoded.
    If memo_str is valid hex, decodes it as UTF-8 (using 'replace' for invalid bytes);
    otherwise, returns the original memo_str.
    """
    if not memo_str:
        return ""
    try:
        b = bytes.fromhex(memo_str)
        try:
            return b.decode("utf-8", errors="replace")
        except UnicodeDecodeError as ude:
            logger.error(f"Unicode decode error with errors='replace': {ude}")
            return b.decode("utf-8", errors="ignore")
    except ValueError:
        return memo_str

async def poll_for_valid_transaction(
    rpc_client: RpcClient,
    account: str,
    min_amount: Decimal,
    temp_id: str,
    timeout: int = TIMEOUT,
    poll_interval: int = POLL_INTERVAL
) -> Dict[str, Any]:
    """
    Poll the XRPL for transactions incoming to the specified wallet address.
    The function checks for transactions where:
      - txn.amount_pft >= min_amount, and
      - the memo (txn.memo_data) contains temp_id.
    Polling stops when a valid transaction is found or after 'timeout' seconds.
    """
    start_time = time.time()
    logger.info(f"Starting poll for valid transaction on account {account} with timeout {timeout} sec.")
    while (time.time() - start_time) < timeout:
        try:
            transactions = await fetch_latest_transactions(rpc_client, account, limit=25)
            logger.debug(f"Fetched {len(transactions)} transactions.")
            for txn in transactions:
                try:
                    # Check if the transaction meets the specified criteria.
                    if txn.amount_pft >= min_amount and temp_id in txn.memo_data:
                        logger.info(f"Valid transaction found (hash: {txn.hash}).")
                        return {"status": VERIFIED, "transaction": txn}
                except Exception as e:
                    logger.error(f"Error processing transaction {txn.hash}: {e}")
        except RpcFetchError as e:
            logger.error(f"RPC fetch error during polling: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during polling: {e}")
        await asyncio.sleep(poll_interval)
    logger.info(f"No valid transaction found for account {account} within {timeout} sec.")
    return {"status": NO_TRANSACTION}

def run_transaction_poll(
    rpc_endpoint: str = RPC_ENDPOINT,
    account: str = WALLET_ADDRESS,
    min_amount: Decimal = MIN_AMOUNT,
    temp_id: str = TEMP_ID,
    timeout: int = TIMEOUT,
    poll_interval: int = POLL_INTERVAL
) -> Dict[str, Any]:
    """
    Synchronous wrapper to run the asynchronous poll_for_valid_transaction function.
    This function can be called by an agent script to verify a transaction on-demand.
    """
    try:
        client = RpcClient(rpc_endpoint)
        return asyncio.run(poll_for_valid_transaction(client, account, min_amount, temp_id, timeout, poll_interval))
    except Exception as e:
        logger.error(f"Polling process failed: {e}")
        return {"status": NO_TRANSACTION}

if __name__ == "__main__":
    result = run_transaction_poll()
    print("Polling Result:", result)
