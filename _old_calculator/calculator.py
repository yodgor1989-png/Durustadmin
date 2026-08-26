"""Xavfsiz matematik ifodalarni hisoblovchi modul.

eval() ishlatilmaydi - ifoda AST (abstract syntax tree) ga aylantirilib,
faqat ruxsat etilgan tugunlar (sonlar, amallar, funksiyalar) bajariladi.
Bu foydalanuvchi zararli kod yubora olmasligini kafolatlaydi.
"""

import ast
import math
import operator
import re


class CalcError(Exception):
    """Hisoblashdagi xatolik (foydalanuvchiga ko'rsatiladigan matn bilan)."""


# Ruxsat etilgan binar amallar
_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

# Ruxsat etilgan unar amallar
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _as_int(x):
    """Butun son kutilgan joyda float -> int (agar u haqiqatan butun bo'lsa)."""
    if isinstance(x, bool):
        raise CalcError("Noto'g'ri argument turi.")
    if isinstance(x, int):
        return x
    if isinstance(x, float) and x.is_integer():
        return int(x)
    raise CalcError("Bu funksiya faqat butun son qabul qiladi.")


def _cbrt(x):
    return math.copysign(abs(x) ** (1 / 3), x)


# Ruxsat etilgan funksiyalar
_FUNCS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sqrt": math.sqrt,
    "cbrt": _cbrt,
    "pow": math.pow,
    "exp": math.exp,
    "log": math.log,          # log(x) yoki log(x, asos)
    "log2": math.log2,
    "log10": math.log10,
    "ln": math.log,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "sinh": math.sinh,
    "cosh": math.cosh,
    "tanh": math.tanh,
    "degrees": math.degrees,
    "radians": math.radians,
    "floor": math.floor,
    "ceil": math.ceil,
    "trunc": math.trunc,
    "factorial": lambda x: math.factorial(_as_int(x)),
    "gcd": lambda a, b: math.gcd(_as_int(a), _as_int(b)),
    "lcm": lambda a, b: math.lcm(_as_int(a), _as_int(b)),
    "hypot": math.hypot,
}

# Ruxsat etilgan doimiylar
_CONSTS = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
}

# Foydalanuvchi qulayligi uchun almashtiriladigan belgilar
_REPLACEMENTS = [
    ("×", "*"),   # ×
    ("·", "*"),   # ·
    ("х", "*"),   # kirill "x"
    ("÷", "/"),   # ÷
    (":", "/"),
    ("−", "-"),   # minus
    ("–", "-"),   # en dash
    ("—", "-"),   # em dash
    ("^", "**"),
    ("π", "pi"),    # π
    (" ", ""),      # uzilmas probel
    (" ", ""),
]

# "√16" -> "sqrt(16)" uchun
_SQRT_NUM_RE = re.compile(r"√\s*(\d+(?:\.\d+)?)")
# "3,5" kabi o'nlik vergul (ikki raqam orasidagi vergul) uchun
_DECIMAL_COMMA_RE = re.compile(r"(?<=\d),(?=\d)")
# Ifodada funksiya nomi bormi? (bo'lsa, vergul - argument ajratgichi)
_HAS_FUNC_RE = re.compile(r"[A-Za-z_]\w*\s*\(")

MAX_EXPR_LEN = 200          # ifoda uzunligi chegarasi
MAX_POW_EXPONENT = 1000     # darajaning maksimal ko'rsatkichi
MAX_FACTORIAL = 1000        # faktorial chegarasi


