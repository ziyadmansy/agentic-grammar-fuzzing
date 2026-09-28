from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: roughly matching grammar, allowing safe codepoints and escapes
    # We'll generate strings with safe unicode codepoints and some escapes.
    # To keep it simple, use Hypothesis text with limited characters and escape some.
    def json_string():
        # Characters allowed inside strings (excluding control chars and " \)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Generate a string with length up to 20
        base_str = st.text(safe_chars, max_size=20)

        # We will randomly insert some escapes into the string
        # Escapes: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
        escapes = st.sampled_from([
            r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t',
            # Unicode escape: \uXXXX with hex digits
            lambda: r'\u' + ''.join(draw(st.sampled_from("0123456789abcdefABCDEF")) for _ in range(4))
        ])

        def insert_escapes(s):
            # Randomly replace some chars with escapes
            import random
            s_list = list(s)
            for i in range(len(s_list)):
                if draw(st.booleans()):
                    esc = draw(escapes)
                    if callable(esc):
                        esc = esc()
                    s_list[i] = esc
            return ''.join(s_list)

        s = draw(base_str)
        s = insert_escapes(s)
        return '"' + s + '"'

    json_string_st = st.deferred(json_string)

    # NUMBER: generate numbers matching grammar
    # Use floats and ints, convert to string with minimal formatting
    def json_number():
        # Generate int or float or exponent form
        # We'll generate floats and ints and format them accordingly
        # To keep it simple, generate float or int as string
        # Use floats with limited exponent range
        # Also generate negative numbers
        sign = draw(st.sampled_from(["", "-"]))
        int_part = draw(st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        ))
        frac_part = draw(st.one_of(
            st.just(""),
            st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False)
            .map(lambda f: ("%.10f" % f).lstrip("0"))
            .filter(lambda s: s.startswith("."))
        ))
        exp_part = draw(st.one_of(
            st.just(""),
            st.integers(min_value=-10, max_value=10).map(lambda e: "e" + ("+" if e >= 0 else "") + str(e))
        ))
        # Compose number string
        num_str = sign + int_part
        if frac_part:
            num_str += frac_part
        num_str += exp_part
        return num_str

    json_number_st = st.deferred(json_number)

    # Recursive JSON values: string, number, obj, arr, true, false, null
    # Use st.recursive to keep recursion bounded

    # Forward declarations
    json_value = st.deferred(lambda: json_value_inner)

    # Object: { pair (, pair)* } or {}
    # pair: STRING : value
    @st.composite
    def json_pair(draw):
        k = draw(json_string_st)
        v = draw(json_value)
        return f"{k}:{v}"

    @st.composite
    def json_obj(draw):
        # Generate up to 3 pairs to keep size bounded
        pairs = draw(st.lists(json_pair(), max_size=3))
        if pairs:
            return "{" + ",".join(pairs) + "}"
        else:
            return "{}"

    # Array: [ value (, value)* ] or []
    @st.composite
    def json_arr(draw):
        values = draw(st.lists(json_value, max_size=3))
        if values:
            return "[" + ",".join(values) + "]"
        else:
            return "[]"

    # Compose json_value_inner with recursion bounded by st.recursive
    json_value_inner = st.recursive(
        st.one_of(
            json_string_st,
            json_number_st,
            json_true,
            json_false,
            json_null,
        ),
        lambda children: st.one_of(
            json_obj(),
            json_arr(),
        ),
        max_leaves=10,
    )

    # Compose full json with EOF
    json_text = draw(json_value_inner)
    # Return bytes
    return json_text.encode("utf-8")