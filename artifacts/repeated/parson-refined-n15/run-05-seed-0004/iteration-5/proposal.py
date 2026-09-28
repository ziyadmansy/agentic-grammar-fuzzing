from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then json.dumps them to get valid JSON strings.
    # But since we can't import json or use eval/exec, we build strings manually.
    # We'll generate strings with safe unicode codepoints excluding control chars and quotes/backslash.
    # To keep it simple, generate ascii letters, digits, space, and some punctuation except " and \.
    safe_chars = st.characters(
        blacklist_characters=['"', '\\'],
        min_codepoint=0x20,
        max_codepoint=0x7E,
    )
    # Also allow some escapes: \\, \", \b, \f, \n, \r, \t, \uXXXX
    # We'll simulate escapes by randomly inserting them in the string.
    def json_string():
        # Generate a string of length 0..20
        base = st.text(safe_chars, max_size=20)
        # Insert escapes randomly
        escapes = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # We'll generate a list of chunks: either safe substrings or escapes
        # To keep it simple, generate a list of length 0..10 of either safe substrings or escapes
        chunk = st.one_of(
            st.text(safe_chars, max_size=3).filter(lambda s: s != ""),
            escapes,
            # Unicode escape: \uXXXX
            st.builds(lambda h: '\\u' + h, st.text(st.characters(min_codepoint=0, max_codepoint=0xF, whitelist_categories=('Nd',)), min_size=4, max_size=4).map(lambda s: ''.join(c if c in '0123456789abcdefABCDEF' else '0' for c in s)))
        )
        chunks = st.lists(chunk, max_size=10)
        return chunks.map(lambda chunks: '"' + ''.join(chunks) + '"')

    json_string_strat = json_string()

    # NUMBER: generate numbers as strings matching the grammar
    # We'll generate floats and ints and format them accordingly
    def json_number():
        # Generate int part
        int_part = st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        # Optional fraction
        fraction = st.one_of(
            st.just(""),
            st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False).map(lambda f: ("%.6f" % f)[1:] if f > 0 else "")
        )
        # Optional exponent
        exponent = st.one_of(
            st.just(""),
            st.integers(min_value=-10, max_value=10).map(lambda e: "e%+d" % e)
        )
        # Optional minus
        sign = st.booleans().map(lambda b: "-" if b else "")
        return st.tuples(sign, int_part, fraction, exponent).map(lambda t: t[0] + t[1] + t[2] + t[3])

    json_number_strat = json_number()

    # Recursive value strategy
    # We'll use st.recursive to build values: string, number, true, false, null, object, array
    # Objects: { pair (, pair)* } or {}
    # Pairs: STRING : value
    # Arrays: [ value (, value)* ] or []

    # Define pair strategy
    def pair_strategy():
        return st.tuples(json_string_strat, st.deferred(lambda: value_strategy)).map(lambda t: f"{t[0]}:{t[1]}")

    # Define object strategy
    def object_strategy():
        # empty or with pairs separated by commas
        pairs = st.lists(pair_strategy(), max_size=3)
        return pairs.map(lambda ps: "{" + (",".join(ps) if ps else "") + "}")

    # Define array strategy
    def array_strategy():
        values = st.lists(st.deferred(lambda: value_strategy), max_size=3)
        return values.map(lambda vs: "[" + (",".join(vs) if vs else "") + "]")

    # Compose value strategy
    base_values = st.one_of(
        json_string_strat,
        json_number_strat,
        json_true,
        json_false,
        json_null,
    )

    value_strategy = st.recursive(
        base_values,
        lambda children: st.one_of(
            object_strategy(),
            array_strategy(),
        ),
        max_leaves=10,
    )

    # Draw a value and encode as bytes
    s = draw(value_strategy)
    return s.encode("utf-8")