def normalize(expr):
    """Foydalanuvchi kiritgan matnni Python sintaksisiga moslashtiradi."""
    expr = expr.strip()

    # √ belgisi: "√16" -> "sqrt(16)", "√(2+2)" -> "sqrt(2+2)"
    expr = _SQRT_NUM_RE.sub(lambda m: "sqrt(%s)" % m.group(1), expr)
    expr = expr.replace("√", "sqrt")

    for src, dst in _REPLACEMENTS:
        expr = expr.replace(src, dst)

    # Vergul: agar ifodada funksiya chaqiruvi bo'lmasa - o'nlik ajratgich
    # ("3,5" -> "3.5"). Aks holda u argumentlarni ajratadi ("max(3, 9)").
    if not _HAS_FUNC_RE.search(expr):
        expr = _DECIMAL_COMMA_RE.sub(".", expr)

    # "50%" -> "50/100" (raqamdan keyin kelgan va operanddan oldin turmagan %)
    out = []
    i = 0
    while i < len(expr):
        ch = expr[i]
        if ch == "%":
            prev = expr[i - 1] if i else ""
            nxt = expr[i + 1] if i + 1 < len(expr) else ""
            if (prev.isdigit() or prev == ")") and (nxt == "" or nxt in "+-*/)"):
                out.append("/100")
                i += 1
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def _eval_node(node):
    """AST tugunini rekursiv hisoblaydi."""
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise CalcError("Faqat sonlar bilan ishlayman.")
        return node.value

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _BIN_OPS:
            raise CalcError("Bu amal qo'llab-quvvatlanmaydi.")
        left = _eval_node(node.left)
        right = _eval_node(node.right)

        if op_type in (ast.Div, ast.FloorDiv, ast.Mod) and right == 0:
            raise CalcError("Nolga bo'lish mumkin emas.")
        if op_type is ast.Pow and abs(right) > MAX_POW_EXPONENT:
            raise CalcError("Daraja ko'rsatkichi juda katta (max %d)." % MAX_POW_EXPONENT)

        try:
            return _BIN_OPS[op_type](left, right)
        except ZeroDivisionError:
            raise CalcError("Nolga bo'lish mumkin emas.")
        except OverflowError:
            raise CalcError("Natija juda katta.")
        except ValueError as exc:
            raise CalcError("Matematik xato: %s" % exc)

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _UNARY_OPS:
            raise CalcError("Bu amal qo'llab-quvvatlanmaydi.")
        return _UNARY_OPS[op_type](_eval_node(node.operand))

    if isinstance(node, ast.Name):
        if node.id in _CONSTS:
            return _CONSTS[node.id]
        raise CalcError("Noma'lum belgi: %s" % node.id)

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise CalcError("Noto'g'ri funksiya chaqiruvi.")
        name = node.func.id
        if name not in _FUNCS:
            raise CalcError("Noma'lum funksiya: %s" % name)
        if node.keywords:
            raise CalcError("Funksiyaga nomli argument berib bo'lmaydi.")

        args = [_eval_node(a) for a in node.args]
        if name == "factorial" and args and args[0] > MAX_FACTORIAL:
            raise CalcError("Faktorial juda katta (max %d)." % MAX_FACTORIAL)

        try:
            return _FUNCS[name](*args)
        except CalcError:
            raise
        except ZeroDivisionError:
            raise CalcError("Nolga bo'lish mumkin emas.")
        except (ValueError, OverflowError) as exc:
            raise CalcError("'%s' uchun noto'g'ri qiymat: %s" % (name, exc))
        except TypeError:
            raise CalcError("'%s' funksiyasiga argumentlar soni noto'g'ri." % name)

    raise CalcError("Ifodada ruxsat etilmagan qism bor.")


def evaluate(expr):
    """Matnli ifodani hisoblab, son qaytaradi. Xatoda CalcError ko'taradi."""
    if not expr or not expr.strip():
        raise CalcError("Ifoda bo'sh.")
    if len(expr) > MAX_EXPR_LEN:
        raise CalcError("Ifoda juda uzun (max %d belgi)." % MAX_EXPR_LEN)

    cleaned = normalize(expr)
    if not cleaned:
        raise CalcError("Ifoda bo'sh.")

    try:
        tree = ast.parse(cleaned, mode="eval")
    except SyntaxError:
        raise CalcError("Ifoda noto'g'ri yozilgan. Masalan: 2 + 2 * 3")

    result = _eval_node(tree)

    if isinstance(result, complex):
        raise CalcError("Natija kompleks son - qo'llab-quvvatlanmaydi.")
    if isinstance(result, float):
        if math.isnan(result):
            raise CalcError("Natija aniqlanmagan (NaN).")
        if math.isinf(result):
            raise CalcError("Natija cheksizlikka teng.")
    return result


def _group(num_text):
    """1234567 -> '1 234 567' (mingliklarni probel bilan ajratish)."""
    negative = num_text.startswith("-")
    digits = num_text.lstrip("-")
    grouped = "{:,}".format(int(digits)).replace(",", " ")
    return ("-" + grouped) if negative else grouped


def format_result(value):
    """Natijani chiroyli matn ko'rinishida qaytaradi."""
    if isinstance(value, int):
        return _group(str(value))

    if isinstance(value, float):
        # Butun songa juda yaqin bo'lsa - butun ko'rinishda chiqaramiz
        if abs(value) < 1e15 and abs(value - round(value)) < 1e-12:
            return _group(str(int(round(value))))
        if value != 0 and (abs(value) >= 1e12 or abs(value) < 1e-6):
            return "{:.10g}".format(value)
        text = "{:.10f}".format(value).rstrip("0").rstrip(".")
        if "." in text:
            whole, frac = text.split(".")
            return _group(whole) + "." + frac
        return _group(text)

    return str(value)


def calculate(expr):
    """Ifodani hisoblab, formatlangan natija matnini qaytaradi."""
    return format_result(evaluate(expr))
