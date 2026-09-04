from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.from_regex(
        r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?",
        fullmatch=True,
        max_size=20,
    )
    # STRING: roughly mimic JSON string with escapes and safe codepoints
    # We'll generate unicode strings and then escape them properly.
    # To keep near-valid cases, sometimes produce invalid escapes.
    def json_string():
        # safe codepoints excluding control chars and quotes/backslash
        safe_chars = (
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        )
        # Escape sequences allowed: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
        # We'll generate strings with some escapes inserted randomly.
        # To keep it simple, generate unicode strings and then escape them.
        s = draw(
            st.text(
                alphabet=safe_chars,
                min_size=0,
                max_size=20,
            )
        )
        # Escape backslash and quote
        def escape_char(c):
            if c == '"':
                return '\\"'
            if c == '\\':
                return '\\\\'
            if ord(c) < 0x20:
                # control chars: use \uXXXX
                return '\\u%04x' % ord(c)
            return c

        escaped = []
        for c in s:
            # randomly insert escapes for some chars
            if c == '"':
                escaped.append('\\"')
            elif c == '\\':
                escaped.append('\\\\')
            elif c == '/':
                # optionally escape slash
                if draw(st.booleans()):
                    escaped.append('\\/')
                else:
                    escaped.append('/')
            elif c == '\b':
                escaped.append('\\b')
            elif c == '\f':
                escaped.append('\\f')
            elif c == '\n':
                escaped.append('\\n')
            elif c == '\r':
                escaped.append('\\r')
            elif c == '\t':
                escaped.append('\\t')
            elif ord(c) < 0x20:
                escaped.append('\\u%04x' % ord(c))
            else:
                escaped.append(c)
        return '"' + ''.join(escaped) + '"'

    json_string_st = st.deferred(lambda: st.just(json_string()))

    # Recursive JSON values
    # We'll use st.recursive to build nested objects and arrays with bounded size
    base = st.one_of(
        json_null,
        json_true,
        json_false,
        json_number,
        st.deferred(lambda: json_string_st),
    )

    def json_obj():
        # pair: STRING ':' value
        # We'll generate small dicts with 0-3 pairs
        def pair():
            k = draw(json_string_st)
            v = draw(value)
            return f"{k}:{v}"

        n_pairs = draw(st.integers(min_value=0, max_value=3))
        if n_pairs == 0:
            return "{}"
        pairs = []
        for _ in range(n_pairs):
            pairs.append(draw(pair()))
        return "{" + ",".join(pairs) + "}"

    def json_arr():
        # array: [value, ...]
        n_vals = draw(st.integers(min_value=0, max_value=3))
        vals = [draw(value) for _ in range(n_vals)]
        return "[" + ",".join(vals) + "]"

    # We need to define value recursively
    # Use st.recursive with base and extend with obj and arr
    # But we want to keep the output as strings, so we define a recursive strategy for strings

    # We'll define a recursive strategy for JSON strings (not Python strings)
    # Because we need to draw() inside the composite, we define a helper composite

    @st.composite
    def value(draw):
        # To keep recursion bounded, limit max depth
        max_depth = 3
        def helper(depth):
            if depth >= max_depth:
                # only base cases
                return draw(base)
            else:
                # choose base or recursive
                choice = draw(
                    st.integers(min_value=0, max_value=2)
                )  # 0: base, 1: obj, 2: arr
                if choice == 0:
                    return draw(base)
                elif choice == 1:
                    # object
                    n_pairs = draw(st.integers(min_value=0, max_value=3))
                    if n_pairs == 0:
                        return "{}"
                    pairs = []
                    for _ in range(n_pairs):
                        k = draw(json_string_st)
                        v = helper(depth + 1)
                        pairs.append(f"{k}:{v}")
                    return "{" + ",".join(pairs) + "}"
                else:
                    # array
                    n_vals = draw(st.integers(min_value=0, max_value=3))
                    vals = [helper(depth + 1) for _ in range(n_vals)]
                    return "[" + ",".join(vals) + "]"

        return helper(0)

    # Draw the full JSON value and append EOF
    s = draw(value())
    return s.encode("utf-8")