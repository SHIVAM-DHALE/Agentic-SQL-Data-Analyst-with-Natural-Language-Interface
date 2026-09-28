from agent1.agent_workflow import run_agent
import pandas as pd

print("=" * 70)
print("🤖 AGENTIC SQL ASSISTANT")
print("Ask questions in plain English.")
print("Type 'exit' to quit.")
print("=" * 70)

while True:

    question = input("\n📝 Ask Question: ").strip()

    if question.lower() == "exit":
        print("\n👋 Thank you for using Agentic SQL Assistant.")
        break

    if question == "":
        print("⚠️ Please enter a valid question.")
        continue

    response = run_agent(question)

    if "error" in response:
        print("\n" + "=" * 70)
        print("❌ ERROR")
        print("=" * 70)
        print(response["error"])
        print("=" * 70)
        continue

    print("\n" + "=" * 70)
    print("🤖 AGENTIC SQL ASSISTANT RESPONSE")
    print("=" * 70)

    print("\n📝 Question")
    print(f"   {response['question']}")

    print("\n" + "-" * 70)
    print("⚡ Generated SQL")
    print("-" * 70)
    print(response["sql"])

    print("\n" + "-" * 70)
    print("📊 Query Result")
    print("-" * 70)

    if response["result"]:
        df = pd.DataFrame(
            response["result"],
            columns=response["columns"]
        )

        print(df.head(10).to_string(index=False))

        if len(df) > 10:
            print(f"\nShowing first 10 of {len(df)} rows.")
    else:
        print("No rows returned.")

    print("\n" + "-" * 70)
    print("💡 Business Insight")
    print("-" * 70)
    print(response["insight"])

    print("\n" + "-" * 70)
    print("📈 Chart")
    print("-" * 70)

    if response.get("chart_path"):
        print(f"Chart saved at: {response['chart_path']}")
    else:
        print("No chart generated for this query.")

    print("\n" + "-" * 70)
    print("📄 Export Report")
    print("-" * 70)

    if response.get("report_path"):
        print(f"Report saved at: {response['report_path']}")
    else:
        print("No report generated.")

    print("\n" + "-" * 70)
    print("🧠 Conversation Memory")
    print("-" * 70)

    if response["history"]:
        for i, item in enumerate(response["history"], start=1):
            print(f"{i}. {item}")
    else:
        print("No conversation history.")

    print("\n" + "=" * 70)
    print("✅ Query Executed Successfully")
    print("=" * 70)
