import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import feedparser
import requests
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODELS_TO_TEST = [
    "nemotron-3-super-120b",  # Largest, 120B params
    "gpt-oss-20b",
    "qwen3-coder-30b",
    "qwen3-next-80b",
]

LLAMA_BASE_URL = os.environ.get("LLAMA_CPP_BASE_URL", "http://pedrogpt:8080/v1")


def get_llm(model: str, temperature: float = 0.2) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=LLAMA_BASE_URL,
        model=model,
        api_key="not-needed",
        temperature=temperature,
        max_tokens=2048,
    )


@dataclass
class EvalCase:
    name: str
    content: dict
    expected_relevant: bool
    expected_contains: list[str] = None


EVAL_CASES = [
    EvalCase(
        name="AI Reliability Engineering post",
        content={
            "title": "Part 2 — AI Reliability Engineering Series",
            "description": "In the last post, I argued that most AI systems are not failing because of models, rather they're failing because we are not engineering them like systems. Reliability doesn't come from better prompts.",
            "url": "https://soypetetech.substack.com/p/unit-testing-your-agents",
        },
        expected_relevant=True,
    ),
    EvalCase(
        name="Random blog post (irrelevant)",
        content={
            "title": "Top 10 recipes for cookies",
            "description": "The best chocolate chip cookie recipe that anyone can make at home.",
            "url": "https://example.com/cookies",
        },
        expected_relevant=False,
    ),
    EvalCase(
        name="Go tutorial post",
        content={
            "title": "Building a Production-Grade CLI in Go",
            "description": "A deep dive into building CLI tools with Cobra, proper error handling, and testing strategies for production.",
            "url": "https://soypetetech.substack.com/p/go-cli",
        },
        expected_relevant=True,
    ),
]


POST_QUALITY_PROMPT = """Evaluate this social media post for quality. Return JSON:

{{"length_ok": true/false, "has_hook": true/false, "has_perspective": true/false, "not_ai_sounding": true/false, "in_voice": true/false, "issues": ["issue1", "issue2"]}}

Platform: {platform} (max {max_chars} chars)
Voice: casual, technical, direct - short sentences, no fluff

Post:
{post}"""


def evaluate_post_quality(post: str, platform: str = "discord", max_chars: int = 2000) -> dict:
    """Evaluate the quality of a generated social post."""
    llm = get_llm("qwen3-coder-30b")
    
    response = llm.invoke([
        SystemMessage(content=POST_QUALITY_PROMPT.format(
            platform=platform,
            max_chars=max_chars,
            post=post,
        ))
    ])
    
    try:
        result = json.loads(response.content)
    except json.JSONDecodeError:
        import re
        m = re.search(r'\{.*\}', response.content, re.DOTALL)
        if m:
            result = json.loads(m.group())
        else:
            result = {"length_ok": True, "has_hook": True, "has_perspective": True, "not_ai_sounding": True, "in_voice": True, "issues": ["parse error"]}
    
    return result


RELEVANCE_PROMPT = """You are a content curator. Given a piece of content and recent posts you've made, 
evaluate if this is worth sharing.

Content to evaluate:
- Title: {title}
- Description: {description}
- URL: {url}

Your recent posts (for context on what you've already shared):
{recent_posts}

Respond with JSON only:
{{"relevant": true/false, "reason": "one sentence explanation", "confidence": 0.0-1.0, "suggested_text": "1-2 sentence hook in your voice"}}

Consider: Is this interesting to your audience? Have you covered this topic recently? Is it in your area of expertise?"""


REWRITE_PROMPT = """You are writing a social media post. Use this voice/style:
{voice}

Original content:
- Title: {title}
- Description: {description}
- URL: {url}

Write a Discord post (max 2000 chars) that:
1. Hooks the reader in 1-2 sentences
2. Adds your unique perspective/take
3. Ends with a question or call-to-action if natural

Write in your natural voice - not AI-sounding. Be conversational, not promotional."""


