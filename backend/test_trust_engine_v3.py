"""
test_trust_engine_v3.py — Test suite for trust_engine_v3
Run: python3 test_trust_engine_v3.py
"""

import sys
sys.path.insert(0, ".")

from trust_engine_v3 import run_trust_engine

TESTS = [
    {
        "name": "Safe delete in dev (should NOT collapse)",
        "ticket": {"verb": "delete", "service": "s3", "env": "dev", "affected_nodes": []},
        "expect_conf_range": (0.20, 0.35),
        "expect_decisions":  {"HUMAN_APPROVAL", "HARD_BLOCK"},
    },
    {
        "name": "Dangerous delete — prod IAM admin",
        "ticket": {
            "verb": "delete", "service": "iam", "env": "production",
            "scope": {"privilege_level": "admin"},
            "affected_nodes": ["ec2", "lambda", "cdn", "cloudwatch"],
        },
        "expect_conf_range": (0.01, 0.05),
        "expect_decisions":  {"HARD_BLOCK"},
    },
    {
        "name": "Medium risk delete — lambda in dev",
        "ticket": {"verb": "delete", "service": "lambda", "env": "dev",
                   "affected_nodes": ["ec2", "cloudwatch"]},
        "expect_conf_range": (0.10, 0.25),
        "expect_decisions":  {"HUMAN_APPROVAL", "HARD_BLOCK"},
    },
    {
        "name": "Safe IAM attach — read_only in dev",
        "ticket": {
            "verb": "attach", "service": "iam", "env": "dev",
            "scope": {"privilege_level": "read_only"},
            "affected_nodes": ["ec2"],
        },
        "expect_conf_range": (0.80, 0.90),
        "expect_decisions":  {"AUTO_EXECUTE"},
    },
    {
        "name": "Scaling EC2 — unknown env",
        "ticket": {"verb": "scaling", "service": "ec2", "env": "unknown",
                   "affected_nodes": ["alb", "cloudwatch"]},
        "expect_conf_range": (0.75, 0.85),
        "expect_decisions":  {"AUTO_EXECUTE", "HUMAN_APPROVAL"},
    },
]


def run_tests():
    passed = failed = 0
    print("=" * 72)
    print("  trust_engine_v3 — Test Suite")
    print("=" * 72)

    for i, tc in enumerate(TESTS, 1):
        r      = run_trust_engine(tc["ticket"])
        conf   = r["confidence"]
        dec    = r["decision"]
        lo, hi = tc["expect_conf_range"]
        ok     = (lo <= conf <= hi) and (dec in tc["expect_decisions"])

        if ok:
            passed += 1
        else:
            failed += 1

        print(f"\n[{i}] {tc['name']}")
        print(f"     intent={r['intent_score']:.3f}  rev={r['reversibility']:.3f}  "
              f"blast={r['blast_radius']:.3f}  policy={r['policy_score']:.3f}")
        print(f"     raw={r['raw_confidence']:.4f}  final={conf:.4f}  decision={dec}")
        print(f"     expected conf∈[{lo},{hi}]  decision∈{tc['expect_decisions']}")
        status = "✓ PASS" if ok else "✗ FAIL"
        print(f"     {status}", end="")
        if not (lo <= conf <= hi):
            print(f"  ← conf {conf:.4f} outside [{lo},{hi}]", end="")
        if dec not in tc["expect_decisions"]:
            print(f"  ← decision '{dec}' not in {tc['expect_decisions']}", end="")
        print()

    print(f"\n{'=' * 72}")
    print(f"  {passed}/{len(TESTS)} passed  |  {failed}/{len(TESTS)} failed")
    print("=" * 72)
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if run_tests() else 1)
