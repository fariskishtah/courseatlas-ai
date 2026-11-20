"""Hand-annotated evaluation set (60 questions, 3 courses).

Gold labels are written by hand as (file, substring) pairs: a retrieved chunk is relevant if it comes from
that file and contains the substring (case-insensitive). This is independent of chunking and of the system's output.
`need`: "any" = one gold group is enough; "all" = every group must be covered (cross-document questions).
`criteria`: regexes; an answer is keyword-correct if ANY matches (a proxy; sampled manual review is in docs/EVALUATION.md).
The script validates that every gold substring really occurs in the named file.
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.ingestion import extract  # noqa: E402

PL, PD, PC, PT = ("python_lecture_notes.pdf", "python_exercise_guide.docx", "python_practice_exercises.csv", "python_reference_notes.txt")
SL, SD, SC, ST = ("statistics_lecture_notes.pdf", "statistics_exercise_guide.docx", "statistics_worked_examples.csv", "statistics_reference_notes.txt")
ML_, MD, MC, MT = ("ml_lecture_notes.pdf", "ml_exercise_guide.docx", "ml_model_evaluation_runs.csv", "ml_reference_notes.txt")

dB = [10, 12, 23, 23, 16, 23, 21, 16]
vB = statistics.variance(dB)
G = lambda f, *subs: {"file": f, "contains": list(subs)}  # noqa: E731

Q = []  # (course, category, question, answerable, gold, need, criteria)
def add(c, cat, q, ans, gold=(), need="any", crit=()):
    Q.append((c, cat, q, ans, list(gold), need, list(crit)))

# ---------------- python
add("python", "direct_factual", "What does the // operator do in Python?", True, [G(PL, "Integer division // discards")], crit=[r"fraction|integer division|discard|floor|round"])
add("python", "direct_factual", "Why does range(1, 20) not include the number 20?", True, [G(PD, "range(1, 20), which stops at 19"), G(PL, "never includes stop")], crit=[r"stop|exclud|not include|19"])
add("python", "direct_factual", "What does the with statement guarantee when you open a file?", True, [G(PL, "guarantees the file is closed")], crit=[r"clos"])
add("python", "direct_factual", "What is the difference between sorted() and list.sort()?", True, [G(PT, "list.sort() sorts in place"), G(PL, "sorted(nums) returns a new sorted list")], crit=[r"new (sorted )?list|in[- ]place"])
add("python", "concept_explanation", "Explain why a mutable default argument is dangerous in a Python function.", True, [G(PL, "Never use a mutable object"), G(PD, "shared between calls")], crit=[r"once|shared|same list|accumulate"])
add("python", "concept_explanation", "How does inheritance work in Python classes?", True, [G(PL, "Inheritance lets a subclass reuse")], crit=[r"subclass|parent|super"])
add("python", "concept_explanation", "What is the difference between a list and a tuple?", True, [G(PL, "A tuple is an ordered but immutable")], crit=[r"immutable|mutable"])
add("python", "cross_document", "How do the lecture notes and the exercise guide explain the mutable default argument bug and its fix?", True, [G(PL, "Never use a mutable object"), G(PD, "shared between calls")], "all", [r"None"])
add("python", "cross_document", "What does ValueError mean, and which practice exercise demonstrates it?", True, [G(PT, "ValueError: the type is right"), G(PC, "PY015")], "all", [r"PY015|int\(['\"]?abc"])
add("python", "csv_row", "What is the expected output of 7 // 2 according to the practice exercises?", True, [G(PC, "PY001")], crit=[r"\b3\b"])
add("python", "csv_row", "Which practice exercise shows that zip stops at the shortest input?", True, [G(PC, "PY012")], crit=[r"PY012"])
add("python", "csv_row", "What difficulty level is exercise PY014 and what does it demonstrate?", True, [G(PC, "PY014")], crit=[r"hard|mutable"])
add("python", "exact_terminology", "What indentation does PEP 8 recommend?", True, [G(PT, "PEP 8 recommends four spaces")], crit=[r"four|4 spaces"])
add("python", "exact_terminology", "What does a KeyError mean?", True, [G(PT, "KeyError: a dictionary key does not exist")], crit=[r"key"])
add("python", "exact_terminology", "What is the LEGB rule?", True, [G(PL, "LEGB rule")], crit=[r"Local.*Enclosing.*Global.*Built"])
add("python", "unanswerable", "What is the average salary of a Python engineer in Egypt?", False)
add("python", "unanswerable", "Which Python version introduced the walrus operator and what is its syntax?", False)
add("python", "other_course", "How do I compute a 95% confidence interval for a mean?", False)
add("python", "other_course", "What is the F1 score and how is it computed?", False)
add("python", "ambiguous", "How do I fix the error?", False)
# ---------------- statistics
add("statistics", "direct_factual", "Why does sample variance divide by n - 1?", True, [G(SL, "Bessel's correction")], crit=[r"Bessel|underestimat|sample mean"])
add("statistics", "direct_factual", "What does the empirical rule say about the normal distribution?", True, [G(SL, "68% of values lie within")], crit=[r"68"])
add("statistics", "direct_factual", "State Bayes' theorem.", True, [G(SL, "Bayes' theorem reverses"), G(ST, "Bayes: P(A|B)")], crit=[r"P\(A\s*\|\s*B\)|P\(B\s*\|\s*A\)"])
add("statistics", "direct_factual", "What is the standard error of the mean?", True, [G(ST, "Standard error of the mean"), G(SL, "standard error")], crit=[r"sqrt|square root|sigma|standard deviation"])
add("statistics", "concept_explanation", "How should a 95% confidence interval be interpreted?", True, [G(SL, "does not mean there is a 95% probability")], crit=[r"repeated|many times|95\s*%"])
add("statistics", "concept_explanation", "What does a p-value tell us, and what does it not tell us?", True, [G(SL, "A p-value is not the probability")], crit=[r"null|extreme"])
add("statistics", "concept_explanation", "Why does a positive test for a rare disease not mean the person is probably sick?", True, [G(SL, "base rate effect"), G(SC, "Disease 1%")], crit=[r"rare|base rate|16"])
add("statistics", "cross_document", "What is the sample variance of 2, 4, 4, 4, 5, 5, 7, 9 and why is the formula divided by n - 1?", True, [G(SD, "32 / 7"), G(SL, "Bessel's correction")], "all", [r"4\.57|32\s*/\s*7"])
add("statistics", "cross_document", "What are the mean and variance of a binomial distribution, and where is this summarised?", True, [G(SD, "Binomial(n, p)"), G(SL, "Its mean is n * p")], "all", [r"n\s*\*?\s*p"])
add("statistics", "csv_row", "What is the sample variance of Dataset B in the worked examples?", True, [G(SC, "Dataset B", "Sample variance")], crit=[rf"{str(vB)[:4]}|{round(vB, 1)}"])
add("statistics", "csv_row", "Which worked example gives the probability that both cards drawn are aces?", True, [G(SC, "both aces")], crit=[r"0\.0045|4/52|ST0"])
add("statistics", "csv_row", "What is the z-score for x = 85 with mean 70 and standard deviation 10 in the worked examples?", True, [G(SC, "z-score of x = 85")], crit=[r"1\.5"])
add("statistics", "exact_terminology", "What is the IQR rule for flagging outliers?", True, [G(SL, "1.5 * IQR"), G(ST, "Outlier fences")], crit=[r"1\.5"])
add("statistics", "exact_terminology", "What is the formula for a Poisson probability?", True, [G(ST, "Poisson: P(X = k)")], crit=[r"lambda|e\^|λ"])
add("statistics", "exact_terminology", "What is a Type I error?", True, [G(SL, "A Type I error means"), G(ST, "Type I error rate")], crit=[r"reject.*true|alpha|false positive"])
add("statistics", "unanswerable", "What was the population of Egypt in 2020?", False)
add("statistics", "unanswerable", "How do I run a Mann-Whitney U test in R?", False)
add("statistics", "other_course", "What is the difference between a list and a tuple in Python?", False)
add("statistics", "other_course", "What is overfitting in a decision tree?", False)
add("statistics", "ambiguous", "What is the variance?", True, [G(SL, "The variance averages squared deviations"), G(ST, "Population variance")], crit=[r"squared|deviation"])
# ---------------- ml
add("ml", "direct_factual", "What does recall measure?", True, [G(ML_, "Recall (sensitivity) = TP / (TP + FN)"), G(MT, "Recall: TP / (TP + FN)")], crit=[r"TP|truly positive|actual positive|found"])
add("ml", "direct_factual", "Why is accuracy misleading on imbalanced data?", True, [G(ML_, "Accuracy is misleading on imbalanced data"), G(MD, "99%")], crit=[r"majority"])
add("ml", "direct_factual", "What is k-fold cross-validation?", True, [G(ML_, "k-fold cross-validation splits")], crit=[r"fold|held[- ]out|average"])
add("ml", "direct_factual", "What does a ROC AUC of 0.5 mean?", True, [G(ML_, "0.5 is random guessing"), G(MT, "0.5 means random ranking")], crit=[r"random"])
add("ml", "concept_explanation", "What is overfitting and how can it be reduced?", True, [G(ML_, "Ways to reduce overfitting"), G(MD, "limiting the maximum depth")], crit=[r"regulariz|more data|simpl|depth|cross-validation"])
add("ml", "concept_explanation", "Explain the bias-variance tradeoff.", True, [G(ML_, "The bias-variance tradeoff explains")], crit=[r"bias", ])
add("ml", "concept_explanation", "What is data leakage?", True, [G(ML_, "Data leakage more generally"), G(MT, "Data leakage: using information")], crit=[r"information|test|future"])
add("ml", "cross_document", "Why is standardizing the full dataset before splitting wrong, and what rule does the concept guide give for scalers?", True, [G(MD, "The scaler computed"), G(ML_, "Scalers must be fit on the training data only")], "all", [r"training"])
add("ml", "cross_document", "Which model in the evaluation runs overfits the most and what does the concept guide suggest to reduce overfitting?", True, [G(MC, "ML002"), G(ML_, "Ways to reduce overfitting")], "all", [r"ML002|Decision Tree|depth=None|regulariz|depth"])
add("ml", "csv_row", "What was the validation accuracy of the Random Forest in the spam classification runs?", True, [G(MC, "ML004")], crit=[r"0\.95"])
add("ml", "csv_row", "Which fraud detection model has the highest F1 in the evaluation runs?", True, [G(MC, "ML009")], crit=[r"Gradient Boosting|ML009"])
add("ml", "csv_row", "What recall did the always-predict-majority model achieve?", True, [G(MC, "ML007")], crit=[r"\b0(\.0+)?\b|zero|ML007"])
add("ml", "exact_terminology", "What is the formula for precision?", True, [G(ML_, "Precision = TP / (TP + FP)"), G(MT, "Precision: TP / (TP + FP)")], crit=[r"TP"])
add("ml", "exact_terminology", "What is the difference between a parameter and a hyperparameter?", True, [G(MT, "Hyperparameter: a setting chosen")], crit=[r"before training|learned during training|chosen"])
add("ml", "exact_terminology", "What does L1 regularization do to weights?", True, [G(MT, "L1 (lasso) can set weights to zero"), G(ML_, "L1 can drive weights to exactly zero")], crit=[r"zero"])
add("ml", "unanswerable", "Which GPU is best for training large language models?", False)
add("ml", "unanswerable", "How does the transformer attention mechanism work?", False)
add("ml", "other_course", "What is the Central Limit Theorem?", False)
add("ml", "other_course", "How do I open a file in Python?", False)
add("ml", "ambiguous", "Which model is best?", False)


def main() -> None:
    texts = {}
    for f in (ROOT / "data" / "sample_courses").rglob("*.*"):
        if f.suffix in (".pdf", ".docx", ".csv", ".txt"):
            texts[f.name] = " ".join(b.text for b in extract(f).blocks).lower()
    out, per_cat_seen, bad = [], {}, 0
    for i, (c, cat, q, ans, gold, need, crit) in enumerate(Q, 1):
        for g in gold:
            for s in g["contains"]:
                if s.lower() not in texts[g["file"]]:
                    print(f"GOLD NOT FOUND q{i}: {g['file']} :: {s}")
                    bad += 1
        k = (c, cat)
        per_cat_seen[k] = per_cat_seen.get(k, 0) + 1
        out.append({"id": f"{c[:2]}-{i:03d}", "course_id": c, "question": q, "category": cat, "answerable": ans, "gold": gold,
                    "need": need, "criteria": crit, "split": "dev" if per_cat_seen[k] % 2 else "test"})
    (ROOT / "data" / "eval").mkdir(exist_ok=True)
    with open(ROOT / "data" / "eval" / "questions.jsonl", "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(len(out), "questions; gold errors:", bad)


if __name__ == "__main__":
    main()
