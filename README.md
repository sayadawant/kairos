# Kairos Purpose Agent

Kairos is a purpose-finding service delivered through an AI-powered agent. It helps individuals discover clarity, meaning, and direction in a post-AGI world.

The Kairos agent follows a structured interaction flow:

1. Welcomes the user and collects their initial purpose-related question
2. Asks 1-3 follow-up questions to better understand the user's context
3. Provides a brief preview of the forthcoming advice
4. Facilitates a PFT token donation process with transaction verification
5. Delivers comprehensive, personalized purpose guidance (1000-2000 tokens)
6. For premium donations (>=10 PFT), provides additional Oracle Vision insights
7. Closes with an option for additional donations

### Prerequisites

- Python 3.8 or higher
- PFT token capability for donations
- OpenAI API key

### Setup

1. Clone the repository
2. Install required dependencies:
   ```
   pip install openai python-dotenv
   ```
3. Copy the environment example file and configure your settings:
   ```
   cp .env.example .env
   ```
4. Edit `.env` with your OpenAI API key, wallet address, and other settings

## Usage

Run the agent with:

```
python kairos.py
```

Follow the on-screen prompts to interact with the purpose agent.

## Dependencies

- `openai`: For AI model access (GPT-4o)
- `python-dotenv`: For environment variable loading
- `xrpl-py`: For XRP Ledger interaction
- `aiohttp`: For asynchronous HTTP requests
- Local modules:
  - `pft_transact_check`: For donation verification
  - `pythia_addon`: For Oracle Vision feature (premium tier)

## Configuration

Configure the agent through the `.env` file:

- `OPENAI_API_KEY`: Your OpenAI API key
- `XRPL_RPC_ENDPOINT`: XRPL node endpoint for transaction verification
- `WALLET_ADDRESS`: PFT token receiving wallet address
- `MIN_AMOUNT`: Minimum donation amount (default: 2 PFT)
- `MIN_AMOUNT_ADDON`: Premium tier threshold (default: 10 PFT)
- `TIMEOUT`: Donation verification timeout (default: 300 seconds)
- `POLL_INTERVAL`: Verification polling interval (default: 10 seconds)
- `SYSTEM_PROMPT`: Base system prompt for the purpose coach AI
- `FOLLOWUP_SYSTEM_PROMPT`: System prompt for generating follow-up questions
- `PYTHIA_SYSTEM_PROMPT`: System prompt for Oracle Vision (premium feature)

## Notes

- The agent uses several API calls to OpenAI:
  1. First call generates follow-up questions to better understand the user
  2. Second call creates a brief preview/summary of the forthcoming advice
  3. Third call generates comprehensive purpose guidance
  4. Optional fourth call (for premium users) invokes the Oracle Vision
- The premium Oracle Vision feature provides mystical, future-oriented wisdom
- All system prompts are configurable through environment variables
- The code is modular, with separate components for purpose advice and oracle insights