from hypothesis import strategies as st

# Iteration 2: iteration-1 covered deep nesting, numeric edge cases, escaping,
# and duplicate keys (0 crashes; confirmed parson *rejects* duplicate keys via
# json_object_add, unlike cJSON) but every object/array was capped at 6
# elements. parson's hash table starts at STARTING_CAPACITY=16 cells /
# item_capacity=11 (cell_capacity*7/10), so objects with <=11 unique keys
# never exercise json_object_grow_and_rehash(), and arrays under a similar
# small bound never resize either. This iteration steers toward that
# untested region: wide objects/arrays that force multiple rehashes/grows,
# combined with the deep-nesting and numeric-edge-case generators that
# already worked.

digit = st.sampled_from("0123456789")
digit1_9 = st.sampled_from("123456789")


def _join(strategy):
    return strategy.map(lambda parts: "".join(parts))


int_part = st.one_of(
    st.just("0"),
    st.tuples(digit1_9, _join(st.lists(digit, max_size=18))).map(lambda t: t[0] + t[1]),
)
frac_part = _join(st.lists(digit, min_size=1, max_size=18)).map(lambda d: "." + d)
exp_part = st.tuples(
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    _join(st.lists(digit, min_size=2, max_size=5)),
).map(lambda t: t[0] + t[1] + t[2])

json_number = st.one_of(
    st.tuples(st.sampled_from(["", "-"]), int_part).map(lambda t: t[0] + t[1]),
    st.tuples(st.sampled_from(["", "-"]), int_part, frac_part).map(lambda t: t[0] + t[1] + t[2]),
    st.tuples(st.sampled_from(["", "-"]), int_part, exp_part).map(lambda t: t[0] + t[1] + t[2]),
    st.just("-0"),
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
        "a" * 20000,
    ]
)

json_string = st.one_of(safe_string_body, escaped_string_body).map(lambda body: '"' + body + '"')

# short alphabet so distinct draws are likely to collide on hash-bucket
# neighborhoods once the table is full of them, stressing linear-probe reuse.
short_key_char = st.sampled_from("abcdefghijklmnopqrstuvwxyz")
unique_key = _join(st.lists(short_key_char, min_size=1, max_size=3)).map(lambda body: '"' + body + '"')

json_scalar = st.one_of(
    st.just("null"),
    st.just("true"),
    st.just("false"),
    json_number,
    json_string,
)


def _extend(children):
    array_items = st.lists(children, max_size=6).map(lambda items: "[" + ",".join(items) + "]")
    object_pairs = st.lists(st.tuples(unique_key, children), max_size=6).map(
        lambda pairs: "{" + ",".join(k + ":" + v for k, v in pairs) + "}"
    )
    return st.one_of(array_items, object_pairs)


json_value = st.recursive(json_scalar, _extend, max_leaves=40)

deep_array = st.integers(min_value=1900, max_value=2200).map(lambda n: "[" * n + "0" + "]" * n)
deep_object = st.integers(min_value=1900, max_value=2100).map(
    lambda n: ('{"a":' * n) + "0" + ("}" * n)
)

# force repeated json_object_grow_and_rehash(): STARTING_CAPACITY=16,
# item_capacity=11; use enough *unique* keys to grow several times over.
wide_object = st.lists(
    st.tuples(unique_key, json_scalar), min_size=1, max_size=4000, unique_by=lambda t: t[0]
).map(lambda pairs: "{" + ",".join(k + ":" + v for k, v in pairs) + "}")

wide_array = st.lists(json_scalar, min_size=1, max_size=4000).map(
    lambda items: "[" + ",".join(items) + "]"
)

nested_wide_object = st.lists(
    st.tuples(unique_key, wide_array), min_size=1, max_size=40, unique_by=lambda t: t[0]
).map(lambda pairs: "{" + ",".join(k + ":" + v for k, v in pairs) + "}")


@st.composite
def generated_json(draw):
    mode = draw(
        st.sampled_from(
            [
                "value",
                "value",
                "deep_array",
                "deep_object",
                "wide_object",
                "wide_object",
                "wide_array",
                "nested_wide_object",
            ]
        )
    )
    if mode == "deep_array":
        text = draw(deep_array)
    elif mode == "deep_object":
        text = draw(deep_object)
    elif mode == "wide_object":
        text = draw(wide_object)
    elif mode == "wide_array":
        text = draw(wide_array)
    elif mode == "nested_wide_object":
        text = draw(nested_wide_object)
    else:
        text = draw(json_value)
    return text.encode("utf-8", errors="surrogatepass")
