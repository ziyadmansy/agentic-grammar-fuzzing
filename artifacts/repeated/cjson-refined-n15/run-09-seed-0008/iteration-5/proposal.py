from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON tokens
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with safe codepoints and escapes
    # We'll generate Python strings and then JSON-encode them to ensure correctness.
    # But since we cannot import json or use eval/exec, we build strings manually.
    # Instead, generate strings with safe characters and escapes.
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and quotes/backslash)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # Escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
        simple_escapes = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape: \uXXXX where X is hex digit
        hex_digit = st.characters('0123456789abcdefABCDEF')
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))

        # Compose string pieces: either safe char, simple escape, or unicode escape
        piece = st.one_of(
            safe_chars.map(lambda c: c),
            simple_escapes,
            unicode_escape
        )
        # Generate list of pieces (length 0 to 20)
        pieces = st.lists(piece, max_size=20)
        # Join and wrap in quotes
        return pieces.map(lambda ps: '"' + ''.join(ps) + '"')

    json_string_strat = json_string()

    # NUMBER strategy: generate numbers matching grammar
    # We'll generate floats and ints and convert to strings matching JSON number grammar
    def json_number():
        # Generate int part
        int_part = st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        # Optional fraction
        fraction = st.one_of(
            st.just(""),
            st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False)
            .map(lambda f: ("%.10f" % f).lstrip("0") if f > 0 else "")
            .filter(lambda s: s.startswith('.'))
        )
        # Optional exponent
        exponent = st.one_of(
            st.just(""),
            st.integers(min_value=-10, max_value=10).map(lambda e: "e" + ("" if e >= 0 else "-") + str(abs(e)))
        )
        # Sign
        sign = st.one_of(st.just(""), st.just("-"))

        # Compose number string
        def compose(sign_, int_, frac_, exp_):
            # Clean fraction: ensure it starts with '.' and digits
            if frac_ and not frac_.startswith('.'):
                frac_ = '.' + frac_
            return f"{sign_}{int_}{frac_}{exp_}"

        return st.tuples(sign, int_part, fraction, exponent).map(lambda t: compose(*t)).filter(lambda s: s != "")

    json_number_strat = json_number()

    # Recursive value strategy
    # Use st.recursive to build nested objects and arrays with bounded depth and size
    base = st.one_of(
        json_string_strat,
        json_number_strat,
        json_true,
        json_false,
        json_null,
    )

    # Forward declarations for obj and arr
    # obj: '{' pair (',' pair)* '}' or '{}'
    # pair: STRING ':' value
    # arr: '[' value (',' value)* ']' or '[]'

    # We'll define pair and then obj and arr recursively

    # pair strategy: STRING ':' value
    @st.composite
    def pair(draw, value_strat):
        key = draw(json_string_strat)
        val = draw(value_strat)
        return f"{key}:{val}"

    def obj_strategy(value_strat):
        # list of pairs (0 to 5)
        pairs = st.lists(pair(value_strat), max_size=5)
        return pairs.map(lambda ps: "{" + ",".join(ps) + "}" if ps else "{}")

    def arr_strategy(value_strat):
        # list of values (0 to 5)
        values = st.lists(value_strat, max_size=5)
        return values.map(lambda vs: "[" + ",".join(vs) + "]" if vs else "[]")

    # recursive value strategy including obj and arr
    def value_strategy():
        return st.recursive(
            base,
            lambda children: st.one_of(
                obj_strategy(children),
                arr_strategy(children),
            ),
            max_leaves=10,
        )

    val_strat = value_strategy()

    # Compose full json: value + EOF (EOF is implicit)
    json_strat = val_strat.map(lambda s: s)

    s = draw(json_strat)
    return s.encode("utf-8")