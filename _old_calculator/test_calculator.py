"""calculator.py uchun oddiy testlar. Ishga tushirish:  python test_calculator.py"""

import math

from calculator import CalcError, calculate, evaluate

OK = [
    ("2+2", 4),
    ("2 + 2 * 3", 8),
    ("(15 + 5) / 4", 5),
    ("10 // 3", 3),
    ("10 % 3", 1),
    ("2^10", 1024),
    ("2**10", 1024),
    ("sqrt(144)", 12),
    ("-5 + 3", -2),
    ("12 × 3", 36),
    ("100 ÷ 4", 25),
    ("3,5 + 1,5", 5),
    ("50%", 0.5),
    ("25% * 200", 50),
    ("factorial(5)", 120),
    ("abs(-7)", 7),
    ("max(3, 9, 5)", 9),
    ("gcd(12, 18)", 6),
    ("round(3.14159, 2)", 3.14),
    ("sin(pi/2)", 1),
    ("log10(1000)", 3),
    ("cbrt(27)", 3),
    ("√16", 4),
]

FAIL = [
    "1/0",
    "10 % 0",
    "__import__('os').system('dir')",
    "open('x')",
    "2 +",
    "",
    "abc",
    "2**99999",
    "factorial(100000)",
    "[1,2,3]",
    "lambda: 1",
    "x = 5",
]


def main():
    passed = failed = 0

    for expr, expected in OK:
        try:
            got = evaluate(expr)
        except Exception as exc:
            print("XATO  %-24r -> istisno: %s" % (expr, exc))
            failed += 1
            continue
        if math.isclose(got, expected, rel_tol=1e-9, abs_tol=1e-9):
            print("OK    %-24r = %s" % (expr, calculate(expr)))
            passed += 1
        else:
            print("XATO  %-24r -> %s (kutilgan %s)" % (expr, got, expected))
            failed += 1

    for expr in FAIL:
        try:
            got = evaluate(expr)
        except CalcError as exc:
            print("OK    %-24r -> rad etildi: %s" % (expr, exc))
            passed += 1
        except Exception as exc:
            print("XATO  %-24r -> noto'g'ri istisno turi: %r" % (expr, exc))
            failed += 1
        else:
            print("XATO  %-24r -> qabul qilindi (%s), rad etilishi kerak edi" % (expr, got))
            failed += 1

    print("\nNatija: %d ta o'tdi, %d ta xato" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
