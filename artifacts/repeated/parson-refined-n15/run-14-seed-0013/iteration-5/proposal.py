from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives as strings
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON string: use safe characters, escape as needed
    # We'll generate strings without control chars or unescaped quotes/backslashes
    json_string = st.text(
        alphabet=(
            # safe codepoints excluding control chars and quotes/backslash
            # SAFECODEPOINT: ~["\\\u0000-\u001F]
            # We'll exclude control chars and " and \ explicitly
            st.characters(
                blacklist_characters=['"', '\\'],
                blacklist_categories=('Cc',)
            )
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # JSON number as string
    # We'll generate numbers as strings matching the grammar
    def json_number_str():
        # Compose number parts
        sign = st.one_of(st.just(''), st.just('-'))
        int_part = st.one_of(st.just('0'), st.integers(min_value=1, max_value=10**6).map(str))
        frac_part = st.one_of(st.just(''), st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False).map(lambda f: '.' + str(f).split('.')[1]))
        exp_part = st.one_of(st.just(''), st.tuples(st.sampled_from(['e', 'E']), st.sampled_from(['+', '-','']), st.integers(min_value=0, max_value=100)).map(lambda t: t[0] + t[1] + str(t[2])))
        return st.tuples(sign, int_part, frac_part, exp_part).map(lambda parts: ''.join(parts))

    json_number = json_number_str()

    # Recursive JSON value strategy
    # We'll limit max_leaves to keep size bounded
    def json_value():
        return st.recursive(
            st.one_of(json_string, json_number, json_true, json_false, json_null),
            lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.dictionaries(
                    keys=json_string,
                    values=children,
                    min_size=0,
                    max_size=3,
                ).map(lambda d: '{' + ','.join(f'{k}:{v}' for k, v in d.items()) + '}'),
                # array: [ value (, value)* ] or []
                st.lists(children, min_size=0, max_size=3).map(lambda l: '[' + ','.join(l) + ']'),
            ),
            max_leaves=10,
        )

    val = draw(json_value())
    return val.encode('utf-8')