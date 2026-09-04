from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON values
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.from_regex(
        r"-?(0|[1-9]\d*)(\.\d+)?([eE][+-]?\d+)?", fullmatch=True
    )
    json_string = st.text(
        alphabet=(
            # SAFECODEPOINT: any Unicode codepoint except control chars and " \ 
            # We'll exclude control chars and backslash and quote
            # Control chars: U+0000-U+001F
            # Exclude " and \
            # So: all chars >= U+0020 except " and \
            # Hypothesis text() can take a blacklist via filter
        )
    ).filter(
        lambda s: all(
            (c >= " " and c != '"' and c != "\\") for c in s
        )
    ).map(lambda s: '"' + s + '"')

    # Recursive strategy for JSON values
    def json_value():
        # Use recursive to build nested arrays and objects
        base = st.one_of(json_string, json_number, json_null, json_true, json_false)
        return st.recursive(
            base,
            lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.dictionaries(
                    keys=json_string,
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
                # array: [ value (, value)* ] or []
                st.lists(children, min_size=0, max_size=3).map(
                    lambda l: "[" + ",".join(l) + "]"
                ),
            ),
            max_leaves=10,
        )

    s = json_value()
    result = draw(s)
    return result.encode("utf-8")