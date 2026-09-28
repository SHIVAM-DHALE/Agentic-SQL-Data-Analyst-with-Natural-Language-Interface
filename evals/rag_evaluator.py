"""
rag_evaluator.py
----------------
Evaluates whether the RAG retriever returns useful project context.

This evaluator checks:
- whether RAG context is retrieved
- whether expected schema/business terms are present
- whether the retrieval is useful for SQL generation

Run:
python -m evals.rag_evaluator
"""

import sys
from pathlib import Path
from typing import Dict, List

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.rag_eval_cases import RAG_EVAL_CASES

try:
    from rag.retriever import get_rag_context
except Exception:
    get_rag_context = None


def normalize_text(text: str) -> str:
    """
    Normalize text for simple case-insensitive matching.
    """
    return " ".join(str(text).lower().split())


def evaluate_single_rag_case(case: Dict) -> Dict:
    """
    Evaluate one RAG test case.
    """

    question = case.get("question", "")
    expected_terms: List[str] = case.get("expected_context_terms", [])

    if get_rag_context is None:
        return {
            "name": case.get("name", "Unnamed case"),
            "question": question,
            "passed": False,
            "score": 0,
            "matched_terms": [],
            "missing_terms": expected_terms,
            "message": "RAG retriever could not be imported.",
        }

    context = get_rag_context(question)

    if not context:
        return {
            "name": case.get("name", "Unnamed case"),
            "question": question,
            "passed": False,
            "score": 0,
            "matched_terms": [],
            "missing_terms": expected_terms,
            "message": "No RAG context retrieved. Check whether vector_index exists.",
        }

    normalized_context = normalize_text(context)

    matched_terms = []
    missing_terms = []

    for term in expected_terms:
        normalized_term = normalize_text(term)

        if normalized_term in normalized_context:
            matched_terms.append(term)
        else:
            missing_terms.append(term)

    score = round((len(matched_terms) / len(expected_terms)) * 100, 2) if expected_terms else 0
    passed = score >= 60

    return {
        "name": case.get("name", "Unnamed case"),
        "question": question,
        "passed": passed,
        "score": score,
        "matched_terms": matched_terms,
        "missing_terms": missing_terms,
        "message": "Passed" if passed else "Needs improvement",
    }


def run_rag_evaluation() -> List[Dict]:
    """
    Run all RAG evaluation cases.
    """

    results = []

    for case in RAG_EVAL_CASES:
        result = evaluate_single_rag_case(case)
        results.append(result)

    return results


def print_rag_evaluation_report(results: List[Dict]) -> None:
    """
    Print readable RAG evaluation report.
    """

    print("\nRAG Evaluation Report")
    print("=" * 60)

    passed_count = 0

    for index, result in enumerate(results, start=1):
        if result["passed"]:
            passed_count += 1

        print(f"\n{index}. {result['name']}")
        print(f"Question: {result['question']}")
        print(f"Passed: {result['passed']}")
        print(f"Score: {result['score']}%")
        print(f"Matched terms: {result['matched_terms']}")
        print(f"Missing terms: {result['missing_terms']}")
        print(f"Message: {result['message']}")

    total = len(results)
    overall_score = round((passed_count / total) * 100, 2) if total else 0

    print("\n" + "=" * 60)
    print(f"Total cases: {total}")
    print(f"Passed cases: {passed_count}")
    print(f"Overall RAG evaluation score: {overall_score}%")
    print("=" * 60)


if __name__ == "__main__":
    evaluation_results = run_rag_evaluation()
    print_rag_evaluation_report(evaluation_results)