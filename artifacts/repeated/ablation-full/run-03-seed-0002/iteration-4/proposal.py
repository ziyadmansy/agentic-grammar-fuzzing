from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives as strings
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON string: use Hypothesis text with safe codepoints, escape quotes and backslashes
    def json_string():
        # Use a small max_size to keep output size bounded
        s = draw(st.text(
            alphabet=st.characters(
                blacklist_characters=['"', '\\', '\u0000', '\u0001', '\u0002', '\u0003', '\u0004', '\u0005', '\u0006', '\u0007',
                                      '\u0008', '\u0009', '\u000A', '\u000B', '\u000C', '\u000D', '\u000E', '\u000F',
                                      '\u0010', '\u0011', '\u0012', '\u0013', '\u0014', '\u0015', '\u0016', '\u0017',
                                      '\u0018', '\u0019', '\u001A', '\u001B', '\u001C', '\u001D', '\u001E', '\u001F']),
            min_size=0,
            max_size=20))
        # Escape backslash and quote
        s = s.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{s}"'

    json_string_st = st.deferred(lambda: st.just(json_string()))

    # JSON number: use Hypothesis floats converted to JSON number strings
    json_number = st.floats(allow_nan=False, allow_infinity=False, width=32).map(lambda f: format(f, 'g'))

    # Recursive JSON value strategy
    def json_value():
        # Compose the recursive strategy with bounded depth and size
        base = st.one_of(
            json_string_st,
            json_number,
            json_true,
            json_false,
            json_null,
        )

        # Recursive containers: objects and arrays
        def json_obj():
            # pairs: STRING : value
            # limit number of pairs to keep size bounded
            pairs = st.dictionaries(
                keys=json_string_st,
                values=st.deferred(json_value),
                min_size=0,
                max_size=5,
                # To keep keys unique and valid
                )
            return pairs.map(
                lambda d: (
                    "{" + ",".join(f"{k}:{v}" for k, v in d.items()) + "}"
                    if d else "{}"
                )
            )

        def json_arr():
            # arrays of values, bounded length
            arr = st.lists(st.deferred(json_value), min_size=0, max_size=5)
            return arr.map(
                lambda l: (
                    "[" + ",".join(l) + "]"
                    if l else "[]"
                )
            )

        return st.recursive(
            base,
            lambda children: st.one_of(json_obj(), json_arr()),
            max_leaves=10,
        )

    # Compose full JSON text with EOF
    json_text = json_value()

    s = draw(json_text)
    return s.encode("utf-8")