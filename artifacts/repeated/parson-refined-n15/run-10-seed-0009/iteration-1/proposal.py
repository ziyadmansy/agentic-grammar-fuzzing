from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: use Hypothesis built-in json string strategy, but restrict escapes to those allowed
    # We'll generate strings without control chars or unescaped quotes/backslashes
    # Hypothesis has st.text with min_codepoint and max_codepoint, but we want to exclude control chars and quotes/backslash
    # SAFECODEPOINT: ~["\\\u0000-\u001F]
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars, quote, backslash)
        # Unicode codepoints from 0x20 (space) to 0x10FFFF excluding '"' and '\\'
        # We'll generate strings of length 0..20 to keep size bounded
        allowed_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        return st.text(allowed_chars, max_size=20).map(lambda s: '"' + s + '"')

    # NUMBER strategy: match grammar NUMBER: '-'? INT ('.' [0-9]+)? EXP?
    # We'll generate numbers as strings
    def json_number():
        # Generate floats and ints, then convert to string matching grammar
        # Use floats with bounded magnitude and precision
        # We'll generate numbers as strings to avoid float formatting issues
        int_part = st.integers(min_value=0, max_value=10**6)
        frac_part = st.one_of(st.none(), st.text(st.digits, min_size=1, max_size=5))
        exp_part = st.one_of(st.none(),
                            st.tuples(st.sampled_from(['e', 'E']),
                                      st.sampled_from(['+', '-', '']),
                                      st.integers(min_value=0, max_value=99)).map(
                                lambda t: t[0] + t[1] + str(t[2])
                            ))
        def build_number(t):
            neg, i, f, e = t
            s = "-" if neg else ""
            s += str(i)
            if f is not None:
                s += "." + f
            if e is not None:
                s += e
            return s

        return st.tuples(st.booleans(), int_part, frac_part, exp_part).map(build_number)

    # Forward declarations for recursive structures
    # We'll use st.recursive to keep recursion bounded

    # Base values: string, number, true, false, null
    base_values = st.one_of(
        json_string(),
        json_number(),
        json_true,
        json_false,
        json_null,
    )

    # Recursive containers: object and array
    # Use st.recursive to build nested structures

    def json_value():
        # We'll define this inside to use recursion
        return st.recursive(
            base_values,
            lambda children: st.one_of(
                # object: '{' pair (',' pair)* '}' or '{}'
                st.dictionaries(
                    keys=json_string(),
                    values=children,
                    min_size=0,
                    max_size=5,
                ).map(lambda d: "{" + ",".join(f"{k}:{v}" for k, v in d.items()) + "}"),
                # array: '[' value (',' value)* ']' or '[]'
                st.lists(children, min_size=0, max_size=5).map(
                    lambda l: "[" + ",".join(l) + "]"
                ),
            ),
            max_leaves=10,
        )

    # Generate full JSON text and encode as bytes
    json_text = json_value()
    s = draw(json_text)
    return s.encode("utf-8")