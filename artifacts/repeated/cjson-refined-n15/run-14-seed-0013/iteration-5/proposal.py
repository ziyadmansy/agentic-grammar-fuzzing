from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # SAFECODEPOINT: ~["\\\u0000-\u001F], i.e. no control chars, no " or \
    # We'll include common escapes and unicode escapes as well.
    hex_digit = st.characters("0123456789abcdefABCDEF")
    unicode_escape = st.tuples(
        st.just("\\u"),
        hex_digit, hex_digit, hex_digit, hex_digit
    ).map(lambda t: "".join(t))

    simple_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
    # SAFECODEPOINT: any char except control (0x00-0x1F), " and \
    safe_char = st.characters(
        blacklist_characters=['"', '\\'],
        min_codepoint=0x20,
        max_codepoint=0x10FFFF
    )

    # Compose string content from a mix of safe chars, escapes, and unicode escapes
    string_char = st.one_of(
        safe_char,
        simple_escapes,
        unicode_escape
    )
    # Limit string length to keep output size bounded
    string_content = st.lists(string_char, min_size=0, max_size=20).map("".join)
    json_string = string_content.map(lambda s: f'"{s}"')

    # NUMBER strategy: follow grammar NUMBER : '-'? INT ('.' [0-9]+)? EXP? ;
    # INT : '0' | [1-9][0-9]* ;
    # EXP : [Ee][+-]?[0-9]+ ;
    def number_str():
        sign = st.booleans().map(lambda b: "-" if b else "")
        int_part = st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        frac_part = st.one_of(
            st.none(),
            st.lists(st.characters("0123456789"), min_size=1, max_size=6).map(lambda ds: "." + "".join(ds))
        )
        exp_part = st.one_of(
            st.none(),
            st.tuples(
                st.sampled_from("Ee"),
                st.booleans().map(lambda b: "+" if b else "-"),
                st.lists(st.characters("0123456789"), min_size=1, max_size=4).map("".join)
            ).map(lambda t: t[0] + t[1] + t[2])
        )
        return st.tuples(sign, int_part, frac_part, exp_part).map(lambda parts: "".join(filter(None, parts)))

    json_number = number_str()

    # Recursive JSON value strategy
    # Use st.recursive to build obj and arr from values
    # Limit max depth and size to keep output bounded

    # Forward declare value strategy
    # We'll define value_strategy below after obj and arr

    # Placeholder for value_strategy to be defined later
    value_strategy = st.deferred(lambda: value_strategy_inner)

    # pair : STRING ':' value ;
    pair_strategy = st.tuples(json_string, value_strategy).map(lambda t: f"{t[0]}:{t[1]}")

    # obj : '{' pair (',' pair)* '}' | '{' '}' ;
    # To keep variety and bounded size, limit number of pairs
    obj_strategy = st.one_of(
        st.just("{}"),
        st.lists(pair_strategy, min_size=1, max_size=5).map(lambda pairs: "{" + ",".join(pairs) + "}")
    )

    # arr : '[' value (',' value)* ']' | '[' ']' ;
    arr_strategy = st.one_of(
        st.just("[]"),
        st.lists(value_strategy, min_size=1, max_size=5).map(lambda values: "[" + ",".join(values) + "]")
    )

    # Now define value_strategy_inner
    value_strategy_inner = st.one_of(
        json_string,
        json_number,
        obj_strategy,
        arr_strategy,
        json_true,
        json_false,
        json_null,
    )

    # Compose full json: value EOF
    json_full = value_strategy_inner.map(lambda s: s)

    # Draw the json string and encode as bytes
    s = draw(json_full)
    return s.encode("utf-8")