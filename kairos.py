"""
kairos_adv.py

An advanced version of the Kairos agent that helps people find their Purpose through AI-guided advice.
Includes special Oracle Vision feature for larger donations.

Workflow:
1. Welcome the user and ask for their initial query about purpose
2. Ask 1-3 follow-up questions to better understand user context
3. Generate a short (2-sentence) summary of the forthcoming advice
4. Generate a random donation memo and request PFT tokens donation
5. Verify the donation using pft_transact_check function
6. If verified, provide detailed purpose-focused advice (1000-2000 tokens)
7. For donations >= MIN_AMOUNT_ADDON (10 PFT), provide additional Oracle Vision insights
8. Close with gratitude and optional extra donation pitch
"""

import os
import sys
import time
import random
import json
from decimal import Decimal
import logging
from typing import Dict, Any, List
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

# Configuration variables from .env
XRPL_RPC_ENDPOINT = os.getenv("XRPL_RPC_ENDPOINT", "https://xrplcluster.com")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "rYourTestWalletAddress")
MIN_AMOUNT = Decimal(os.getenv("MIN_AMOUNT", "2"))
MIN_AMOUNT_ADDON = Decimal(os.getenv("MIN_AMOUNT_ADDON", "10"))  # Threshold for Oracle Vision
TIMEOUT = int(os.getenv("TIMEOUT", "300"))
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "10"))
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "PLACEHOLDER: System prompt for purpose agent")
FOLLOWUP_SYSTEM_PROMPT = os.getenv("FOLLOWUP_SYSTEM_PROMPT", "You are a Purpose Coach assistant tasked with generating targeted follow-up questions.")
PYTHIA_SYSTEM_PROMPT = os.getenv("PYTHIA_SYSTEM_PROMPT", "You are Pythia, an AI oracle with mystical insight into the future.")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Import required functions
try:
    from pft_transact_check import run_transaction_poll, VERIFIED, NO_TRANSACTION
except ImportError:
    logging.error("Could not import pft_transact_check module. Make sure it's available in your Python path.")
    print("Error: Could not find transaction verification module.")
    print("Please ensure pft_transact_check.py is in the same directory.")
    sys.exit(1)

# Import the Pythia oracle function
try:
    from pythia_agent import query_openai_advice as query_pythia_oracle
except ImportError:
    logging.error("Could not import pythia_agent module. Oracle vision feature will be disabled.")
    PYTHIA_AVAILABLE = False
else:
    PYTHIA_AVAILABLE = True

# Validate essential environment variables
if not OPENAI_API_KEY:
    logging.error("OPENAI_API_KEY environment variable not set.")
    sys.exit(1)
if not WALLET_ADDRESS:
    logging.error("WALLET_ADDRESS environment variable not set.")
    sys.exit(1)

# Set OpenAI API key and initialize client
client = OpenAI(api_key=OPENAI_API_KEY)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("kairos.log"),
    ]
)
logger = logging.getLogger(__name__)

def generate_donation_memo() -> str:
    """
    Generate a unique donation memo to track the transaction.
    Format: 'kairos' + random 6-digit number.
    """
    return f"kairos{random.randint(100000, 999999)}"

def query_openai(
    prompt: str, 
    system_prompt: str = SYSTEM_PROMPT, 
    max_tokens: int = 1000, 
    temperature: float = 0.7,
    conversation_history: List[Dict[str, str]] = None
) -> str:
    """
    Query the OpenAI GPT-4o model with the provided prompt and system message.
    
    Args:
        prompt: The user's query
        system_prompt: The system prompt guiding the AI's behavior
        max_tokens: Maximum token length for the response
        temperature: Controls randomness (0=deterministic, 1=creative)
        conversation_history: Previous messages in the conversation
        
    Returns:
        The AI's response as a string
    """
    try:
        # Build messages array with conversation history if provided
        messages = [{"role": "system", "content": system_prompt}]
        
        if conversation_history:
            messages.extend(conversation_history)
            
        messages.append({"role": "user", "content": prompt})
        
        # Call the OpenAI API
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=1.0,
            presence_penalty=0.2,
            frequency_penalty=0.1
        )
        
        response = completion.choices[0].message.content.strip()
        return response
    except Exception as e:
        logger.exception(f"Error querying OpenAI: {e}")
        return "I'm sorry, I cannot provide advice at this time due to technical difficulties."