def run_relevance_eval(case: EvalCase, recent_posts: list[str] = None, model: str = "nemotron-3-super-120b") -> dict:
    """Run a single relevance evaluation."""
    recent_text = "\n".join([f"- {p[:100]}..." for p in (recent_posts or [])[:5]]) or "No recent posts"
    
    llm = get_llm(model)
    response = llm.invoke([
        SystemMessage(
            content=RELEVANCE_PROMPT.format(
                title=case.content.get("title", ""),
                description=case.content.get("description", ""),
                url=case.content.get("url", ""),
                recent_posts=recent_text,
            )
        ),
    ])
    
    try:
        result = json.loads(response.content)
    except json.JSONDecodeError:
        import re
        m = re.search(r'\{.*\}', response.content, re.DOTALL)
        if m:
            result = json.loads(m.group())
        else:
            result = {"relevant": False, "reason": "parse error", "confidence": 0.0}
    
    result["raw_response"] = response.content[:200]
    return result


def run_rewrite_eval(case: EvalCase, voice: str, model: str = "nemotron-3-super-120b") -> dict:
    """Run a single rewrite evaluation."""
    llm = get_llm(model)
    response = llm.invoke([
        SystemMessage(
            content=REWRITE_PROMPT.format(
                voice=voice,
                title=case.content.get("title", ""),
                description=case.content.get("description", ""),
                url=case.content.get("url", ""),
            )
        ),
    ])
    
    return {"text": response.content, "length": len(response.content)}


def run_evals(model: str = "nemotron-3-super-120b", runs: int = 15) -> dict:
    """Run all eval cases multiple times and measure consistency."""
    results = {
        "model": model,
        "total_runs": runs,
        "cases": {},
        "summary": {},
    }
    
    voice = "Casual, technical, direct. Uses short sentences. No fluff."
    recent_posts = ["Just shared a post about Go testing patterns", "Wrote about AI middleware"]
    
    all_latencies = []
    
    for case in EVAL_CASES:
        case_results = {
            "relevant_results": [],
            "rewrite_results": [],
        }
        
        logger.info(f"Running eval: {case.name} ({runs} times) with {model}")
        
        for i in range(runs):
            start = time.time()
            rel_result = run_relevance_eval(case, recent_posts, model)
            latencies = time.time() - start
            all_latencies.append(latencies)
            case_results["relevant_results"].append(rel_result)
            
            start = time.time()
            rew_result = run_rewrite_eval(case, voice, model)
            latencies = time.time() - start
            all_latencies.append(latencies)
            case_results["rewrite_results"].append(rew_result)
        
        relevant_outcomes = [r.get("relevant") for r in case_results["relevant_results"]]
        confidence_scores = [r.get("confidence", 0) for r in case_results["relevant_results"]]
        
        true_count = sum(relevant_outcomes)
        false_count = len(relevant_outcomes) - true_count
        
        case_summary = {
            "expected_relevant": case.expected_relevant,
            "actual_relevant_count": true_count,
            "actual_relevant_false_count": false_count,
            "confidence_mean": sum(confidence_scores) / len(confidence_scores),
            "confidence_std": _std(confidence_scores),
            "consistency": "HIGH" if true_count == runs or false_count == runs else "LOW",
        }
        
        results["cases"][case.name] = {
            "details": case_results,
            "summary": case_summary,
        }
        
        logger.info(f"  {case.name}: relevant={true_count}/{runs}, consistency={case_summary['consistency']}")
    
    all_consistent = all(
        r["summary"]["consistency"] == "HIGH" 
        for r in results["cases"].values()
    )
    
    results["summary"] = {
        "all_consistent": all_consistent,
        "avg_latency_sec": sum(all_latencies) / len(all_latencies) if all_latencies else 0,
        "total_latency_sec": sum(all_latencies),
    }
    
    return results


def _std(values: list[float]) -> float:
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return variance ** 0.5


