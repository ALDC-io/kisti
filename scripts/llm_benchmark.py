#!/usr/bin/env python3
"""KiSTI — LLM Benchmark: compare models on Jetson Orin Nano.

Runs a set of driving-context prompts through Ollama and records:
  - Time to first token (TTFT)
  - Total response time
  - Token count
  - Full response text (for quality evaluation)

Usage:
    python3 scripts/llm_benchmark.py --model llama3.2:3b --runs 3
    python3 scripts/llm_benchmark.py --model gemma4:e4b --runs 3
    python3 scripts/llm_benchmark.py --compare  # runs both, saves comparison
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
BENCHMARKS_DIR = Path(__file__).parent.parent / "benchmarks"

# KiSTI system prompt (matches voice/llm_engine.py)
SYSTEM_PROMPT = (
    "You are KiSTI, an AI co-driver in a 2014 Subaru STI. "
    "Keep responses under 2 sentences. Be direct, concise, useful for driving. "
    "You have access to: IMU G-forces, FLIR road surface temps, weather data, "
    "DCCD center diff lock, wheel speeds, and barometric pressure."
)

# 20 driving-context prompts covering KiSTI's domain
PROMPTS = [
    # Persona / conversational
    "How's the road looking?",
    "What's the weather doing?",
    "Tell me about the car",
    "What's the grip like right now?",
    "Are we safe to push harder?",
    # Technical / sensor queries
    "What does high DCCD lock percentage mean?",
    "Why is the road surface cold?",
    "Explain trail braking in one sentence",
    "What causes understeer in an AWD car?",
    "How does barometric pressure affect driving?",
    # Situational awareness
    "It's raining, what should I watch for?",
    "The road temp just dropped below zero",
    "I see fog ahead, any advice?",
    "We're entering a canyon, what changes?",
    "The G-force shows I'm braking too hard",
    # Short factual
    "What's the STI's DCCD system?",
    "How many G's is normal cornering?",
    "What's a good tire pressure for rain?",
    "Difference between understeer and oversteer?",
    "What does the FLIR camera see?",
]

# 15 quality-evaluation prompts (subset for blind A/B)
QUALITY_PROMPTS = PROMPTS[:15]


def _ollama_chat(model: str, prompt: str, max_tokens: int = 64) -> dict:
    """Call Ollama chat API and measure timing."""
    import urllib.request
    import urllib.error

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "stream": True,
        "options": {
            "num_predict": max_tokens,
            "temperature": 0.4,
        },
    }).encode()

    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    t_start = time.perf_counter()
    t_first_token = None
    response_text = ""
    token_count = 0

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            for line in resp:
                chunk = json.loads(line)
                msg = chunk.get("message", {})
                content = msg.get("content", "")
                if content and t_first_token is None:
                    t_first_token = time.perf_counter()
                response_text += content
                if content:
                    token_count += 1  # approximate: one chunk ≈ one token
                if chunk.get("done"):
                    break
    except Exception as exc:
        return {
            "error": str(exc),
            "prompt": prompt,
            "model": model,
        }

    t_end = time.perf_counter()

    return {
        "model": model,
        "prompt": prompt,
        "response": response_text.strip(),
        "ttft_ms": round((t_first_token - t_start) * 1000, 1) if t_first_token else None,
        "total_ms": round((t_end - t_start) * 1000, 1),
        "tokens": token_count,
        "max_tokens": max_tokens,
    }


def run_benchmark(model: str, runs: int = 3, max_tokens: int = 64) -> list[dict]:
    """Run all prompts through a model, multiple times."""
    results = []
    for run_idx in range(runs):
        print(f"  Run {run_idx + 1}/{runs}...")
        for i, prompt in enumerate(PROMPTS):
            result = _ollama_chat(model, prompt, max_tokens)
            result["run"] = run_idx + 1
            result["prompt_idx"] = i
            results.append(result)
            # Brief pause between prompts to avoid thermal throttling
            if i < len(PROMPTS) - 1:
                time.sleep(0.5)
        print(f"  Run {run_idx + 1} complete.")
    return results


def save_results(results: list[dict], model: str, label: str = "") -> Path:
    """Save benchmark results to JSON."""
    out_dir = BENCHMARKS_DIR / "latency"
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_name = model.replace(":", "_").replace("/", "_")
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{safe_name}_{ts}.json" if not label else f"{label}_{ts}.json"
    out_path = out_dir / filename

    summary = {
        "model": model,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prompt_count": len(PROMPTS),
        "runs": len(set(r.get("run", 1) for r in results)),
        "results": results,
    }

    # Compute aggregates (exclude errors)
    valid = [r for r in results if "error" not in r and r.get("ttft_ms")]
    if valid:
        summary["aggregates"] = {
            "avg_ttft_ms": round(sum(r["ttft_ms"] for r in valid) / len(valid), 1),
            "avg_total_ms": round(sum(r["total_ms"] for r in valid) / len(valid), 1),
            "min_ttft_ms": round(min(r["ttft_ms"] for r in valid), 1),
            "max_ttft_ms": round(max(r["ttft_ms"] for r in valid), 1),
            "avg_tokens": round(sum(r["tokens"] for r in valid) / len(valid), 1),
            "error_count": len(results) - len(valid),
        }

    out_path.write_text(json.dumps(summary, indent=2))
    print(f"Results saved: {out_path}")
    return out_path


def generate_quality_pairs(
    results_a: list[dict], results_b: list[dict],
    model_a: str, model_b: str,
) -> Path:
    """Generate blind A/B quality evaluation pairs."""
    import random

    out_dir = BENCHMARKS_DIR / "quality"
    out_dir.mkdir(parents=True, exist_ok=True)

    pairs = []
    # Use first run of each model for quality comparison
    a_run1 = [r for r in results_a if r.get("run") == 1 and "error" not in r]
    b_run1 = [r for r in results_b if r.get("run") == 1 and "error" not in r]

    for i, prompt in enumerate(QUALITY_PROMPTS):
        a_resp = next((r for r in a_run1 if r.get("prompt_idx") == i), None)
        b_resp = next((r for r in b_run1 if r.get("prompt_idx") == i), None)
        if not a_resp or not b_resp:
            continue

        # Randomize which is "Response 1" vs "Response 2"
        coin = random.random() > 0.5
        pairs.append({
            "prompt_idx": i,
            "prompt": prompt,
            "response_1": a_resp["response"] if coin else b_resp["response"],
            "response_2": b_resp["response"] if coin else a_resp["response"],
            "response_1_is": model_a if coin else model_b,
            "response_2_is": model_b if coin else model_a,
            "winner": "",  # JK fills this in
            "notes": "",
        })

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"quality_pairs_{ts}.json"
    out_path.write_text(json.dumps({"pairs": pairs}, indent=2))
    print(f"Quality pairs saved: {out_path} ({len(pairs)} pairs)")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="KiSTI LLM Benchmark")
    parser.add_argument("--model", type=str, default="llama3.2:3b",
                        help="Model to benchmark")
    parser.add_argument("--runs", type=int, default=3,
                        help="Number of benchmark runs")
    parser.add_argument("--max-tokens", type=int, default=64,
                        help="Max tokens per response")
    parser.add_argument("--compare", action="store_true",
                        help="Run both llama3.2:3b and gemma4:e4b")
    args = parser.parse_args()

    if args.compare:
        models = ["llama3.2:3b", "gemma4:e4b"]
        all_results = {}
        for model in models:
            print(f"\n{'='*60}")
            print(f"Benchmarking: {model}")
            print(f"{'='*60}")
            results = run_benchmark(model, args.runs, args.max_tokens)
            save_results(results, model)
            all_results[model] = results

        # Print comparison summary
        print(f"\n{'='*60}")
        print("COMPARISON SUMMARY")
        print(f"{'='*60}")
        for model, results in all_results.items():
            valid = [r for r in results if "error" not in r and r.get("ttft_ms")]
            if valid:
                avg_ttft = sum(r["ttft_ms"] for r in valid) / len(valid)
                avg_total = sum(r["total_ms"] for r in valid) / len(valid)
                print(f"  {model}: TTFT={avg_ttft:.0f}ms  Total={avg_total:.0f}ms  "
                      f"({len(valid)} valid / {len(results)} total)")

        # Generate quality pairs
        if len(all_results) == 2:
            m_a, m_b = models
            generate_quality_pairs(
                all_results[m_a], all_results[m_b], m_a, m_b,
            )
    else:
        print(f"Benchmarking: {args.model} ({args.runs} runs, {args.max_tokens} max tokens)")
        results = run_benchmark(args.model, args.runs, args.max_tokens)
        save_results(results, args.model)

        valid = [r for r in results if "error" not in r and r.get("ttft_ms")]
        if valid:
            avg_ttft = sum(r["ttft_ms"] for r in valid) / len(valid)
            avg_total = sum(r["total_ms"] for r in valid) / len(valid)
            print(f"\nSummary: TTFT={avg_ttft:.0f}ms  Total={avg_total:.0f}ms  "
                  f"({len(valid)} valid / {len(results)} total)")


if __name__ == "__main__":
    main()
