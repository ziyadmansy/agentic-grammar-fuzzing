from hypothesis import strategies as st

# Direct-to-text JSON grammar generation (mirrors grammar/JSON.g4 productions),
# built only from Hypothesis combinators and string operators/methods so it
# runs inside the harness sandbox (which strips ordinary Python builtins).

digit = st.sampled_from("0123456789")
digit1_9 = st.sampled_from("123456789")


def _join(strategy):
    return strategy.map(lambda parts: "".join(parts))


int_part = st.one_of(
    st.just("0"),
    st.tuples(digit1_9, _join(st.lists(digit, max_size=18))).map(lambda t: t[0] + t[1]),
)
frac_part = _join(st.lists(digit, min_size=1, max_size=18)).map(lambda d: "." + d)
huge_exponent_digits = _join(st.lists(digit, min_size=2, max_size=5))
exp_part = st.tuples(
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    huge_exponent_digits,
).map(lambda t: t[0] + t[1] + t[2])

json_number = st.one_of(
    st.tuples(st.sampled_from(["", "-"]), int_part).map(lambda t: t[0] + t[1]),
    st.tuples(st.sampled_from(["", "-"]), int_part, frac_part).map(lambda t: t[0] + t[1] + t[2]),
    st.tuples(st.sampled_from(["", "-"]), int_part, exp_part).map(lambda t: t[0] + t[1] + t[2]),
    st.tuples(st.sampled_from(["", "-"]), int_part, frac_part, exp_part).map(
        lambda t: t[0] + t[1] + t[2] + t[3]
    ),
    st.just("-0"),
    st.just("-0.0"),
    st.just("0e0"),
    st.just("-0e-0"),
    _join(st.lists(digit, min_size=1, max_size=400)),
)

safe_char = st.characters(min_codepoint=0x20, max_codepoint=0x7E, exclude_characters='"\\')
safe_string_body = _join(st.lists(safe_char, max_size=48))

escaped_string_body = st.sampled_from(
    [
        "",
        "\\n\\t\\r\\b\\f",
        "\\u0000",
        "\\uffff",
        "\\ud800",
        "\\udfff",
        "\\ud800\\ud800",
        "\\ud83d\\ude00",
        "\\ud83d",
        "\\/\\\\\\\"",
        "a" * 4096,
    ]
)

json_string = st.one_of(safe_string_body, escaped_string_body).map(lambda body: '"' + body + '"')

json_key = st.one_of(safe_string_body, st.just(""), st.just("k")).map(lambda body: '"' + body + '"')

json_scalar = st.one_of(
    st.just("null"),
    st.just("true"),
    st.just("false"),
    json_number,
    json_string,
)


def _extend(children):
    array_items = st.lists(children, max_size=6).map(lambda items: "[" + ",".join(items) + "]")
    object_pairs = st.lists(st.tuples(json_key, children), max_size=6).map(
        lambda pairs: "{" + ",".join(k + ":" + v for k, v in pairs) + "}"
    )
    return st.one_of(array_items, object_pairs)


json_value = st.recursive(json_scalar, _extend, max_leaves=40)

deep_array = st.integers(min_value=1900, max_value=2200).map(lambda n: "[" * n + "0" + "]" * n)
deep_object = st.integers(min_value=1900, max_value=2100).map(
    lambda n: ('{"a":' * n) + "0" + ("}" * n)
)
mixed_deep = st.integers(min_value=900, max_value=1100).map(
    lambda n: ('[{"a":' * n) + "0" + ("}]" * n)
)

duplicate_keys = st.lists(json_scalar, min_size=2, max_size=8).map(
    lambda values: "{" + ",".join('"k":' + v for v in values) + "}"
)

trailing_garbage = st.tuples(
    json_value, st.sampled_from([" x", ",", "}", "]", "\x00", "  \n\t"])
).map(lambda t: t[0] + t[1])


@st.composite
def generated_json(draw):
    mode = draw(
        st.sampled_from(
            [
                "value",
                "value",
                "value",
                "deep_array",
                "deep_object",
                "mixed_deep",
                "duplicate_keys",
                "trailing_garbage",
            ]
        )
    )
    if mode == "deep_array":
        text = draw(deep_array)
    elif mode == "deep_object":
        text = draw(deep_object)
    elif mode == "mixed_deep":
        text = draw(mixed_deep)
    elif mode == "duplicate_keys":
        text = draw(duplicate_keys)
    elif mode == "trailing_garbage":
        text = draw(trailing_garbage)
    else:
        text = draw(json_value)
    return text.encode("utf-8", errors="surrogatepass")