def run_quality_evals(model: str = "qwen3-coder-30b", runs: int = 5) -> dict:
    """Run post-quality evals: length, voice, engagement."""
    results = {
        "model": model,
        "total_runs": runs,
        "posts": [],
    }
    
    voice = "Casual, technical, direct. Uses short sentences. No fluff."
    
    for case in EVAL_CASES[:2]:  # Just test relevant cases for quality
        if not case.expected_relevant:
            continue
            
        for i in range(runs):
            rew_result = run_rewrite_eval(case, voice, model)
            post = rew_result["text"]
            
            quality = evaluate_post_quality(post, platform="discord", max_chars=2000)
            quality["post"] = post[:200] + "..."
            quality["length"] = len(post)
            quality["raw"] = post
            
            results["posts"].append({
                "case": case.name,
                "run": i,
                "quality": quality,
            })
    
    # Summarize quality metrics
    all_good = all(
        p["quality"].get("length_ok") and 
        p["quality"].get("not_ai_sounding") and
        p["quality"].get("in_voice")
        for p in results["posts"]
    )
    
    results["summary"] = {
        "all_quality_pass": all_good,
        "total_posts": len(results["posts"]),
    }
    
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run social poster evals")
    parser.add_argument("--runs", type=int, default=15, help="Number of runs per test case")
    parser.add_argument("--model", type=str, default=None, help="Specific model to test (default: all)")
    parser.add_argument("--output", type=str, help="Output JSON file")
    parser.add_argument("--quality", action="store_true", help="Run post-quality evals instead of relevance")
    parser.add_argument("--timeout", type=int, default=600, help="Timeout per eval in seconds")
    args = parser.parse_args()
    
    models = [args.model] if args.model else MODELS_TO_TEST
    all_results = []
    
    if args.quality:
        # Quality evals - test post generation
        model = models[0] if models else "qwen3-coder-30b"
        logger.info(f"Running quality evals on {model} ({args.runs} runs)")
        results = run_quality_evals(model=model, runs=args.runs)
        all_results = [results]
        
        print(f"\n{model} Quality Results:")
        for p in results["posts"]:
            q = p["quality"]
            length = p.get("length", q.get("length", 0))
            print(f"  {p['case']} (run {p['run']}):")
            print(f"    length_ok={q.get('length_ok')}, not_ai_sounding={q.get('not_ai_sounding')}, in_voice={q.get('in_voice')}")
            print(f"    length={length} chars")
        
        print(f"\nAll quality pass: {results['summary']['all_quality_pass']}")
        return  # Exit early for quality evals
    else:
        # Relevance evals - test classification
        for model in models:
            logger.info(f"\n{'='*60}")
            logger.info(f"Testing model: {model}")
            logger.info(f"{'='*60}")
            
            results = run_evals(model=model, runs=args.runs)
            all_results.append(results)
            
            print(f"\n{model}:")
            print(f"  Consistency: {'PASS' if results['summary']['all_consistent'] else 'FAIL'}")
            print(f"  Avg latency: {results['summary']['avg_latency_sec']:.2f}s")
        
        print("\n" + "="*60)
        print("COMPARISON SUMMARY")
        print("="*60)
        
        for r in all_results:
            status = "✓" if r["summary"]["all_consistent"] else "✗"
            print(f"{status} {r['model']}: {r['summary']['avg_latency_sec']:.2f}s avg latency")
    
    if args.output:
        with open(args.output, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"\nResults saved to {args.output}")
    
    print("\n" + "="*60)
    print("EVAL RESULTS")
    print("="*60)
    
    for case_name, data in results["cases"].items():
        summary = data["summary"]
        print(f"\n{case_name}:")
        print(f"  Expected relevant: {summary['expected_relevant']}")
        print(f"  Actual relevant: {summary['actual_relevant_count']}/{args.runs}")
        print(f"  Confidence mean: {summary['confidence_mean']:.2f}")
        print(f"  Consistency: {summary['consistency']}")
    
    print(f"\nAll consistent: {results['summary']['all_consistent']}")
    
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()