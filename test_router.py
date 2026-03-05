"""Test that routing sends queries to the right agent."""
import sys
sys.path.insert(0, ".")

from agents.router import route

tests = [
    ("What is a rApp?", "generic"),
    ("Why did my session fail?", "debugger"),
    ("Explain the BDT engine", "generic"),
    ("There is an error in my logs", "debugger"),
    ("What is CCO optimization?", "generic"),
    ("My worker crashed", "debugger"),
]

print("Router test results:")
print("-" * 40)
all_passed = True
for query, expected in tests:
    result = route(query)
    status = "✓ PASS" if result == expected else "✗ FAIL"
    if result != expected:
        all_passed = False
    print(f"{status} | Expected: {expected} | Got: {result}")
    print(f"       Query: {query}")
print("-" * 40)
print("All passed!" if all_passed else "Some tests failed — check router keywords")