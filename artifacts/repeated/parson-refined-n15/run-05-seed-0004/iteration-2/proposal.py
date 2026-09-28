from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll keep strings short to keep examples bounded
    def json_string():
        # Characters allowed inside strings: safe codepoints and escapes
        # We'll generate unicode codepoints excluding control chars and quotes/backslash
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # Escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
        # We'll generate either a safe char or an escape sequence
        escape_simple = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape: \u followed by 4 hex digits
        hex_digit = st.sampled_from('0123456789abcdefABCDEF')
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))
        char_or_escape = st.one_of(
            safe_char.map(lambda c: c),
            escape_simple,
            unicode_escape
        )
        # Build string of length 0 to 20 chars
        return char_or_escape.flatmap(
            lambda first: st.lists(char_or_escape, max_size=19).map(
                lambda rest: '"' + first + ''.join(rest) + '"'
            )
        ).filter(lambda s: len(s) <= 22)  # rough bound on length

    json_string_st = json_string()

    # NUMBER strategy: use Hypothesis floats and ints, convert to JSON number strings
    # We'll generate numbers as strings matching the grammar
    def json_number():
        # Generate int part
        int_part = st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        # Optional fractional part
        frac_part = st.one_of(
            st.just(""),
            st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False)
            .map(lambda f: ("%.10f" % f).rstrip('0').rstrip('.'))
            .filter(lambda s: s.startswith('0.'))
            .map(lambda s: s[1:])  # remove leading 0, keep .xxx
        )
        # Optional exponent part
        exp_part = st.one_of(
            st.just(""),
            st.integers(min_value=-10, max_value=10).map(lambda e: "e%d" % e)
        )
        # Optional leading minus
        sign_part = st.one_of(st.just(""), st.just("-"))
        return st.tuples(sign_part, int_part, frac_part, exp_part).map(
            lambda parts: "".join(parts)
        )

    json_number_st = json_number()

    # Recursive JSON value strategy
    # We'll limit max depth and size to keep examples bounded
    def json_value():
        return st.recursive(
            st.one_of(
                json_string_st,
                json_number_st,
                json_true,
                json_false,
                json_null,
            ),
            lambda children: st.one_of(
                # Object: { pair (, pair)* } or {}
                st.dictionaries(
                    keys=json_string_st,
                    values=children,
                    max_size=3,
                    # keys are strings with quotes, but pair expects STRING without quotes
                ).map(
                    lambda d: (
                        "{" +
                        ",".join(f"{k}:{v}" for k, v in d.items()) +
                        "}"
                    )
                ),
                # Array: [ value (, value)* ] or []
                st.lists(children, max_size=3).map(
                    lambda l: "[" + ",".join(l) + "]"
                ),
            ),
            max_leaves=10,
        )

    # Compose full JSON text with EOF
    json_text = json_value()

    s = draw(json_text)
    return s.encode("utf-8")