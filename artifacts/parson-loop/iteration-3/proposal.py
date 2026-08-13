from hypothesis import strategies as st

# Iteration 3: iterations 1-2 covered numeric/escape edge cases, deep nesting
# near/at/over MAX_NESTING=2048, and wide objects/arrays forcing several
# json_object_grow_and_rehash()/json_array_resize() calls (0 crashes so far).
# This iteration adds: (a) shared-prefix keys to stress hash-bucket linear
# probing specifically (not just triggering resize), (b) combined wide+deep
# structures (wide objects nested inside deep arrays and vice versa), and
# (c) surrogate-pair escapes positioned at the exact end of a string's
# content (right before the closing quote) to stress the boundary between
# parse_utf16's raw pointer walk and process_string's input_len tracking.

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
)

safe_char = st.characters(min_codepoint=0x20, max_codepoint=0x7E, exclude_characters='"\\')
safe_string_body = _join(st.lists(safe_char, max_size=32))

# surrogate escapes glued to the closing quote, and truncated second-escapes,
# to probe the boundary between parse_utf16's raw walk and the string's own
# input_len-bounded content.
boundary_string_body = st.sampled_from(
    [
        "\\ud800",
        "\\udbff",
        "\\ud800\\u",
        "\\ud800\\ud",
        "\\ud800\\ud8",
        "\\ud800\\ud80",
        "\\ud800\\udc00",
        "\\udbff\\udfff",
        "x\\ud800",
        "\\ud800x",
    ]
)

json_string = st.one_of(safe_string_body, boundary_string_body).map(lambda body: '"' + body + '"')

short_key_char = st.sampled_from("ab")
shared_prefix_key = st.tuples(
    st.just("shared_prefix_key_"), _join(st.lists(short_key_char, min_size=1, max_size=4))
).map(lambda t: '"' + t[0] + t[1] + '"')

json_scalar = st.one_of(
    st.just("null"),
    st.just("true"),
    st.just("false"),
    json_number,
    json_string,
)


def _extend(children):
    array_items = st.lists(children, max_size=6).map(lambda items: "[" + ",".join(items) + "]")
    object_pairs = st.lists(st.tuples(shared_prefix_key, children), max_size=6, unique_by=lambda t: t[0]).map(
        lambda pairs: "{" + ",".join(k + ":" + v for k, v in pairs) + "}"
    )
    return st.one_of(array_items, object_pairs)


json_value = st.recursive(json_scalar, _extend, max_leaves=30)

# many keys sharing a hash-colliding prefix, forced through several rehashes
wide_collision_object = st.lists(
    shared_prefix_key, min_size=20, max_size=200, unique_by=lambda k: k
).map(lambda keys: "{" + ",".join(k + ":0" for k in keys) + "}")

deep_array = st.integers(min_value=1900, max_value=2100).map(lambda n: "[" * n + "0" + "]" * n)

# wide object nested inside a moderately deep array, and vice versa
wide_in_deep = st.tuples(
    st.integers(min_value=50, max_value=200),
    st.lists(shared_prefix_key, min_size=10, max_size=60, unique_by=lambda k: k),
).map(lambda t: ("[" * t[0]) + "{" + ",".join(k + ":0" for k in t[1]) + "}" + ("]" * t[0]))

deep_in_wide = st.lists(
    st.integers(min_value=200, max_value=600), min_size=5, max_size=15
).map(lambda depths: "[" + ",".join("[" * d + "0" + "]" * d for d in depths) + "]")


@st.composite
def generated_json(draw):
    mode = draw(
        st.sampled_from(
            [
                "value",
                "value",
                "deep_array",
                "wide_collision_object",
                "wide_collision_object",
                "wide_in_deep",
                "deep_in_wide",
            ]
        )
    )
    if mode == "deep_array":
        text = draw(deep_array)
    elif mode == "wide_collision_object":
        text = draw(wide_collision_object)
    elif mode == "wide_in_deep":
        text = draw(wide_in_deep)
    elif mode == "deep_in_wide":
        text = draw(deep_in_wide)
    else:
        text = draw(json_value)
    return text.encode("utf-8", errors="surrogatepass")
