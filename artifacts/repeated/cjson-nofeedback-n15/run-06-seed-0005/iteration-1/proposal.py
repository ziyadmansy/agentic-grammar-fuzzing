from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then encode them as JSON strings.
    # To keep it simple, use st.text with safe characters and escape quotes/backslashes.
    def json_string():
        # safe codepoints exclude control chars and quotes/backslash
        safe_chars = (
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        )
        # Allow some escapes by including backslash and quote and then escaping them
        # But Hypothesis text won't generate backslash or quote here, so we add them manually
        # We'll generate a string and then escape quotes and backslashes manually
        return st.text(safe_chars, max_size=20).map(
            lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'
        )

    json_string_st = json_string()

    # NUMBER strategy: generate numbers matching the grammar
    # We'll generate Python floats and ints and convert to JSON number strings
    def json_number():
        # Generate int or float with optional exponent
        # Use floats with limited magnitude to avoid huge exponents
        # Also generate ints as strings
        int_part = st.integers(min_value=-10**6, max_value=10**6)
        float_part = st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e6,
            max_value=1e6,
        )
        # Compose number string from int or float
        def to_json_number(x):
            # Format float with minimal representation
            if isinstance(x, int):
                return str(x)
            else:
                # Use repr to get scientific notation if needed
                s = repr(x)
                # Remove trailing .0 for floats that are integral
                if s.endswith(".0"):
                    s = s[:-2]
                return s

        return st.one_of(
            int_part.map(to_json_number),
            float_part.map(to_json_number),
        )

    json_number_st = json_number()

    # Recursive JSON value strategy
    # We'll use st.recursive to build nested objects and arrays with bounded depth and size

    # Forward declare value strategy
    # value = STRING | NUMBER | obj | arr | true | false | null

    # Base values: string, number, true, false, null
    base_values = st.one_of(
        json_string_st,
        json_number_st,
        json_true,
        json_false,
        json_null,
    )

    # Pair: STRING ':' value
    @st.composite
    def pair(draw, value_st):
        k = draw(json_string_st)
        v = draw(value_st)
        return f"{k}:{v}"

    # Object: '{' pair (',' pair)* '}' or '{}'
    def obj(value_st):
        # Generate 0 to 5 pairs
        pairs = st.lists(pair(value_st), max_size=5)
        return pairs.map(
            lambda ps: "{" + ",".join(ps) + "}" if ps else "{}"
        )

    # Array: '[' value (',' value)* ']' or '[]'
    def arr(value_st):
        vals = st.lists(value_st, max_size=5)
        return vals.map(
            lambda vs: "[" + ",".join(vs) + "]" if vs else "[]"
        )

    # Recursive value strategy
    value_st = st.recursive(
        base_values,
        lambda children: st.one_of(
            obj(children),
            arr(children),
        ),
        max_leaves=10,
    )

    # Compose full JSON: value + EOF (just value here)
    json_text = value_st

    s = draw(json_text)
    return s.encode("utf-8")