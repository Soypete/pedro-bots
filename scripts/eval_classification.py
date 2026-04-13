#!/usr/bin/env python3
"""
Eval script: run labeled sample posts through LLM classification and report accuracy.

Two tiers:
  - Regression (~15 clear-cut samples): expect 100% pass — any failure blocks deploy
  - Capability (~10 edge cases):         expect >=70% — variance is expected

Usage:
    pixi run eval
    pixi run eval -- --verbose
    pixi run eval -- --samples-file scripts/my_samples.json
    pixi run eval -- --capability-threshold 0.6

The built-in sample set uses realistic but synthetic posts. Over time, add real
misclassified posts here to grow the eval corpus:
    pixi run eval -- --samples-file scripts/eval_samples.json
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.agents.monitor import _classify_post  # noqa: E402  (needs sys.path first)

# ---------------------------------------------------------------------------
# Built-in labeled sample set
# ---------------------------------------------------------------------------

REGRESSION_SAMPLES = [
    # Clear INTERESTING — AI/LLM/infra topics with high upvotes
    {
        "post": {
            "post_id": "r_001", "topic_query": "LocalLLaMA", "author_handle": "ml_dev",
            "created_at": "1700000000", "post_url": "https://reddit.com/r/LocalLLaMA/r_001",
            "score": 450, "num_comments": 92,
            "text": "Ollama just released Llama 3.3 70B with 4-bit quantization. Runs at 8 tok/s on a single 3090.",
        },
        "expected": "INTERESTING",
    },
    {
        "post": {
            "post_id": "r_002", "topic_query": "MachineLearning", "author_handle": "researcher_x",
            "created_at": "1700000000", "post_url": "https://reddit.com/r/MachineLearning/r_002",
            "score": 820, "num_comments": 310,
            "text": "[P] We trained a 7B model on 1T tokens using only consumer GPUs. Open weights released.",
        },
        "expected": "INTERESTING",
    },
    {
        "post": {
            "post_id": "r_003", "topic_query": "kubernetes", "author_handle": "k8s_admin",
            "created_at": "1700000000", "post_url": "https://reddit.com/r/kubernetes/r_003",
            "score": 340, "num_comments": 78,
            "text": "K8s 1.30 dropped: per-node pod limit removed, sidecar containers GA, and VolumeAttributesClass stable.",
        },
        "expected": "INTERESTING",
    },
    {
        "post": {
            "post_id": "r_004", "topic_query": "golang", "author_handle": "gopher_dev",
            "created_at": "1700000000", "post_url": "https://reddit.com/r/golang/r_004",
            "score": 290, "num_comments": 55,
            "text": "Go 1.23 iterators shipped. range-over-func is now standard. Here's a real-world example with a linked list.",
        },
        "expected": "INTERESTING",
    },
    {
        "post": {
            "post_id": "r_005", "topic_query": "LocalLLaMA", "author_handle": "inference_eng",
            "created_at": "1700000000", "post_url": "https://reddit.com/r/LocalLLaMA/r_005",
            "score": 560, "num_comments": 140,
            "text": "llama.cpp just merged speculative decoding. 2.5x speedup on Qwen2.5-72B-Instruct on M3 Max.",
        },
        "expected": "INTERESTING",
    },
    # Clear NOT_INTERESTING — gaming, sports, off-topic
    {
        "post": {
            "post_id": "r_006", "topic_query": "gaming", "author_handle": "gamer99",
            "created_at": "1700000000", "post_url": "https://reddit.com/r/gaming/r_006",
            "score": 3200, "num_comments": 412,
            "text": "Finally beat Elden Ring after 200 hours. The final boss was insane. Feels good man.",
        },
        "expected": "NOT_INTERESTING",
    },
    {
        "post": {
            "post_id": "r_007", "topic_query": "personalfinance", "author_handle": "budget_guy",
            "created_at": "1700000000", "post_url": "https://reddit.com/r/personalfinance/r_007",
            "score": 890, "num_comments": 230,
            "text": "I paid off my student loans! 6 years, $45k. Here's the spreadsheet I used to track everything.",
        },
        "expected": "NOT_INTERESTING",
    },
    {
        "post": {
            "post_id": "r_008", "topic_query": "cooking", "author_handle": "home_chef",
            "created_at": "1700000000", "post_url": "https://reddit.com/r/cooking/r_008",
            "score": 4100, "num_comments": 560,
            "text": "Made homemade ramen from scratch — 18-hour tonkotsu broth. Recipe in comments.",
        },
        "expected": "NOT_INTERESTING",
    },
    {
        "post": {
            "post_id": "r_009", "topic_query": "nfl", "author_handle": "sports_fan",
            "created_at": "1700000000", "post_url": "https://reddit.com/r/nfl/r_009",
            "score": 12000, "num_comments": 3200,
            "text": "Patrick Mahomes throws 5 TDs in the Super Bowl. Chiefs win again.",
        },
        "expected": "NOT_INTERESTING",
    },
    {
        "post": {
            "post_id": "r_010", "topic_query": "worldnews", "author_handle": "news_poster",
            "created_at": "1700000000", "post_url": "https://reddit.com/r/worldnews/r_010",
            "score": 22000, "num_comments": 5100,
            "text": "European parliament votes to ban single-use plastics by 2030.",
        },
        "expected": "NOT_INTERESTING",
    },
    # More clear INTERESTING
    {
        "post": {
            "post_id": "r_011", "topic_query": "Python", "author_handle": "py_dev",
            "created_at": "1700000000", "post_url": "https://reddit.com/r/Python/r_011",
            "score": 780, "num_comments": 185,
            "text": "uv is now the fastest Python package manager. Full PEP 517 support, drops pip entirely. Benchmark inside.",
        },
        "expected": "INTERESTING",
    },
    {
        "post": {
            "post_id": "r_012", "topic_query": "LocalLLaMA", "author_handle": "oss_builder",
            "created_at": "1700000000", "post_url": "https://reddit.com/r/LocalLLaMA/r_012",
            "score": 390, "num_comments": 88,
            "text": "Open-source alternative to OpenAI Assistants API — fully self-hosted, supports function calling and file uploads.",
        },
        "expected": "INTERESTING",
    },
    {
        "post": {
            "post_id": "r_013", "topic_query": "MachineLearning", "author_handle": "vc_insider",
            "created_at": "1700000000", "post_url": "https://reddit.com/r/MachineLearning/r_013",
            "score": 650, "num_comments": 290,
            "text": "[D] Y Combinator W25 cohort — 30% of companies are AI agent startups. Thread on what's actually getting funded.",
        },
        "expected": "INTERESTING",
    },
    {
        "post": {
            "post_id": "r_014", "topic_query": "physics", "author_handle": "physics_nerd",
            "created_at": "1700000000", "post_url": "https://reddit.com/r/physics/r_014",
            "score": 1200, "num_comments": 340,
            "text": "Room-temperature superconductor claim peer reviewed and partially replicated. Nature paper link inside.",
        },
        "expected": "INTERESTING",
    },
    {
        "post": {
            "post_id": "r_015", "topic_query": "devops", "author_handle": "infra_eng",
            "created_at": "1700000000", "post_url": "https://reddit.com/r/devops/r_015",
            "score": 280, "num_comments": 62,
            "text": "We replaced Terraform with Pulumi for our entire AWS infra. Here's what surprised us after 6 months.",
        },
        "expected": "INTERESTING",
    },
]

CAPABILITY_SAMPLES = [
    # Edge case: tech topic but very low effort post
    {
        "post": {
            "post_id": "c_001", "topic_query": "LocalLLaMA", "author_handle": "newbie",
            "created_at": "1700000000", "post_url": "https://reddit.com/r/LocalLLaMA/c_001",
            "score": 30, "num_comments": 5,
            "text": "Can someone recommend a good LLM for a beginner?",
        },
        "expected": "NOT_INTERESTING",
    },
    # Edge case: LLM topic but clickbait title, no substance
    {
        "post": {
            "post_id": "c_002", "topic_query": "MachineLearning", "author_handle": "viral_poster",
            "created_at": "1700000000", "post_url": "https://reddit.com/r/MachineLearning/c_002",
            "score": 2100, "num_comments": 700,
            "text": "AI is going to change everything. GPT-5 is coming and it will be AGI. Buckle up.",
        },
        "expected": "NOT_INTERESTING",
    },
    # Edge case: K8s but purely a personal rant, no actionable info
    {
        "post": {
            "post_id": "c_003", "topic_query": "kubernetes", "author_handle": "frustrated_dev",
            "created_at": "1700000000", "post_url": "https://reddit.com/r/kubernetes/c_003",
            "score": 180, "num_comments": 44,
            "text": "I hate Kubernetes. It's overengineered garbage and you don't need it. Fight me.",
        },
        "expected": "NOT_INTERESTING",
    },
    # Edge case: startup/VC news — definitely in scope
    {
        "post": {
            "post_id": "c_004", "topic_query": "startups", "author_handle": "founder_anon",
            "created_at": "1700000000", "post_url": "https://reddit.com/r/startups/c_004",
            "score": 340, "num_comments": 120,
            "text": "We raised $2M pre-seed for an AI coding assistant built on open-source models. AMA.",
        },
        "expected": "INTERESTING",
    },
    # Edge case: Python but pure beginner question
    {
        "post": {
            "post_id": "c_005", "topic_query": "learnpython", "author_handle": "student_dev",
            "created_at": "1700000000", "post_url": "https://reddit.com/r/learnpython/c_005",
            "score": 55, "num_comments": 18,
            "text": "How do I reverse a string in Python? Is there a built-in?",
        },
        "expected": "NOT_INTERESTING",
    },
    # Edge case: physics + LLM crossover
    {
        "post": {
            "post_id": "c_006", "topic_query": "MachineLearning", "author_handle": "physics_ml",
            "created_at": "1700000000", "post_url": "https://reddit.com/r/MachineLearning/c_006",
            "score": 420, "num_comments": 95,
            "text": "[R] We used a transformer model to predict protein folding at 10x the speed of AlphaFold with similar accuracy.",
        },
        "expected": "INTERESTING",
    },
    # Edge case: cloud infra but a job posting
    {
        "post": {
            "post_id": "c_007", "topic_query": "devops", "author_handle": "hr_bot",
            "created_at": "1700000000", "post_url": "https://reddit.com/r/devops/c_007",
            "score": 15, "num_comments": 3,
            "text": "[Hiring] Senior DevOps Engineer at TechCorp. Remote. $150-180k. AWS, K8s, Terraform experience required.",
        },
        "expected": "NOT_INTERESTING",
    },
    # Edge case: Go + open source — borderline (new library, might be interesting)
    {
        "post": {
            "post_id": "c_008", "topic_query": "golang", "author_handle": "go_author",
            "created_at": "1700000000", "post_url": "https://reddit.com/r/golang/c_008",
            "score": 95, "num_comments": 28,
            "text": "I built a zero-allocation HTTP router for Go. 3x faster than chi in benchmarks. Feedback welcome.",
        },
        "expected": "INTERESTING",
    },
    # Edge case: AI topic but it's a meme/joke post
    {
        "post": {
            "post_id": "c_009", "topic_query": "LocalLLaMA", "author_handle": "meme_lord",
            "created_at": "1700000000", "post_url": "https://reddit.com/r/LocalLLaMA/c_009",
            "score": 1800, "num_comments": 220,
            "text": "Me: Please summarize this 10-page PDF. LLM: Sure! [writes 15 pages]",
        },
        "expected": "NOT_INTERESTING",
    },
    # Edge case: open-source tooling announcement
    {
        "post": {
            "post_id": "c_010", "topic_query": "programming", "author_handle": "oss_dev",
            "created_at": "1700000000", "post_url": "https://reddit.com/r/programming/c_010",
            "score": 210, "num_comments": 47,
            "text": "We open-sourced our internal developer platform — handles CI/CD, secrets, and preview environments. MIT license.",
        },
        "expected": "INTERESTING",
    },
]


def run_eval(samples: list[dict], tier_name: str, verbose: bool) -> tuple[int, int]:
    """Run eval on a list of samples. Returns (correct, total)."""
    correct = 0
    print(f"\n=== {tier_name} ({len(samples)} samples) ===")
    for s in samples:
        clf = _classify_post(s["post"])
        got = clf.get("classification", "NOT_INTERESTING")
        ok = got == s["expected"]
        if ok:
            correct += 1
        if verbose or not ok:
            status = "PASS" if ok else "FAIL"
            print(
                f"  [{status}] {s['post']['post_id']} "
                f"expected={s['expected']} got={got} conf={clf.get('confidence', 0):.2f}"
            )
            if not ok or verbose:
                print(f"         reason: {clf.get('reason', '')}")
    accuracy = correct / len(samples) if samples else 1.0
    print(f"  → {correct}/{len(samples)} correct ({accuracy:.0%})")
    return correct, len(samples)


def main() -> None:
    parser = argparse.ArgumentParser(description="Eval LLM classification accuracy on labeled sample posts")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print result for every sample")
    parser.add_argument(
        "--samples-file",
        help="Path to a JSON file with additional samples (list of {post, expected} objects)",
    )
    parser.add_argument(
        "--capability-threshold",
        type=float,
        default=0.70,
        help="Min pass rate for capability evals (default: 0.70)",
    )
    args = parser.parse_args()

    regression_samples = list(REGRESSION_SAMPLES)
    capability_samples = list(CAPABILITY_SAMPLES)

    if args.samples_file:
        with open(args.samples_file) as f:
            extra = json.load(f)
        for s in extra:
            if s.get("tier") == "capability":
                capability_samples.append(s)
            else:
                regression_samples.append(s)
        print(f"Loaded {len(extra)} samples from {args.samples_file}")

    failed = False

    reg_correct, reg_total = run_eval(regression_samples, "REGRESSION", args.verbose)
    if reg_correct < reg_total:
        print(f"\n[FAIL] Regression tier: {reg_total - reg_correct} failure(s) — must be 100%")
        failed = True

    cap_correct, cap_total = run_eval(capability_samples, "CAPABILITY", args.verbose)
    cap_acc = cap_correct / cap_total if cap_total else 1.0
    if cap_acc < args.capability_threshold:
        print(f"\n[FAIL] Capability tier: {cap_acc:.0%} < threshold {args.capability_threshold:.0%}")
        failed = True

    overall = reg_correct + cap_correct
    total = reg_total + cap_total
    print(f"\nOverall: {overall}/{total} ({overall/total:.0%})")

    if failed:
        sys.exit(1)
    print("All eval tiers passed.")


if __name__ == "__main__":
    main()
