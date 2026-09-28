from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: use Hypothesis built-in json string strategy, which respects escapes and codepoints
    json_string = st.text(
        alphabet=(
            # safe codepoints excluding control chars and quotes/backslash
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # NUMBER strategy: bounded floats and ints to avoid packing errors
    # Use decimal notation only, no exponents to keep simpler and smaller
    json_number = st.one_of(
        st.integers(min_value=-10**6, max_value=10**6).map(str),
        st.floats(
            allow_nan=False,
            allow_infinity=False,
            min_value=-1e6,
            max_value=1e6,
            width=32,
        ).map(lambda f: format(f, '.6g'))
    )

    # Recursive JSON value strategy
    # Use st.recursive with max_depth to keep size bounded
    def json_value_strategy():
        base = st.one_of(
            json_string,
            json_number,
            json_null,
            json_true,
            json_false,
        )
        return st.recursive(
            base,
            lambda children: st.one_of(
                # object: { pair (, pair)* } or empty {}
                st.dictionaries(
                    keys=json_string,
                    values=children,
                    min_size=0,
                    max_size=3,
                ).map(
                    lambda d: (
                        '{' + 
                        ','.join(f'{k}:{v}' for k, v in d.items()) + 
                        '}'
                    )
                ),
                # array: [ value (, value)* ] or empty []
                st.lists(children, min_size=0, max_size=3).map(
                    lambda l: '[' + ','.join(l) + ']'
                ),
            ),
            max_leaves=10,
        )

    json_val = draw(json_value_strategy())
    return json_val.encode('utf-8')