from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON string: use safe unicode codepoints excluding control chars and quotes/backslash
    # SAFECODEPOINT ~["\\\u0000-\u001F]
    # We'll use a filtered string strategy to avoid control chars and backslash/quote
    def safe_json_string():
        # Characters allowed inside JSON strings (excluding control chars, backslash, quote)
        # Unicode codepoints from 0x20 (space) to 0x10FFFF except " and \
        # Hypothesis's st.text can filter characters by a predicate
        def is_safe(c):
            return c not in ['"', '\\'] and ord(c) >= 0x20
        # Limit max size to keep output bounded
        return st.text(alphabet=st.characters(blacklist_characters=['"', '\\'], min_codepoint=0x20), min_size=0, max_size=20)

    json_string = safe_json_string().map(lambda s: '"' + s + '"')

    # JSON number: use Hypothesis floats and ints, then format as JSON number string
    # We'll generate numbers as strings to avoid encoding errors
    def json_number_str():
        # Generate floats and ints within reasonable bounds
        # Use floats with finite values only
        number = st.one_of(
            st.integers(min_value=-10**6, max_value=10**6),
            st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)
        )
        def format_number(n):
            # Format int without decimal point, float with minimal representation
            if isinstance(n, int):
                return str(n)
            else:
                # Use repr to get minimal float representation
                s = repr(n)
                # JSON requires decimal point for floats
                if '.' not in s and 'e' not in s and 'E' not in s:
                    s += '.0'
                return s
        return number.map(format_number)

    # Recursive JSON value strategy
    # Use st.recursive to build nested arrays and objects
    base = st.one_of(
        json_null,
        json_true,
        json_false,
        json_string,
        json_number_str(),
    )

    # Compose arrays and objects
    # Arrays: [ value (, value)* ]
    # Objects: { pair (, pair)* }
    # pair: STRING : value

    # To avoid deep recursion and huge outputs, limit max_depth and max_size
    max_depth = 3
    max_size = 5

    def json_value():
        return st.recursive(
            base,
            lambda children: st.one_of(
                # array
                st.lists(children, min_size=0, max_size=max_size).map(
                    lambda vs: "[" + ",".join(vs) + "]"
                ),
                # object
                st.dictionaries(
                    keys=safe_json_string(),
                    values=children,
                    min_size=0,
                    max_size=max_size,
                ).map(
                    lambda d: "{" + ",".join(f"{k}:{v}" for k, v in d.items()) + "}"
                ),
            ),
            max_leaves=100,
        )

    json_str = draw(json_value())
    return json_str.encode("utf-8")