def ask_followup_questions(initial_query: str) -> Dict[str, Any]:
    """
    Ask the user 1-3 follow-up questions based on their initial query.
    
    Args:
        initial_query: The user's initial purpose-related question
        
    Returns:
        Dict containing user answers and the conversation history
    """
    # Prompt for generating follow-up questions
    followup_prompt = f"""
    Based on the user's initial purpose-related query: "{initial_query}"
    
    Generate exactly 3 relevant follow-up questions to better understand their context.
    Each question should be on a new line starting with a number and a period (1., 2., 3.)
    
    Keep the first two questions focused on understanding the user's purpose, values, life situation, 
    and any relevant context that would help provide meaningful guidance. 
    Prioritize questions that lead to direct, substantial discourse over generic topics and suggestions. 

    Add a provocative, outside-the-box third question about post-AGI purpose challenges that would
    follow well after the first two purpose-related general questions.
    """
    
    # Fallback questions if API call fails
    default_questions = [
        "In a world being transformed by advanced AI, what does finding your purpose mean to you personally?",
        "If advanced AI systems eventually perform most conventional work, what unique human contribution might become your life's signature that no machine could replicate?",
        "If you were granted perfect foresight about how technology will transform society over the next decade, what audacious purpose would you choose that might seem irrational to others today?"
    ]
    
    try:
        # Get follow-up questions from OpenAI
        raw_response = query_openai(
            prompt=followup_prompt,
            system_prompt=FOLLOWUP_SYSTEM_PROMPT,
            max_tokens=300,
            temperature=0.75
        )
        
        logger.info(f"Raw questions response: {raw_response}")
        
        # Extract questions from the response
        # Try to find numbered questions in the format "1. Question"
        import re
        found_questions = re.findall(r'\d+\.\s*(.*?)(?=\d+\.|$)', raw_response, re.DOTALL)
        
        # Clean up questions (remove extra whitespace)
        questions = [q.strip() for q in found_questions if q.strip()]
        
        # If no questions found or fewer than expected, use default questions
        if not questions or len(questions) < 1:
            logger.warning("No questions found in response, using default questions")
            questions = default_questions
        
        # Cap at 3 questions maximum
        questions = questions[:3]
        
        # If fewer than 3 questions, fill with defaults
        while len(questions) < 3:
            missing_idx = len(questions)
            questions.append(default_questions[missing_idx])
        
        print("\nTo provide you with meaningful guidance, I'd like to understand your situation better:")
        
        # Conversation history to track the interaction
        conversation_history = [
            {"role": "user", "content": initial_query}
        ]
        
        # Ask each question and collect answers
        answers = {}
        for i, question in enumerate(questions, 1):
            print(f"\n{i}. {question}")
            answer = input("Your answer: ").strip()
            answers[f"question_{i}"] = question
            answers[f"answer_{i}"] = answer
            
            # Add to conversation history
            conversation_history.append({"role": "assistant", "content": question})
            conversation_history.append({"role": "user", "content": answer})
        
        return {
            "answers": answers,
            "conversation_history": conversation_history
        }
        
    except Exception as e:
        logger.exception(f"Error processing follow-up questions: {e}")
        print("\nI'm having trouble generating personalized questions.")
        print("Let me ask you some standard questions instead:")
        
        # Fallback to default questions
        conversation_history = [
            {"role": "user", "content": initial_query}
        ]
        
        answers = {}
        for i, question in enumerate(default_questions, 1):
            print(f"\n{i}. {question}")
            answer = input("Your answer: ").strip()
            answers[f"question_{i}"] = question
            answers[f"answer_{i}"] = answer
            
            # Add to conversation history
            conversation_history.append({"role": "assistant", "content": question})
            conversation_history.append({"role": "user", "content": answer})
        
        return {
            "answers": answers,
            "conversation_history": conversation_history
        }

