from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: simple escaped strings, avoiding control chars
    # Use Hypothesis built-in text with safe chars, then escape quotes and backslashes
    def json_string():
        # safe codepoints excluding control chars and quotes/backslash
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # generate text of length 0 to 20
        text_strat = st.text(safe_chars, min_size=0, max_size=20)

        @st.composite
        def escaped_string(draw):
            s = draw(text_strat)
            # escape backslash and quote
            s = s.replace('\\', '\\\\').replace('"', '\\"')
            return f'"{s}"'

        return escaped_string()

    json_string_strat = json_string()

    # NUMBER strategy: use floats and ints, then convert to JSON number strings
    @st.composite
    def json_number(draw):
        # generate int or float with bounded size
        # limit exponent to avoid huge numbers
        # Use floats with limited decimal places
        is_float = draw(st.booleans())
        if is_float:
            # floats between -1e6 and 1e6 with up to 6 decimal places
            f = draw(st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False))
            # format to JSON number string
            s = format(f, '.6f').rstrip('0').rstrip('.')
            if s == '-0':
                s = '0'
            return s
        else:
            i = draw(st.integers(min_value=-1_000_000, max_value=1_000_000))
            return str(i)

    json_number_strat = json_number()

    # Recursive value strategy
    # We define a recursive strategy for value:
    # value = string | number | obj | arr | true | false | null

    # Forward declaration for value
    # We'll define obj and arr inside recursive

    # To keep recursion bounded, limit max_depth
    max_depth = 3

    def json_value():
        # base cases
        base = st.one_of(
            json_string_strat,
            json_number_strat,
            json_true,
            json_false,
            json_null,
        )

        # recursive cases: obj and arr
        def json_obj():
            # obj = '{' pair (',' pair)* '}' | '{}'
            # pair = STRING ':' value
            # limit number of pairs to 0..4
            @st.composite
            def pairs(draw):
                n = draw(st.integers(min_value=0, max_value=4))
                # pairs: list of (string, value)
                # keys must be unique strings
                keys = draw(st.lists(json_string_strat, min_size=n, max_size=n, unique=True))
                values = [draw(json_value()) for _ in range(n)]
                # pair strings are already quoted strings, so keys are strings with quotes
                # but keys must be strings without quotes for JSON keys? No, JSON keys must be strings with quotes.
                # So keys are strings with quotes, we keep them as is.
                # Compose pairs as '"key":value'
                pairs_str = []
                for k, v in zip(keys, values):
                    pairs_str.append(f"{k}:{v}")
                return pairs_str

            @st.composite
            def obj_str(draw):
                pairs_list = draw(pairs())
                if not pairs_list:
                    return "{}"
                else:
                    inner = ",".join(pairs_list)
                    return "{" + inner + "}"

            return obj_str()

        def json_arr():
            # arr = '[' value (',' value)* ']' | '[]'
            # limit length 0..4
            @st.composite
            def arr_str(draw):
                n = draw(st.integers(min_value=0, max_value=4))
                values = [draw(json_value()) for _ in range(n)]
                inner = ",".join(values)
                return "[" + inner + "]"

            return arr_str()

        # Compose recursive strategy with bounded depth
        return st.recursive(
            base,
            lambda children: st.one_of(json_obj(), json_arr()),
            max_leaves=10,
        )

    # Draw the full JSON text and encode as bytes
    json_text = draw(json_value())
    return json_text.encode("utf-8")