import time
from agent1.agent_controller import process_question

def run_agent(question):
    return process_question(question)

if __name__ == "__main__":

    questions_to_ask = [
        "show all orders",
        "Show top 5 products by revenue",
        "Show revenue by category"
    ]

    for index, q in enumerate(questions_to_ask):
        print(f"\n=======================================================")
        print(f" Processing Question {index + 1}: {q}")
        print(f"=======================================================")

        response = run_agent(q)

        print("\nFINAL RESPONSE:")
        if "error" in response:
            print("❌ Error:", response["error"])
        else:
            print("Question :", response["question"])
            print("SQL      :", response["sql"])
            print("Result   :", response["result"])
            print("Insight  :", response["insight"])
            print("History  :", response["history"])

        # Wait between questions to avoid 429 quota error
        if index < len(questions_to_ask) - 1:
            print("\n⏳ Waiting 20 seconds for API rate limits...")
            time.sleep(20)