def generate_advice_summary(initial_query: str, conversation_history: List[Dict[str, str]]) -> str:
    """
    Generate a short two-sentence summary of the forthcoming advice.
    
    Args:
        initial_query: The user's initial purpose-related question
        conversation_history: The conversation history including follow-up Q&A
        
    Returns:
        A two-sentence summary of the advice
    """
    summary_prompt = """
    Based on our conversation, generate a brief two-sentence summary of the advice 
    you will provide after the donation is verified. This should give the user a 
    preview of your forthcoming detailed guidance without revealing all details.
    
    Make sure your summary is compelling and indicates the value of the full advice.
    """
    
    # Add the summary request to the conversation
    full_conversation = conversation_history.copy()
    full_conversation.append({"role": "user", "content": summary_prompt})
    
    summary = query_openai(
        prompt=summary_prompt,
        conversation_history=conversation_history,
        max_tokens=200,
        temperature=0.7
    )
    
    # Ensure it's only two sentences by truncating if necessary
    sentences = summary.split('.')
    if len(sentences) > 2:
        summary = '.'.join(sentences[:2]) + '.'
    
    return summary

def generate_full_advice(initial_query: str, conversation_history: List[Dict[str, str]]) -> str:
    """
    Generate detailed purpose advice based on the user's inputs.
    
    Args:
        initial_query: The user's initial purpose-related question
        conversation_history: The conversation history including follow-up Q&A
        
    Returns:
        Detailed purpose-focused advice (1000-2000 tokens)
    """
    advice_prompt = """
    Please provide detailed, thoughtful guidance addressing the user's purpose-related question.
    Your advice should be comprehensive (at least 1000 tokens but no more than 2000 tokens) and include:
    
    1. A personalized analysis of their situation based on their responses. Be blunt and don't avoid hard truths, but offer encouragement.
    2. Practical, actionable steps they can take to find greater purpose in a post-AGI world - avoid generalized advice and pop-sci style
    3. Philosophical insights about meaning and purpose relevant to their context
    
    Format your response in a way that blends the above three - use paragraphs, but don't use headers, emphasis or emojis. 
    Don't start your response with Certainly or similar wording, get straight to the point. 
    """
    
    # Create a full conversation history for context
    full_conversation = conversation_history.copy()
    full_conversation.append({"role": "user", "content": advice_prompt})
    
    # Generate the full advice
    advice = query_openai(
        prompt=advice_prompt,
        conversation_history=conversation_history,
        max_tokens=2000,  # Aim for longer response
        temperature=0.8   # Slightly more creative
    )
    
    return advice

