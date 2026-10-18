from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: quoted strings with safe codepoints and escapes
    # We'll generate unicode strings excluding control chars and quotes/backslash,
    # then escape some characters to produce valid JSON strings.
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars, quotes, backslash)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Generate a string of length 0 to 20
        base_str = st.text(safe_chars, max_size=20)

        # Escape some characters randomly to produce valid JSON escapes
        def escape_json_string(s: str) -> str:
            # Escape backslash and quote
            s = s.replace('\\', '\\\\').replace('"', '\\"')
            # Escape control characters if any (should be none, but just in case)
            # Also escape some special chars to keep near-valid cases
            s = s.replace('\b', '\\b').replace('\f', '\\f').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
            return s

        escaped = draw(base_str.map(escape_json_string))
        return f'"{escaped}"'

    json_string_st = st.deferred(json_string)

    # NUMBER strategy: integers and floats with optional exponent
    json_number = st.floats(allow_nan=False, allow_infinity=False).map(lambda f: format(f, '.15g'))

    # Forward declaration for recursive structures
    # We'll use st.recursive to build obj and arr

    # Pair: STRING ':' value
    @st.composite
    def pair(draw, value_st):
        key = draw(json_string_st)
        val = draw(value_st)
        return f"{key}:{val}"

    # Object: '{' pair (',' pair)* '}' or '{}'
    def json_object(value_st):
        # 0 to 5 pairs
        pairs = st.lists(pair(value_st), max_size=5)
        return pairs.map(lambda ps: "{" + ",".join(ps) + "}" if ps else "{}")

    # Array: '[' value (',' value)* ']' or '[]'
    def json_array(value_st):
        values = st.lists(value_st, max_size=5)
        return values.map(lambda vs: "[" + ",".join(vs) + "]" if vs else "[]")

    # Recursive value strategy
    def json_value():
        base = st.one_of(
            json_string_st,
            json_number,
            json_null,
            json_true,
            json_false,
        )
        return st.recursive(
            base,
            lambda children: st.one_of(
                json_object(children),
                json_array(children),
            ),
            max_leaves=10,
        )

    value_st = json_value()

    # Compose full JSON: value + EOF (just value here)
    json_text = value_st

    s = draw(json_text)
    return s.encode("utf-8")