from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: produce valid JSON strings with escapes and safe codepoints
    # We'll produce Python strings and then json.dumps them for correctness,
    # but since we can't import json, we mimic escapes carefully.
    # Instead, produce strings with safe codepoints and simple escapes.
    # SAFECODEPOINT: ~["\\\u0000-\u001F]
    # We'll produce strings with characters from 0x20 to 0x10FFFF excluding " and \.
    # To keep it simple, use ascii letters, digits, and some safe punctuation.
    safe_chars = (
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789"
        " !#$%&'()*+,-./:;<=>?@[]^_`{|}~"
    )
    # Add some escaped sequences occasionally
    def json_string():
        # Compose a string with safe chars and occasional escapes
        base = st.text(safe_chars, min_size=0, max_size=20)
        # Occasionally insert escapes
        esc_chars = ['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t']
        def insert_escapes(s):
            import random
            s = list(s)
            for _ in range(random.randint(0, 3)):
                pos = random.randint(0, len(s)) if s else 0
                esc = random.choice(esc_chars)
                s.insert(pos, esc)
            return "".join(s)
        # We can't use random inside draw, so instead produce a strategy that mixes escapes and safe chars
        # We'll produce a list of pieces: either safe char sequences or escapes
        pieces = st.lists(
            st.one_of(
                st.text(safe_chars, min_size=1, max_size=5),
                st.sampled_from(esc_chars)
            ),
            min_size=0,
            max_size=10
        )
        return pieces.map(lambda ps: "".join(ps))

    json_string_strat = json_string().map(lambda s: '"' + s + '"')

    # NUMBER: use Hypothesis built-in floats and ints, format as JSON numbers
    def json_number():
        # Generate int or float strings matching JSON number grammar
        # Use floats with finite values, no NaN or inf
        # Format with minimal representation
        def to_json_number(n):
            if isinstance(n, int):
                return str(n)
            else:
                # Format float to JSON number string
                # Use repr to get minimal representation
                s = repr(n)
                # JSON requires decimal point for floats
                if 'e' in s or 'E' in s:
                    # normalize exponent to lowercase e and no plus sign
                    parts = s.lower().split('e')
                    base = parts[0]
                    exp = parts[1].lstrip('+')
                    s = base + 'e' + exp
                return s
        # Generate int or float
        num = st.one_of(
            st.integers(min_value=-(10**9), max_value=10**9),
            st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False)
        )
        return num.map(to_json_number)

    json_number_strat = json_number()

    # Recursive JSON value strategy
    # We'll define value recursively with bounded depth and size
    # Use st.recursive with base cases: string, number, true, false, null
    base = st.one_of(
        json_string_strat,
        json_number_strat,
        json_true,
        json_false,
        json_null,
    )

    def json_object():
        # pair: STRING ':' value
        # Generate pairs as (string, value) joined by colon
        # Limit number of pairs to keep size bounded
        def pair():
            return st.tuples(json_string_strat, value).map(lambda t: f"{t[0]}:{t[1]}")

        pairs = st.lists(pair(), max_size=5)
        # Either empty object or with pairs joined by commas
        return pairs.map(lambda ps: "{" + (",".join(ps) if ps else "") + "}")

    def json_array():
        # array: '[' value (',' value)* ']' or '[]'
        # Generate list of values max size 5
        arr_vals = st.lists(value, max_size=5)
        return arr_vals.map(lambda vs: "[" + (",".join(vs) if vs else "") + "]")

    # Use recursive to build nested objects and arrays
    value = st.recursive(
        base,
        lambda children: st.one_of(
            json_object(),
            json_array(),
        ),
        max_leaves=10,
    )

    # Compose full JSON: value + EOF
    json_str = draw(value)
    # Return bytes
    return json_str.encode("utf-8")