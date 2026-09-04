from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic atomic JSON values
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON strings: use printable ASCII except control chars and backslash, quote
    # To keep it simple, generate strings with safe codepoints only (no control chars)
    # and escape sequences will be omitted for simplicity.
    # We'll generate strings with length up to 20.
    json_string = st.text(
        alphabet=st.characters(
            blacklist_characters=['\\', '"', '\u0000', '\u0001', '\u0002', '\u0003', '\u0004', '\u0005', '\u0006', '\u0007',
                                  '\u0008', '\u0009', '\u000A', '\u000B', '\u000C', '\u000D', '\u000E', '\u000F',
                                  '\u0010', '\u0011', '\u0012', '\u0013', '\u0014', '\u0015', '\u0016', '\u0017',
                                  '\u0018', '\u0019', '\u001A', '\u001B', '\u001C', '\u001D', '\u001E', '\u001F'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s + '"')

    # JSON numbers: integers and floats, bounded in magnitude
    json_number = st.one_of(
        st.integers(min_value=-10**6, max_value=10**6).map(str),
        st.floats(min_value=-1e6, max_value=1e6, allow_infinity=False, allow_nan=False).map(lambda f: format(f, 'g'))
    )

    # Recursive JSON values: obj and arr
    # We'll define a recursive strategy for JSON values

    # Forward declaration for recursive use
    def json_value():
        return st.deferred(lambda: json_value_strategy)

    # JSON pair: "string" : value
    json_pair = st.tuples(json_string, json_value()).map(lambda p: f"{p[0]}:{p[1]}")

    # JSON object: {} or { pair (, pair)* }
    json_object = st.recursive(
        st.just("{}"),
        lambda children: st.one_of(
            st.tuples(
                json_pair,
                st.lists(json_pair, max_size=3)
            ).map(lambda t: "{" + ",".join([t[0]] + t[1]) + "}")
        ),
        max_leaves=5,
    )

    # JSON array: [] or [ value (, value)* ]
    json_array = st.recursive(
        st.just("[]"),
        lambda children: st.lists(children, min_size=1, max_size=4).map(lambda vs: "[" + ",".join(vs) + "]"),
        max_leaves=5,
    )

    # Compose the full json_value_strategy
    json_value_strategy = st.one_of(
        json_string,
        json_number,
        json_object,
        json_array,
        json_true,
        json_false,
        json_null,
    )

    # Draw a JSON value and encode as bytes
    result = draw(json_value_strategy)
    return result.encode("utf-8")