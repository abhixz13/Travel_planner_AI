import os

os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")

from core.logging_config import configure_logging
from core.conversation_manager import initiate_conversation, handle_user_input, get_conversation_history
from core.orchestrator import run_session
from dotenv import load_dotenv

def main():
    load_dotenv() # Load environment variables from .env
    configure_logging()
    print("Hello. How are you doing?")
    print("My name is Cursor. I specialize in trip planning and would love to help you with anything.")
    print("Whom I have the pleasure talking to and what can I help with?")
    
    # Initialize conversation with an optional system prompt
    state = initiate_conversation(system_prompt="You are an AI travel planner assistant. Be helpful and engaging.")

    while True:
        user_input = input("\nYou: ")
        if user_input.lower() in ["exit", "quit", "bye"]:
            print("AI Travel Planner: Goodbye!")
            break

        # Add user input to state
        state = handle_user_input(state, user_input)

        # Run the AI session
        try:
            state = run_session(state)
        except Exception as exc:
            error_msg = str(exc).split("\n")[0]
            print(f"\nAI Travel Planner: I ran into an error: {error_msg}")
            print("Please verify your API keys or retry in a moment.")
            continue

        # Display AI's response (last message in history)
        history = get_conversation_history(state)
        if history:
            last_ai_message = next((msg['content'] for msg in reversed(history) if msg['role'] == 'assistant'), "")
            if last_ai_message:
                print(f"AI Travel Planner: {last_ai_message}")

if __name__ == "__main__":
    main()
