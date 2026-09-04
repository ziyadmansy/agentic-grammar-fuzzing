from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON strings: use safe unicode codepoints excluding control chars and quotes/backslash
    # We mimic SAFECODEPOINT: ~["\\\u0000-\u001F]
    # Hypothesis text excludes surrogates by default, so we just exclude control chars and quotes/backslash
    safe_chars = st.characters(
        blacklist_characters=['"', '\\'],
        min_codepoint=0x20,
        max_codepoint=0x10FFFF,
    )
    json_string = st.text(safe_chars, min_size=0).map(lambda s: '"' + s + '"')

    # JSON numbers: mimic grammar with optional minus, int, optional frac, optional exp
    # Use floats and ints converted to strings, but restrict size to keep bounded
    def number_str():
        # Compose number string with optional parts
        sign = st.sampled_from(["", "-"])
        int_part = st.one_of(st.just("0"), st.integers(min_value=1, max_value=99999).map(str))
        frac_part = st.one_of(st.just(""), st.floats(min_value=0, max_value=1).map(lambda f: ("%.5f" % f)[1:]))
        exp_part = st.one_of(st.just(""), st.integers(min_value=-99, max_value=99).map(lambda e: "e%+d" % e))
        return st.tuples(sign, int_part, frac_part, exp_part).map(lambda t: "".join(t))

    json_number = number_str()

    # Forward declare value strategy for recursion
    # We'll define it below using st.recursive

    # Define value base: primitives only (no recursion)
    json_value_base = st.one_of(
        json_string,
        json_number,
        json_true,
        json_false,
        json_null,
    )

    # Recursive containers: objects and arrays
    # We limit max_leaves to keep size bounded

    def json_object():
        # pair: STRING ':' value
        # pairs: zero or more pairs separated by commas
        # We'll generate dicts with string keys and json_value values
        # Limit dict size to keep bounded
        return st.dictionaries(
            keys=json_string,
            values=json_value,
            max_size=5,
            # keys are strings with quotes, but JSON keys must be strings without quotes inside keys,
            # so keys are quoted strings already
        ).map(lambda d: "{" + ",".join(f"{k}:{v}" for k, v in d.items()) + "}")

    def json_array():
        # array of values, max size 5
        return st.lists(json_value, max_size=5).map(lambda vs: "[" + ",".join(vs) + "]")

    # Now define json_value recursively
    json_value = st.recursive(
        json_value_base,
        lambda children: st.one_of(
            json_object(),
            json_array(),
        ),
        max_leaves=10,
    )

    # Assign to global name for recursion
    global json_value
    json_value = json_value

    # Compose full json: value + EOF (no trailing chars)
    result = draw(json_value)
    return result.encode("utf-8")