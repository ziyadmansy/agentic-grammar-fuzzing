from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # SAFECODEPOINT: any char except " \ and control chars (U+0000-U+001F)
    # We'll generate unicode codepoints excluding control chars and " and \
    def json_string_chars():
        # exclude control chars, " and \
        # range U+0020 to U+10FFFF except " (0x22) and \ (0x5C)
        # We'll generate from 0x20 to 0x10FFFF and filter out " and \
        # but Hypothesis doesn't support filtering unicode codepoints easily,
        # so we restrict to a subset of safe chars:
        # ASCII printable except " and \ plus some unicode ranges
        safe_chars = (
            st.characters(min_codepoint=0x20, max_codepoint=0x21)  # space and !
            | st.characters(min_codepoint=0x23, max_codepoint=0x5B)  # # to [
            | st.characters(min_codepoint=0x5D, max_codepoint=0x10FFFF)  # ] to max
        )
        return safe_chars

    # Escape sequences: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
    # We'll generate strings with some escapes inserted randomly
    # To keep it simple, generate strings of safe chars and randomly insert escapes

    def json_string():
        # Generate a list of chars or escapes
        # We'll generate a list of length 0..20 to keep size bounded
        length = draw(st.integers(min_value=0, max_value=20))
        pieces = []
        for _ in range(length):
            # 80% chance safe char, 20% chance escape
            if draw(st.floats(0, 1)) < 0.8:
                c = draw(json_string_chars())
                pieces.append(c)
            else:
                esc = draw(st.sampled_from([
                    r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t',
                    # unicode escape: \uXXXX
                    r'\u' + ''.join(draw(st.sampled_from('0123456789abcdef')) for _ in range(4))
                ]))
                pieces.append(esc)
        s = ''.join(pieces)
        return '"' + s + '"'

    json_string_st = st.deferred(lambda: st.builds(lambda s: s, json_string()))

    # NUMBER strategy: use Hypothesis built-in floats and ints, then format as JSON number strings
    # We'll generate numbers as strings matching the grammar
    def json_number():
        # Generate int part
        int_part = draw(st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        ))
        # Optional fraction
        fraction = draw(st.one_of(
            st.just(""),
            st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False)
            .map(lambda f: ("%.10f" % f).lstrip("0") if f > 0 else "")
        ))
        # fraction might be empty or something like .123456
        if fraction and not fraction.startswith("."):
            fraction = "." + fraction.split(".")[1]
        # Optional exponent
        exponent = draw(st.one_of(
            st.just(""),
            st.integers(min_value=-10, max_value=10).map(lambda e: "e%d" % e)
        ))
        # Optional minus sign
        sign = draw(st.one_of(st.just(""), st.just("-")))
        num = sign + int_part + fraction + exponent
        # Validate minimal JSON number format by re-parsing float
        # fallback: if invalid, just return int_part
        try:
            float(num)
        except Exception:
            num = sign + int_part
        return num

    json_number_st = st.deferred(lambda: st.builds(lambda s: s, json_number()))

    # Recursive value strategy
    # value = STRING | NUMBER | obj | arr | true | false | null
    # We'll use st.recursive to keep recursion bounded

    # Forward declarations for obj and arr
    @st.composite
    def json_value(draw):
        # Compose value strategy with recursion
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_true,
            json_false,
            json_null,
        )
        # recursive container strategies
        def json_obj():
            # obj : '{' pair (',' pair)* '}' | '{}'
            # pair : STRING ':' value
            # generate 0..5 pairs
            n = draw(st.integers(min_value=0, max_value=5))
            pairs = []
            for _ in range(n):
                k = draw(json_string_st)
                v = draw(json_value())
                pairs.append(f"{k}:{v}")
            if pairs:
                return "{" + ",".join(pairs) + "}"
            else:
                return "{}"

        def json_arr():
            # arr : '[' value (',' value)* ']' | '[]'
            n = draw(st.integers(min_value=0, max_value=5))
            values = [draw(json_value()) for _ in range(n)]
            if values:
                return "[" + ",".join(values) + "]"
            else:
                return "[]"

        container = st.one_of(
            st.deferred(lambda: st.builds(json_obj)),
            st.deferred(lambda: st.builds(json_arr)),
        )
        # 70% base, 30% container to keep recursion bounded
        chosen = draw(st.one_of(
            base,
            container,
        ))
        return chosen

    # Compose full JSON text: value EOF
    json_text = draw(json_value())
    # Return bytes
    return json_text.encode("utf-8")