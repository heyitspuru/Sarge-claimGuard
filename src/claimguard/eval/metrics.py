"""Coding-accuracy metrics: partial credit for same-category ICD codes."""


def code_credit(pred: str, true: str) -> float:
    """1.0 exact match, 0.5 same 3-char category (e.g. "K35"), else 0.0."""
    if pred == true:
        return 1.0
    if pred[:3] == true[:3]:
        return 0.5
    return 0.0


def hierarchical_f1(pred: list[str], true: list[str]) -> float:
    """Precision/recall via best-match credit against the other list, then F1."""
    if not pred or not true:
        return 0.0
    precision = sum(max(code_credit(p, t) for t in true) for p in pred) / len(pred)
    recall = sum(max(code_credit(p, t) for p in pred) for t in true) / len(true)
    if precision + recall == 0.0:
        return 0.0
    return 2 * precision * recall / (precision + recall)
