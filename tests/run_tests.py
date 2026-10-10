#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sleeping Beauty Dress Firmware - Comprehensive E2E Test Suite Runner
Multi-Runtime Compatible: Python 2.7 and Python 3.x
Covers Tiers 1-4 for all 17 features (>=196 tests)
"""
from __future__ import print_function, division, absolute_import
import sys
import os
import time
import unittest

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def create_test_suite():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Discover tests in each tier directory
    tier1_dir = os.path.join(PROJECT_ROOT, "tests", "tier1_features")
    tier2_dir = os.path.join(PROJECT_ROOT, "tests", "tier2_boundaries")
    tier3_dir = os.path.join(PROJECT_ROOT, "tests", "tier3_cross_feature")
    tier4_dir = os.path.join(PROJECT_ROOT, "tests", "tier4_real_world")

    suite_t1 = loader.discover(tier1_dir, pattern="test_*.py", top_level_dir=PROJECT_ROOT)
    suite_t2 = loader.discover(tier2_dir, pattern="test_*.py", top_level_dir=PROJECT_ROOT)
    suite_t3 = loader.discover(tier3_dir, pattern="test_*.py", top_level_dir=PROJECT_ROOT)
    suite_t4 = loader.discover(tier4_dir, pattern="test_*.py", top_level_dir=PROJECT_ROOT)

    return suite_t1, suite_t2, suite_t3, suite_t4

class CustomTestResult(unittest.TestResult):
    def __init__(self, tier_name):
        super(CustomTestResult, self).__init__()
        self.tier_name = tier_name
        self.test_records = []

    def startTest(self, test):
        super(CustomTestResult, self).startTest(test)
        self._start_time = time.time()

    def addSuccess(self, test):
        super(CustomTestResult, self).addSuccess(test)
        elapsed = time.time() - self._start_time
        test_id = test.id().split(".")[-1]
        self.test_records.append((test_id, "PASS", elapsed, None))
        print("  [PASS] {:<50} ({:.3f}s)".format(test_id, elapsed))

    def addFailure(self, test, err):
        super(CustomTestResult, self).addFailure(test, err)
        elapsed = time.time() - self._start_time
        test_id = test.id().split(".")[-1]
        self.test_records.append((test_id, "FAIL", elapsed, err))
        print("  [FAIL] {:<50} ({:.3f}s)".format(test_id, elapsed))

    def addError(self, test, err):
        super(CustomTestResult, self).addError(test, err)
        elapsed = time.time() - self._start_time
        test_id = test.id().split(".")[-1]
        self.test_records.append((test_id, "ERROR", elapsed, err))
        print("  [ERROR] {:<50} ({:.3f}s)".format(test_id, elapsed))

def run_tier(tier_name, suite):
    print("\n" + "=" * 70)
    print("Executing {}:".format(tier_name))
    print("=" * 70)
    result = CustomTestResult(tier_name)
    start = time.time()
    suite.run(result)
    duration = time.time() - start
    passed = len(result.test_records) - len(result.failures) - len(result.errors)
    total = len(result.test_records)
    print("-" * 70)
    print("{}: {}/{} passed ({:.3f}s)".format(tier_name, passed, total, duration))
    return result, duration

def main():
    print("======================================================================")
    print("  SLEEPING BEAUTY DRESS FIRMWARE - COMPREHENSIVE E2E TEST RUNNER")
    print("  Target: Seeed Studio XIAO ESP32-C3 | Tiers 1-4 Verification")
    print("======================================================================")
    print("Python Runtime: {}".format(sys.version.split()[0]))
    print("Project Root:   {}".format(PROJECT_ROOT))

    suite_t1, suite_t2, suite_t3, suite_t4 = create_test_suite()

    total_start = time.time()
    res1, dur1 = run_tier("Tier 1: Feature Coverage (Features 1-17)", suite_t1)
    res2, dur2 = run_tier("Tier 2: Boundary & Corner Cases (Features 1-17)", suite_t2)
    res3, dur3 = run_tier("Tier 3: Cross-Feature Combinations", suite_t3)
    res4, dur4 = run_tier("Tier 4: Real-World Scenarios", suite_t4)
    total_duration = time.time() - total_start

    t1_pass = len(res1.test_records) - len(res1.failures) - len(res1.errors)
    t2_pass = len(res2.test_records) - len(res2.failures) - len(res2.errors)
    t3_pass = len(res3.test_records) - len(res3.failures) - len(res3.errors)
    t4_pass = len(res4.test_records) - len(res4.failures) - len(res4.errors)

    t1_total = len(res1.test_records)
    t2_total = len(res2.test_records)
    t3_total = len(res3.test_records)
    t4_total = len(res4.test_records)

    total_tests = t1_total + t2_total + t3_total + t4_total
    total_passed = t1_pass + t2_pass + t3_pass + t4_pass
    total_failures = len(res1.failures) + len(res2.failures) + len(res3.failures) + len(res4.failures)
    total_errors = len(res1.errors) + len(res2.errors) + len(res3.errors) + len(res4.errors)

    print("\n" + "=" * 70)
    print("                     E2E TEST SUITE SUMMARY")
    print("=" * 70)
    print("  Tier 1 (Feature Coverage):        {:>3} / {:>3} passed  ({:.3f}s)".format(t1_pass, t1_total, dur1))
    print("  Tier 2 (Boundary & Corner Cases): {:>3} / {:>3} passed  ({:.3f}s)".format(t2_pass, t2_total, dur2))
    print("  Tier 3 (Cross-Feature Combos):    {:>3} / {:>3} passed  ({:.3f}s)".format(t3_pass, t3_total, dur3))
    print("  Tier 4 (Real-World Scenarios):    {:>3} / {:>3} passed  ({:.3f}s)".format(t4_pass, t4_total, dur4))
    print("-" * 70)
    print("  TOTAL TESTS:                      {:>3} / {:>3} passed".format(total_passed, total_tests))
    print("  TOTAL DURATION:                   {:.3f}s".format(total_duration))
    print("  MINIMUM REQUIRED (>=196):         {} (met: {})".format(total_tests, "YES" if total_tests >= 196 else "NO"))

    if total_failures > 0 or total_errors > 0 or total_passed < total_tests:
        print("\n[RESULT]: FAIL - Some tests did not pass.")
        return 1
    else:
        print("\n[RESULT]: SUCCESS - All {} E2E tests passed cleanly!".format(total_tests))
        return 0

if __name__ == "__main__":
    sys.exit(main())
