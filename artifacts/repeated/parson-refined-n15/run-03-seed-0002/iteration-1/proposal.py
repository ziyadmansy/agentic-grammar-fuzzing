from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then encode with json.dumps-like escaping
    # but since we can't import json, we'll do a minimal escaping here.
    def json_string():
        # Characters allowed inside JSON strings (SAFECODEPOINT)
        # Exclude control chars and backslash, quote
        safe_chars = (
            st.characters(
                blacklist_characters=['\\', '"'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        )
        # Include some escapes
        escapes = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Compose string parts: either safe char or escape sequence
        part = st.one_of(
            safe_chars.map(lambda c: c),
            escapes,
            # Unicode escape sequences \uXXXX
            st.integers(min_value=0, max_value=0xFFFF).map(lambda i: '\\u%04x' % i),
        )
        # Compose a string of length 0..20 parts
        parts = st.lists(part, max_size=20)
        def assemble(parts):
            # parts are strings already escaped or safe chars
            return '"' + ''.join(parts) + '"'
        return parts.map(assemble)

    json_string_st = json_string()

    # NUMBER strategy: produce valid JSON numbers as strings
    def json_number():
        # Compose number parts according to grammar
        # INT: '0' or non-zero digit followed by digits
        int_part = st.one_of(
            st.just("0"),
            st.tuples(
                st.sampled_from("123456789"),
                st.text("0123456789", max_size=10)
            ).map(lambda t: t[0] + t[1])
        )
        frac_part = st.one_of(
            st.just(""),
            st.tuples(
                st.just("."),
                st.text("0123456789", min_size=1, max_size=10)
            ).map(lambda t: t[0] + t[1])
        )
        exp_part = st.one_of(
            st.just(""),
            st.tuples(
                st.sampled_from("eE"),
                st.one_of(st.just("+"), st.just("-"), st.just("")),
                st.text("0123456789", min_size=1, max_size=5)
            ).map(lambda t: t[0] + t[1] + t[2])
        )
        sign_part = st.one_of(st.just(""), st.just("-"))
        return st.tuples(sign_part, int_part, frac_part, exp_part).map(
            lambda t: "".join(t)
        )

    json_number_st = json_number()

    # Recursive JSON value strategy
    # We'll use st.recursive to build nested objects and arrays with bounded size
    base = st.one_of(
        json_string_st,
        json_number_st,
        json_null,
        json_true,
        json_false,
    )

    # Forward declarations for obj and arr
    # pair: STRING ':' value
    # obj: '{' pair (',' pair)* '}' | '{}'
    # arr: '[' value (',' value)* ']' | '[]'

    # We define value recursively below

    def json_obj(value_st):
        # pair: STRING ':' value
        pair = st.tuples(json_string_st, value_st).map(lambda t: t[0] + ":" + t[1])
        # zero or more pairs separated by commas
        pairs = st.lists(pair, max_size=5)
        return pairs.map(
            lambda ps: "{" + (",".join(ps) if ps else "") + "}"
        )

    def json_arr(value_st):
        # zero or more values separated by commas
        values = st.lists(value_st, max_size=5)
        return values.map(
            lambda vs: "[" + (",".join(vs) if vs else "") + "]"
        )

    value_st = st.recursive(
        base,
        lambda children: st.one_of(
            json_obj(children),
            json_arr(children),
        ),
        max_leaves=10,
    )

    # Compose full JSON text and encode as bytes
    json_text = value_st.map(lambda s: s)

    result = draw(json_text)
    return result.encode("utf-8")