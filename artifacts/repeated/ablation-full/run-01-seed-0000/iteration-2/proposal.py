from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON string: use Hypothesis's built-in string strategy with safe unicode codepoints,
    # then escape as JSON string
    def json_string():
        # We generate strings without control chars or quotes/backslash to keep it simple
        s = draw(st.text(
            alphabet=st.characters(
                blacklist_characters=['"', '\\'],
                blacklist_categories=('Cc',)  # control chars
            ),
            min_size=0,
            max_size=20
        ))
        # Escape backslash and quotes for JSON string
        escaped = s.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped}"'

    # JSON number: generate as string to preserve formatting
    def json_number():
        # Use Hypothesis float strategy, then convert to JSON number string
        # Limit floats to finite values, no NaN or inf
        f = draw(st.floats(allow_nan=False, allow_infinity=False, width=32))
        # Format as JSON number string
        # Use repr to get shortest representation
        s = repr(f)
        # JSON numbers cannot have leading plus sign, repr never adds it
        # repr can produce 'inf', but we disallowed it
        # repr can produce 'nan', disallowed
        return s

    # Recursive JSON value strategy
    def json_value():
        # Compose a recursive strategy for JSON values
        base = st.deferred(lambda: st.one_of(
            st.just("null"),
            st.just("true"),
            st.just("false"),
            st.builds(json_string),
            st.builds(json_number),
        ))

        # Recursive containers: objects and arrays
        def json_obj():
            # pairs: STRING : value
            # STRING keys: use json_string() but keys must be strings, so reuse
            # Use small number of pairs to keep size bounded
            keys = st.lists(
                st.text(
                    alphabet=st.characters(
                        blacklist_characters=['"', '\\'],
                        blacklist_categories=('Cc',)
                    ),
                    min_size=1,
                    max_size=10
                ),
                unique=True,
                max_size=5,
            )
            def build_obj(klist):
                pairs = []
                for k in klist:
                    # escape key as JSON string
                    esc_k = k.replace('\\', '\\\\').replace('"', '\\"')
                    key_str = f'"{esc_k}"'
                    val_str = draw(json_value())
                    pairs.append(f"{key_str}:{val_str}")
                if pairs:
                    return "{" + ",".join(pairs) + "}"
                else:
                    return "{}"
            return keys.flatmap(build_obj)

        def json_arr():
            # array of values, max length 5
            vals = st.lists(json_value(), max_size=5)
            def build_arr(vlist):
                return "[" + ",".join(vlist) + "]"
            return vals.flatmap(build_arr)

        return st.recursive(
            base,
            lambda children: st.one_of(json_obj(), json_arr()),
            max_leaves=10,
        )

    # Draw the top-level JSON value and append EOF
    val = draw(json_value())
    # Return as bytes
    return val.encode("utf-8")