"""
test_trust_engine_v2.py — Test suite for trust_engine_v2
Run: python3 test_trust_engine_v2.py
"""

import sys
sys.path.insert(0, ".")

from trust_engine_v2 import run_trust_engine

# ── Test cases ────────────────────────────────────────────────────────────────

TESTS = [
    {
        "name": "Safe delete in dev (should NOT collapse)",
        "ticket": {
            "verb": "delete",
            "service": "s3",
            "env": "dev",
            "affected_nodes": [],
        },
        "expect_conf_range": (0.20, 0.35),
        "expect_decisions":  {"HUMAN_APPROVAL", "HARD_BLOCK"},
    },
    {
        "name": "Dangerous delete — prod IAM admin",
        "ticket": {
            "verb": "delete",
            "service": "iam",
            "env": "production",
            "scope": {"privilege_level": "admin"},
            "affected_nodes": ["ec2", "lambda", "cdn", "cloudwatch"],
        },
        "expect_conf_range": (0.01, 0.05),
        "expect_decisions":  {"HARD_BLOCK"},
    },
    {
        "name": "Medium risk delete — lambda in dev",
        "ticket": {
            "verb": "delete",
            "service": "lambda",
            "env": "dev",
            "affected_nodes": ["ec2", "cloudwatch"],
        },
        "expect_conf_range": (0.10, 0.25),
        "expect_decisions":  {"HUMAN_APPROVAL", "HARD_BLOCK"},
    },
    {
        "name": "Safe IAM attach — read_only in dev",
        "ticket": {
            "verb": "attach",
            "service": "iam",
            "env": "dev",
            "scope": {"privilege_level": "read_only"},
            "affected_nodes": ["ec2"],
        },
        "expect_conf_range": (0.80, 0.90),
        "expect_decisions":  {"AUTO_EXECUTE"},
    },
    {
        "name": "Scaling EC2 — unknown env",
        "ticket": {
            "verb": "scaling",
            "service": "ec2",
            "env": "unknown",
            "affected_nodes": ["alb", "cloudwatch"],
        },
        "expect_conf_range": (0.75, 0.85),
        "expect_decisions":  {"AUTO_EXECUTE", "HUMAN_APPROVAL"},
    },
]

# ── Runner ────────────────────────────────────────────────────────────────────

def run_tests():
    passed = 0
    failed = 0

    print("=" * 72)
    print("  trust_engine_v2 — Test Suite")
    print("=" * 72)

    for i, tc in enumerate(TESTS, 1):
        result = run_trust_engine(tc["ticket"])
        conf   = result["confidence"]
        dec    = result["decision"]

        lo, hi     = tc["expect_conf_range"]
        conf_ok    = lo <= conf <= hi
        dec_ok     = dec in tc["expect_decisions"]
        ok         = conf_ok and dec_ok

        status = "✓ PASS" if ok else "✗ FAIL"
        if ok:
            passed += 1
        else:
            failed += 1

        print(f"\n[{i}] {tc['name']}")
        print(f"     intent={result['intent_score']:.3f}  "
              f"rev={result['reversibility']:.3f}  "
              f"blast={result['blast_radius']:.3f}  "
              f"policy={result['policy_score']:.3f}")
        print(f"     confidence={conf:.4f}  decision={dec}")
        print(f"     expected conf∈[{lo},{hi}]  decision∈{tc['expect_decisions']}")
        print(f"     {status}", end="")

        if not conf_ok:
            print(f"  ← conf {conf:.4f} outside [{lo},{hi}]", end="")
        if not dec_ok:
            print(f"  ← decision '{dec}' not in {tc['expect_decisions']}", end="")
        print()

    print("\n" + "=" * 72)
    print(f"  {passed}/{len(TESTS)} passed  |  {failed}/{len(TESTS)} failed")
    print("=" * 72)
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
