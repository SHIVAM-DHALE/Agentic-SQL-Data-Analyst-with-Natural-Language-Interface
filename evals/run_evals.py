from practice.sql_generator import SQLGenerator
from practice.sql_validator import validate_sql
from agent1.tools import execute_sql
from evals.eval_cases import EVAL_CASES
from evals.sql_quality_evaluator import evaluate_sql_quality


def run_evals():
    generator = SQLGenerator()

    passed = 0
    failed = 0

    for case in EVAL_CASES:
        question = case["question"]

        print("=" * 80)
        print("Question:", question)

        try:
            sql = generator.generate_sql(question)

            is_valid, validation_message = validate_sql(sql)
            if not is_valid:
                print("FAIL: SQL safety validation failed")
                print(validation_message)
                failed += 1
                continue

            columns, rows = execute_sql(sql)

            result = evaluate_sql_quality(
                question=question,
                sql=sql,
                expected_columns=case["expected_columns"],
                actual_columns=columns,
                required_terms=case["required_terms"],
            )

            print("SQL:", sql)
            print("Columns:", columns)
            print("Score:", result["score"])
            print("Confidence:", result["confidence"])

            if result["passed"]:
                print("PASS")
                passed += 1
            else:
                print("FAIL")
                failed += 1

        except Exception as e:
            print("FAIL:", e)
            failed += 1

    print("=" * 80)
    print("Passed:", passed)
    print("Failed:", failed)


if __name__ == "__main__":
    run_evals()