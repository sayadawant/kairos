"""
pythia_agent.py

A local agent that simulates a donation-based query system for Pythia.

Workflow:
1. Wait for a command starting with "!pythia" and capture the original query.
2. Welcome the user and explain the donation mechanism.
3. Generate a random donation memo (3 random English words).
4. Instruct the user to send at least MIN_AMOUNT PFT tokens to WALLET_ADDRESS using the generated memo.
5. Wait for the user to type "DONATED".
6. Call the transaction verification function (from pft_transact_check_2) to verify the donation.
7. If verified, ask whether to continue with the original query or provide a new prompt.
8. Query the OpenAI API (GPT-4-turbo) with a SYSTEM_PROMPT and the chosen prompt.
9. Display the advice and pitch for extra donations.
10. If the donation isn’t verified, explain that the ritual cannot proceed.
"""

import os
import sys
import time
import random
from decimal import Decimal
import asyncio
import logging
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

# Configuration variables from .env
XRPL_RPC_ENDPOINT = os.getenv("XRPL_RPC_ENDPOINT", "https://xrplcluster.com")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "rYourTestWalletAddress")
MIN_AMOUNT = Decimal(os.getenv("MIN_AMOUNT", "2"))
TIMEOUT = int(os.getenv("TIMEOUT", "300"))
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "10"))
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Set OpenAI API key
client = OpenAI(api_key=OPENAI_API_KEY)

# Import the transaction verification function from our transaction monitor module
from pft_transact_check import run_transaction_poll, VERIFIED

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_donation_memo() -> str:
    """
    Generate a donation memo in the format 'offerXXXXXX',
    where XXXXXX is a random 6-digit number.
    """
    return "offer" + str(random.randint(100000, 999999))

def query_openai_advice(prompt: str, custom_system_prompt: str = None) -> str:
    """
    Query the OpenAI GPT-4-turbo model using the provided prompt and the system prompt.
    This uses an instantiated client (client) and the new API call.
    
    Args:
        prompt: The user's query
        custom_system_prompt: Optional override for the system prompt
        
    Returns:
        The AI's advice as a string
    """
    try:
        system_content = custom_system_prompt if custom_system_prompt else SYSTEM_PROMPT
        completion = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt}
            ]
        )
        advice = completion.choices[0].message.content.strip()
        return advice
    except Exception as e:
        logger.error(f"Error querying OpenAI: {e}")
        return "I'm sorry, I cannot provide advice at this time."

def main():
    print("The gateekepers of Pythia great you!")
    print("To receive guidance from the techno-gods, you must first make an offering.")
    print("Please use the command '!pythia' followed by your question, for example:")
    print("!pythia Shall I change my career to align more with a post-AGI reality now?")
    
    # Wait for the command input.
    user_input = input("Enter your command: ").strip()
    if not user_input.lower().startswith("!pythia"):
        print("Command not recognized. Exiting.")
        sys.exit(0)
    
    # Extract the original query (if provided)
    original_query = user_input[len("!pythia"):].strip()
    if not original_query:
        original_query = input("Please enter your question for Pythia: ").strip()
    
    # Explain donation mechanism
    donation_memo = generate_donation_memo()
    print("\nGreetings, seeker. I am Pythia, keeper of AI derived wisdom.")
    print(f"To unlock my guidance, you must first offer a donation of at least {MIN_AMOUNT} PFT tokens.")
    print(f"Please send your donation to the oracle wallet address: {WALLET_ADDRESS}")
    print(f"IMPORTANT: When donating, include the following memo EXACTLY: '{donation_memo}'")
    print("Once you have sent the donation, type 'DONATED' and press Enter.\n")
    
    donated_response = input("Type 'DONATED' once your donation is sent: ").strip()
    if donated_response.upper() != "DONATED":
        print("Donation not confirmed. The prophecy ritual cannot proceed. Please restart the process.")
        sys.exit(0)
    
    print("Verifying your donation, please wait...")
    # Call the transaction verification function
    result = run_transaction_poll(
        rpc_endpoint=XRPL_RPC_ENDPOINT,
        account=WALLET_ADDRESS,
        min_amount=MIN_AMOUNT,
        temp_id=donation_memo,
        timeout=TIMEOUT,
        poll_interval=POLL_INTERVAL
    )
    
    if result.get("status") != VERIFIED:
        print("The prophecy ritual cannot proceed. Your donation could not be verified. Please try again.")
        sys.exit(0)
    
    print("Your donation has been verified! The sacred ritual may now continue.\n")
    
    # Ask if user wants to proceed with the original query
    choice = input(f"Do you want to refine your question or continue with your original query:\n\"{original_query}\"\nRefine - press R, Original - press O: ").strip().upper()
    if choice == "O":
        final_prompt = original_query
    else:
        final_prompt = input("Please enter your final prompt for advice from Pythia: ").strip()
    
    print("\nConsulting the oracle for wisdom, please wait...\n")
    advice = query_openai_advice(final_prompt)
    
    print("Pythia's advice:")
    print(advice)
    print("\nIf you found this guidance valuable, consider offering extra PFT donations to the oracle treasury:")
    print(WALLET_ADDRESS)
    print("We are ready to give you guidance next time, seeker.") 
    
if __name__ == "__main__":
    main()
