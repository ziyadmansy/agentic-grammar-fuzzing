from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then encode as JSON strings with escapes.
    # To keep it simple, use Hypothesis's built-in json string strategy and adapt.
    # But since we can't import json module or use eval, we build a safe string generator.

    # Characters allowed inside JSON strings (SAFECODEPOINT): no control chars, no " or \
    safe_char = st.characters(
        blacklist_characters=['"', '\\'],
        min_codepoint=0x20,
        max_codepoint=0x10FFFF,
    )
    # Escape sequences: \", \\, \b, \f, \n, \r, \t, \uXXXX
    # We'll simulate escapes by mixing safe chars and some escapes.
    # For simplicity, generate strings with safe chars and occasionally insert escapes.

    def json_string():
        # Generate a string with safe chars and occasional escapes
        # We'll generate a list of either safe chars or escape sequences
        escapes = st.sampled_from([
            r'\"', r'\\', r'\b', r'\f', r'\n', r'\r', r'\t',
            # Unicode escape: \uXXXX with hex digits
            lambda: r'\u' + ''.join(draw(st.sampled_from('0123456789abcdefABCDEF')) for _ in range(4))
        ])

        # Compose a list of elements: either safe char or escape string
        def element():
            # 80% safe char, 20% escape
            return st.one_of(
                safe_char.map(lambda c: c),
                st.deferred(lambda: st.just(draw(escapes)() if callable(draw(escapes)) else draw(escapes)))
            )

        # Generate a list of elements, length bounded
        elems = st.lists(element(), max_size=20)

        s = draw(elems)
        # Join all elements as string
        # If some elements are escapes, they are strings like \n, \uXXXX, etc.
        # safe chars are single characters
        # So join all as strings
        return '"' + ''.join(s) + '"'

    # NUMBER strategy: use Hypothesis floats and ints, then format as JSON number strings
    def json_number():
        # Generate int or float strings matching JSON number grammar
        # We'll generate a float or int and format accordingly
        # Use floats with limited exponent range to avoid huge numbers
        # Also generate negative numbers
        is_float = draw(st.booleans())
        if is_float:
            # float with optional exponent
            f = draw(st.floats(allow_infinity=False, allow_nan=False, width=32))
            # Format to JSON number string
            # Use repr to get a compact representation
            s = repr(f)
            # repr may produce 'inf' or 'nan' but we disallowed those
            # repr may produce '1e-07' which is valid JSON number
            # Remove trailing + in exponent if any (repr doesn't produce +)
            return s
        else:
            # int
            i = draw(st.integers(min_value=-(10**9), max_value=10**9))
            return str(i)

    # Recursive value strategy
    def json_value():
        # Compose the recursive strategy here
        base = st.one_of(
            json_null,
            json_true,
            json_false,
            json_string(),
            st.deferred(json_number),
        )

        # Recursive containers: obj and arr
        # Use st.recursive to keep bounded size
        def obj_strategy():
            # pair: STRING ':' value
            # STRING: use json_string() but strip quotes for keys
            # We'll generate keys as safe strings without escapes for simplicity
            key_char = st.characters(
                blacklist_characters=['"', '\\', ':', '{', '}', '[', ']', ','],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
            key = st.text(key_char, min_size=1, max_size=10).map(lambda s: '"' + s + '"')
            # pair: key : value
            pair = st.tuples(key, json_value())
            # obj: '{' pair (',' pair)* '}' or '{}'
            # Generate list of pairs, max 5 pairs
            pairs = st.lists(pair, max_size=5)
            def to_obj(pairs):
                if not pairs:
                    return "{}"
                return "{" + ",".join(k + ":" + v for k, v in pairs) + "}"
            return pairs.map(to_obj)

        def arr_strategy():
            # arr: '[' value (',' value)* ']' or '[]'
            values = st.lists(json_value(), max_size=5)
            def to_arr(vals):
                if not vals:
                    return "[]"
                return "[" + ",".join(vals) + "]"
            return values.map(to_arr)

        containers = st.one_of(obj_strategy(), arr_strategy())

        return st.recursive(base, lambda children: containers, max_leaves=10)

    # Compose full json text: value EOF
    json_text = json_value()

    s = draw(json_text)
    return s.encode("utf-8")