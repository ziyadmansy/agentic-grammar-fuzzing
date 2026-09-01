from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic leaf strategies
    json_string = st.text(
        alphabet=st.characters(
            blacklist_characters=['\\', '"'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('"', '\\"').replace('\\', '\\\\') + '"')

    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: str(f))
    # Also allow integers as numbers
    json_int = st.integers(min_value=-1_000_000, max_value=1_000_000).map(str)
    json_number = st.one_of(json_int, json_number)

    json_const = st.sampled_from(['true', 'false', 'null'])

    # Forward declaration for recursive structures
    # We'll define value recursively with bounded depth
    def json_value():
        return st.deferred(lambda: json_value_inner())

    # Compose object and array recursively
    # Limit max size and depth to keep examples bounded
    max_depth = 3
    max_pairs = 5
    max_elements = 5

    @st.composite
    def json_obj(draw, depth=0):
        if depth >= max_depth:
            # At max depth, only empty object or simple pairs with leaf values
            empty = draw(st.booleans())
            if empty:
                return '{}'
            else:
                n = draw(st.integers(min_value=1, max_value=max_pairs))
                pairs = []
                for _ in range(n):
                    k = draw(json_string)
                    v = draw(st.one_of(json_string, json_number, json_const))
                    pairs.append(f'{k}:{v}')
                return '{' + ','.join(pairs) + '}'
        else:
            empty = draw(st.booleans())
            if empty:
                return '{}'
            else:
                n = draw(st.integers(min_value=1, max_value=max_pairs))
                pairs = []
                for _ in range(n):
                    k = draw(json_string)
                    v = draw(json_value().map(lambda s: s))
                    pairs.append(f'{k}:{v}')
                return '{' + ','.join(pairs) + '}'

    @st.composite
    def json_arr(draw, depth=0):
        if depth >= max_depth:
            empty = draw(st.booleans())
            if empty:
                return '[]'
            else:
                n = draw(st.integers(min_value=1, max_value=max_elements))
                elems = []
                for _ in range(n):
                    v = draw(st.one_of(json_string, json_number, json_const))
                    elems.append(v)
                return '[' + ','.join(elems) + ']'
        else:
            empty = draw(st.booleans())
            if empty:
                return '[]'
            else:
                n = draw(st.integers(min_value=1, max_value=max_elements))
                elems = []
                for _ in range(n):
                    v = draw(json_value())
                    elems.append(v)
                return '[' + ','.join(elems) + ']'

    @st.composite
    def json_value_inner(draw, depth=0):
        # Choose among all value types, with recursion for obj and arr
        choices = [
            json_string,
            json_number,
            json_const,
        ]
        if depth < max_depth:
            choices.append(json_obj(depth=depth + 1))
            choices.append(json_arr(depth=depth + 1))
        else:
            # At max depth, no recursion
            pass
        return draw(st.one_of(choices))

    # Draw the top-level JSON value and append EOF
    val = draw(json_value_inner(depth=0))
    return val.encode('utf-8')