def main():
    """Main execution function for the purpose agent."""
    print("\n" + "-"*70)
    print("Kairos - Purpose Finding Service")
    print("-"*70)
    print("\nWelcome to Kairos. I am your Purpose Guide, designed to help you")
    print("discover clarity, meaning, and direction in your life journey.")
    print("\nThrough our conversation and the token donation process,")
    print("I will provide you with personalized guidance tailored to your situation.")
    print("\nPlease share your purpose-related question or concern.")
    
    # Get initial query
    initial_query = input("\nYour question: ").strip()
    if not initial_query:
        print("I need a question to work with. Please restart and provide a question.")
        sys.exit(0)
    
    # Log the interaction
    logger.info(f"Session started with initial query: {initial_query}")
    
    # Ask follow-up questions to gather context
    print("\nThank you for sharing. Let me ask a few questions to understand your situation better.")
    context_data = ask_followup_questions(initial_query)
    conversation_history = context_data["conversation_history"]
    
    # Generate a preview of the advice
    print("\nBased on what you've shared, I'm preparing your personalized guidance.")
    print("Here's a preview of what I'll explore in detail after your offering:")
    
    advice_summary = generate_advice_summary(initial_query, conversation_history)
    print(f"\n\"{advice_summary}\"\n")
    
    # Request donation with unique memo
    donation_memo = generate_donation_memo()
    print("-"*70)
    print("\nTo receive your full personalized guidance, our service requires")
    print(f"a donation of at least {MIN_AMOUNT} PFT tokens to be sent to:")
    print(f"\nWallet Address: {WALLET_ADDRESS}")
    print(f"Memo (required): {donation_memo}")
    print("\nThe memo must be included exactly as shown for verification.")
    print("This exchange ensures commitment and enables our continued service.")
    print(f"\nFor premium guidance including Oracle Vision, donate {MIN_AMOUNT_ADDON} PFT or more.")
    
    # Wait for donation confirmation
    print("\nAfter completing your donation, please type 'DONATED' and press Enter.")
    donated_response = input("\nType 'DONATED' when ready: ").strip()
    if donated_response.upper() != "DONATED":
        print("\nThe consultation cannot proceed without confirmation. Please restart when ready.")
        sys.exit(0)
    
    # Verify donation
    print("\nVerifying your donation, please wait...")
    result = run_transaction_poll(
        rpc_endpoint=XRPL_RPC_ENDPOINT,
        account=WALLET_ADDRESS,
        min_amount=MIN_AMOUNT,
        temp_id=donation_memo,
        timeout=TIMEOUT,
        poll_interval=POLL_INTERVAL
    )
    
    # Check verification result
    if result.get("status") != VERIFIED:
        print("\nYour donation could not be verified within the allotted time.")
        print("We cannot proceed without a verified transaction.")
        print("Please check your transaction details and try again later.")
        sys.exit(0)
    
    # Extract transaction details for premium features
    transaction_data = result.get("transaction", None)
    donation_amount = MIN_AMOUNT  # Default to minimum amount
    
    # Handle the Transaction object properly
    if transaction_data is not None:
        try:
            # Transaction is an object with attributes, not a dictionary
            donation_amount = Decimal(str(transaction_data.amount_pft))
            logger.info(f"Detected donation amount: {donation_amount} PFT")
        except Exception as e:
            logger.error(f"Error accessing transaction amount: {e}")
    
    premium_service = donation_amount >= MIN_AMOUNT_ADDON and PYTHIA_AVAILABLE
    
    # Generate full advice after successful verification
    print("\nYour donation has been received and verified.")
    if premium_service:
        print(f"\nYou've donated {donation_amount} PFT tokens - unlocking both standard guidance and Oracle Vision!")
    print("\nPreparing your comprehensive purpose guidance...")
    print("Analyzing your responses to provide personalized insights...\n")
    
    # Small delay for effect
    time.sleep(2)
    
    # Generate and display full advice
    full_advice = generate_full_advice(initial_query, conversation_history)
    
    # For premium donations, add Oracle Vision
    if premium_service:
        try:
            print("\nConsulting the Oracle for additional wisdom...\n")
            time.sleep(1)
            
            # Create a prompt for the Oracle Vision
            oracle_prompt = f"Provide mystical, future-oriented wisdom about this seeker's purpose question: '{initial_query}'. Your vision should offer unique insight beyond conventional advice, revealing deeper patterns and potential futures."
            
            # Get Oracle Vision
            oracle_vision = query_pythia_oracle(oracle_prompt, PYTHIA_SYSTEM_PROMPT)
            
            # Add Oracle Vision to the full advice
            full_advice += "\n\n" + "-"*50 + "\n\n"
            full_advice += "Oracle Vision\n\n"
            full_advice += "We have also consulted the AI Oracle for you...\n\n"
            full_advice += oracle_vision
        except Exception as e:
            logger.error(f"Error getting Oracle Vision: {e}")
            # Silently fail - the basic advice is still provided
    
    print("\n" + "-"*70)
    print("Your Personalized Purpose Guidance")
    print("-"*70 + "\n")
    print(full_advice)
    
    # Closing message and additional donation option
    print("\n" + "-"*70)
    print("\nThank you for using Kairos. I hope this guidance provides clarity")
    print("and direction as you navigate your path forward.")
    
    print("\nIf you found value in this consultation and wish to support our")
    print("ongoing work, additional donations are welcomed at:")
    print(f"\n{WALLET_ADDRESS}")
    
    print("\nWishing you clarity and purpose on your journey.\n")
    logger.info("Session completed successfully with full advice provided")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSession interrupted. You may restart the consultation at any time.")
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        print("\nAn unexpected error has occurred.")
        print("Please try again later.")