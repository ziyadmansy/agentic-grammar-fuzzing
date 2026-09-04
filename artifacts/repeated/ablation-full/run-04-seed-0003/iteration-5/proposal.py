from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: use Hypothesis built-in json string with safe codepoints
    # We replicate the grammar's STRING roughly by using st.text with safe characters
    # but to keep it simple and valid, use st.from_regex for JSON string content or st.text
    # Hypothesis has st.text but we must ensure no control chars or unescaped quotes
    # Instead, use st.from_regex for safe JSON string content (excluding control chars and quotes)
    # Then wrap with quotes and escape as needed.
    # To keep it simple, use st.text with min_size=0, max_size=10, filter out control chars and quotes
    def json_string():
        # Characters allowed inside JSON strings (SAFECODEPOINT): no control chars, no " or \
        # We'll exclude " and \ and control chars (<= 0x1F)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Limit length to keep size bounded
        return st.text(safe_chars, min_size=0, max_size=10).map(lambda s: '"' + s + '"')

    json_string_strat = json_string()

    # NUMBER strategy: use Hypothesis floats converted to JSON number strings
    # But to keep it valid JSON number, use st.floats with finite=True, no NaN/inf
    # Then convert to string with minimal formatting
    def json_number():
        # Use floats but exclude NaN and inf, and limit range to avoid huge exponents
        return st.floats(allow_nan=False, allow_infinity=False, width=32).map(
            lambda f: str(f) if '.' in str(f) or 'e' in str(f) or 'E' in str(f) else str(int(f))
        )
    json_number_strat = json_number()

    # Recursive strategy for JSON values
    # We'll define a recursive strategy that can produce objects, arrays, or primitives
    # Limit max_leaves to keep size bounded

    # Forward declaration for recursive use
    def json_value():
        return st.recursive(
            base=st.one_of(
                json_string_strat,
                json_number_strat,
                json_true,
                json_false,
                json_null,
            ),
            extend=lambda children: st.one_of(
                # Object: { pair (, pair)* } or {}
                st.dictionaries(
                    keys=json_string_strat,
                    values=children,
                    min_size=0,
                    max_size=3,
                ).map(
                    lambda d: (
                        "{" +
                        ",".join(f"{k}:{v}" for k, v in d.items()) +
                        "}"
                    )
                ),
                # Array: [ value (, value)* ] or []
                st.lists(children, min_size=0, max_size=3).map(
                    lambda l: "[" + ",".join(l) + "]"
                ),
            ),
            max_leaves=10,
        )

    # Compose the full JSON text with EOF
    json_text = json_value().map(lambda s: s)

    # Draw the JSON string and encode to bytes
    s = draw(json_text)
    return s.encode("utf-8")