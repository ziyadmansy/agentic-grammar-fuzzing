from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then encode them as JSON strings
    # Use a small subset of escapes to keep it simple and valid
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and quotes/backslash)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Some escapes to include
        escapes = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Compose string pieces: either safe char or escape sequence
        pieces = st.lists(st.one_of(safe_chars.map(lambda c: c), escapes), min_size=0, max_size=20)
        return pieces.map(lambda chars: '"' + ''.join(chars) + '"')

    json_string_st = json_string()

    # NUMBER strategy: use Hypothesis floats and ints formatted as JSON numbers
    def json_number():
        # Generate int or float strings matching the grammar
        # Use floats with limited exponent and decimal places
        int_part = st.integers(min_value=-(10**6), max_value=10**6).map(str)
        frac_part = st.one_of(
            st.just(''),
            st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False)
            .map(lambda f: f'{f:.6f}'.lstrip('0'))
        )
        # Instead of composing manually, use Hypothesis floats and format as JSON number string
        # But to keep it simple, just generate floats and format with repr
        return st.one_of(
            st.integers(min_value=-(10**6), max_value=10**6).map(str),
            st.floats(min_value=-1e6, max_value=1e6, allow_infinity=False, allow_nan=False)
            .map(lambda f: format(f, '.6g'))
        )

    json_number_st = json_number()

    # Recursive JSON value strategy
    # We limit max depth to keep output size bounded
    def json_value():
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_null,
            json_true,
            json_false,
        )
        # Recursive containers: objects and arrays
        return st.recursive(
            base,
            lambda children: st.one_of(
                # Object: { pair (, pair)* } or {}
                st.dictionaries(
                    keys=json_string_st,
                    values=children,
                    min_size=0,
                    max_size=3,
                    # keys are JSON strings including quotes, but dictionary keys in Python are unquoted strings,
                    # so we must strip quotes from keys before using them as keys
                    # We'll generate keys as strings without quotes for dict keys, then re-quote in output
                    # So redefine keys strategy to produce unquoted strings
                ).map(
                    lambda d: (
                        '{' +
                        ','.join(
                            f'{k}:{v}' for k, v in d.items()
                        ) +
                        '}'
                    )
                ),
                # Array: [ value (, value)* ] or []
                st.lists(children, min_size=0, max_size=3).map(
                    lambda vs: '[' + ','.join(vs) + ']'
                ),
            ),
            max_leaves=10,
        )

    # Because keys in JSON objects must be strings, and our dict keys are JSON strings with quotes,
    # we need a keys strategy that produces unquoted strings (without quotes),
    # then in the map we add quotes around keys.

    # Redefine keys strategy for dict keys (unquoted strings)
    safe_chars_key = st.characters(
        blacklist_characters=['"', '\\', '\u0000', '\u001F'],
        min_codepoint=0x20,
        max_codepoint=0x10FFFF,
    )
    key_str = st.text(safe_chars_key, min_size=1, max_size=10)

    # Now redefine the recursive json_value with correct keys
    def json_value_fixed():
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_null,
            json_true,
            json_false,
        )

        def obj_strategy(children):
            return st.dictionaries(
                keys=key_str,
                values=children,
                min_size=0,
                max_size=3,
            ).map(
                lambda d: (
                    '{' +
                    ','.join(
                        f'"{k}":{v}' for k, v in d.items()
                    ) +
                    '}'
                )
            )

        def arr_strategy(children):
            return st.lists(children, min_size=0, max_size=3).map(
                lambda vs: '[' + ','.join(vs) + ']'
            )

        return st.recursive(
            base,
            lambda children: st.one_of(
                obj_strategy(children),
                arr_strategy(children),
            ),
            max_leaves=10,
        )

    json_val_st = json_value_fixed()

    # Compose full JSON with EOF
    json_full = json_val_st.map(lambda s: s.encode('utf-8'))

    return draw(json_full)