"""SemanticCite backend for manuscript-citation-audit.

Optional second-opinion verifier. Runs a single citation/claim against a
single PDF using SemanticCite's ReferenceChecker and returns a JSON
object compatible with the skill's merge step.

Routes LLM calls through UF Navigator (OpenAI-compatible) by default,
so no Anthropic API key is required. Override by setting
OPENAI_API_BASE / OPENAI_API_KEY before running.

Usage
-----
    python semanticcite_backend.py \\
        --claim "<one-sentence claim from manuscript>" \\
        --pdf  /path/to/cited_paper.pdf \\
        [--model gpt-4.1-mini] \\
        [--out /path/to/result.json]

Prerequisites
-------------
- SemanticCite cloned at ~/semanticcite and its `cite` conda env built
  (see ~/semanticcite/README.md).
- A Navigator key at ~/.navigator_key (or OPENAI_API_KEY/OPENAI_API_BASE
  exported before running).
- Before invoking this script, activate the `cite` env and prepend the
  env's lib/ to LD_LIBRARY_PATH to avoid a libstdc++ ABI mismatch:

        module load conda
        conda activate cite
        export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$LD_LIBRARY_PATH"

Output schema
-------------
    {
      "backend": "semanticcite",
      "classification": "SUPPORTED" | "PARTIALLY_SUPPORTED" | "UNSUPPORTED" | "UNCERTAIN",
      "confidence": float in [0, 1],
      "reasoning": str,
      "claim": str,                    # LLM-extracted core claim
      "evidence": [                    # top chunks with locations
          {"text": str, "score": float, "chunk_id": int}, ...
      ],
      "runtime_sec": float,
      "model": str
    }
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


def configure_llm_from_env():
    """Set OPENAI_API_KEY / OPENAI_API_BASE for UF Navigator if the user
    hasn't already configured an alternative."""
    if os.environ.get("OPENAI_API_KEY"):
        return  # user provided their own
    nav = Path.home() / ".navigator_key"
    if nav.exists():
        os.environ["OPENAI_API_KEY"] = nav.read_text().strip()
    else:
        raise SystemExit(
            "No OPENAI_API_KEY and no ~/.navigator_key. "
            "Set OPENAI_API_KEY (and optionally OPENAI_API_BASE) "
            "before running."
        )
    os.environ.setdefault("OPENAI_API_BASE",
                          "https://api.ai.it.ufl.edu/v1")
    os.environ.setdefault("OPENAI_BASE_URL", os.environ["OPENAI_API_BASE"])


def load_pdf_text(pdf_path: str) -> str:
    import fitz  # PyMuPDF
    doc = fitz.open(pdf_path)
    return "\n".join(page.get_text("text") for page in doc)


def run(claim: str, pdf_path: str, model: str = "gpt-4.1-mini") -> dict:
    configure_llm_from_env()

    semanticcite_src = Path.home() / "semanticcite" / "src"
    if not semanticcite_src.is_dir():
        raise SystemExit(
            f"SemanticCite not found at {semanticcite_src}. "
            "Clone it: git clone https://github.com/sebhaan/semanticcite"
        )
    sys.path.insert(0, str(semanticcite_src))
    from citecheck import ReferenceChecker  # noqa: E402

    if not Path(pdf_path).is_file():
        raise FileNotFoundError(pdf_path)

    reference_text = load_pdf_text(pdf_path)

    checker = ReferenceChecker(
        llm_provider="openai",
        llm_config={
            "model": model,
            "temperature": 0.1,
            "api_key": os.environ["OPENAI_API_KEY"],
        },
        embedding_provider="local",
        embedding_config={"model_name": "all-mpnet-base-v2"},
    )

    t0 = time.time()
    raw = checker.check_citation(
        citation=claim, reference_text=reference_text, save_chunks=False,
    )
    runtime = time.time() - t0

    # Normalise label to our canonical set.
    cls = str(raw.get("classification", "UNCERTAIN")).upper()
    # SemanticCite sometimes uses "PARTIALLY SUPPORTED" or "PARTIAL".
    if "PARTIAL" in cls:
        cls = "PARTIALLY_SUPPORTED"
    elif cls not in ("SUPPORTED", "UNSUPPORTED", "UNCERTAIN"):
        cls = "UNCERTAIN"

    evidence = []
    for item in raw.get("evidence", []) or []:
        if isinstance(item, dict):
            loc = item.get("location", {}) or {}
            evidence.append({
                "text": item.get("text", ""),
                "score": float(item.get("rerank_score") or item.get("score") or 0.0),
                "chunk_id": int(loc.get("chunk_id", -1)),
            })

    return {
        "backend": "semanticcite",
        "classification": cls,
        "confidence": float(raw.get("confidence", 0.0)),
        "reasoning": raw.get("reasoning", ""),
        "claim": raw.get("claim", claim),
        "evidence": evidence,
        "runtime_sec": round(runtime, 1),
        "model": model,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--claim", required=True,
                    help="One-sentence claim from the manuscript.")
    ap.add_argument("--pdf", required=True,
                    help="Path to the cited paper PDF.")
    ap.add_argument("--model", default="gpt-4.1-mini")
    ap.add_argument("--out", default="-",
                    help="Output path for JSON; '-' prints to stdout.")
    args = ap.parse_args()

    result = run(args.claim, args.pdf, args.model)
    blob = json.dumps(result, indent=2)
    if args.out == "-":
        print(blob)
    else:
        Path(args.out).write_text(blob)
        print(f"Wrote: {args.out}")


if __name__ == "__main__":
    main()
