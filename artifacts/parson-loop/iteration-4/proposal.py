from hypothesis import strategies as st

# Iteration 4: iterations 1-3 reached 0 crashes with high acceptance rates
# (57%/68%/88%) by targeting the *parse* path. Every accepted input in those
# iterations was freed exactly once, via the harness's own top-level
# json_value_free() call, after a completely well-formed parse -- the
# free-path/deallocation angle from the README's "what's next" notes has
# never actually been stressed differently from the parse path. What *is*
# genuinely untested is parson's *internal* error-cleanup calls to
# json_value_free()/json_object_free() scattered through
# parse_object_value()/parse_array_value(): when a deep or wide structure
# parses almost entirely correctly and then fails right at the very end (a
# missing final closing bracket, or a duplicate key appearing only after many
# unique ones were already added), parson frees the entire partially/fully
# built subtree from *inside* the parser itself, before ever returning to the
# harness -- a different call path than the harness's single top-level free.
# This iteration deliberately builds large valid prefixes (deep nesting near
# MAX_NESTING=2048, wide objects that have already gone through several
# json_object_grow_and_rehash() calls) and corrupts only the very end, so:
#   - a wide object that fails on a final duplicate key is freed via
#     json_object_deinit() with count == n fully-populated, already-rehashed
#     slots (json_object_add's failure branch: parson_free(new_key);
#     json_value_free(new_value); json_value_free(output_value);)
#   - a deep array/object missing its outermost closing bracket is freed at
#     its full depth from inside parse_array_value/parse_object_value's own
#     "**string != ']'/'}' " failure branch, not from the harness
#   - small/early duplicate-key failures cover the other end of the
#     partially-built-object state space (count == 1, 2, ... before growth
#     ever triggers)

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
    _join(st.lists(digit, min_size=1, max_size=5)),
).map(lambda t: t[0] + t[1] + t[2])

json_number = st.one_of(
    st.tuples(st.sampled_from(["", "-"]), int_part).map(lambda t: t[0] + t[1]),
    st.tuples(st.sampled_from(["", "-"]), int_part, frac_part).map(lambda t: t[0] + t[1] + t[2]),
    st.tuples(st.sampled_from(["", "-"]), int_part, exp_part).map(lambda t: t[0] + t[1] + t[2]),
)

safe_char = st.characters(min_codepoint=0x20, max_codepoint=0x7E, exclude_characters='"\\')
safe_string_body = _join(st.lists(safe_char, max_size=24))
json_string = safe_string_body.map(lambda body: '"' + body + '"')

short_key_char = st.sampled_from("abcdefghijklmnopqrstuvwxyz")
unique_key = _join(st.lists(short_key_char, min_size=1, max_size=4)).map(lambda body: '"' + body + '"')

json_scalar = st.one_of(st.just("null"), st.just("true"), st.just("false"), json_number, json_string)


def _extend(children):
    array_items = st.lists(children, max_size=5).map(lambda items: "[" + ",".join(items) + "]")
    object_pairs = st.lists(
        st.tuples(unique_key, children), max_size=5, unique_by=lambda t: t[0]
    ).map(lambda pairs: "{" + ",".join(k + ":" + v for k, v in pairs) + "}")
    return st.one_of(array_items, object_pairs)


json_value = st.recursive(json_scalar, _extend, max_leaves=24)

# a deep chain missing exactly its outermost closing bracket: every level
# parses successfully, then the outermost parse_array_value/parse_object_value
# frees the whole built-up subtree from its own failure branch.
deep_array_broken = st.integers(min_value=1500, max_value=2048).map(
    lambda n: "[" * n + "0" + "]" * (n - 1)
)
deep_object_broken = st.integers(min_value=1500, max_value=2048).map(
    lambda n: '{"a":' * n + "0" + "}" * (n - 1)
)

# a wide object that succeeds on n unique keys (crossing several
# STARTING_CAPACITY=16/item_capacity=11 growth boundaries) and then fails on
# a final duplicate of its first key -- frees a fully-populated,
# already-rehashed hash table from inside json_object_add's failure branch.
wide_object_dup_last = st.integers(min_value=10, max_value=1200).flatmap(
    lambda n: st.lists(unique_key, min_size=n, max_size=n, unique_by=lambda k: k).map(
        lambda keys: "{" + ",".join(k + ":0" for k in keys) + "," + keys[0] + ":1}"
    )
)

# same idea, but the duplicate appears after only a couple of successful
# inserts -- covers the small/partially-built end of the failure state space.
small_object_dup_early = st.lists(
    unique_key, min_size=2, max_size=6, unique_by=lambda k: k
).map(lambda keys: "{" + ",".join(k + ":0" for k in keys) + "," + keys[0] + ":9}")

# wide+deep combined: a moderately deep chain of single-key objects bottoming
# out in a wide, already-rehashed object, corrupted at the outermost level so
# the whole mixed-shape subtree frees in one recursive unwind.
wide_in_deep_broken = st.tuples(
    st.integers(min_value=200, max_value=600),
    st.lists(unique_key, min_size=20, max_size=200, unique_by=lambda k: k),
).map(
    lambda t: ('{"a":' * t[0])
    + "{"
    + ",".join(k + ":0" for k in t[1])
    + "}"
    + ("}" * (t[0] - 1))
)

# a duplicate key nested several array levels deep inside an otherwise valid
# document, so the failure unwinds through multiple live parent frames before
# the duplicate-carrying object is the one actually freed.
nested_dup_object = st.tuples(
    st.integers(min_value=1, max_value=20),
    st.lists(unique_key, min_size=3, max_size=30, unique_by=lambda k: k),
).map(
    lambda t: ("[" * t[0])
    + "{"
    + ",".join(k + ":0" for k in t[1])
    + "," + t[1][0] + ":9}"
    + ("]" * t[0])
)


@st.composite
def generated_json(draw):
    mode = draw(
        st.sampled_from(
            [
                "value",
                "deep_array_broken",
                "deep_object_broken",
                "wide_object_dup_last",
                "wide_object_dup_last",
                "small_object_dup_early",
                "wide_in_deep_broken",
                "nested_dup_object",
            ]
        )
    )
    if mode == "deep_array_broken":
        text = draw(deep_array_broken)
    elif mode == "deep_object_broken":
        text = draw(deep_object_broken)
    elif mode == "wide_object_dup_last":
        text = draw(wide_object_dup_last)
    elif mode == "small_object_dup_early":
        text = draw(small_object_dup_early)
    elif mode == "wide_in_deep_broken":
        text = draw(wide_in_deep_broken)
    elif mode == "nested_dup_object":
        text = draw(nested_dup_object)
    else:
        text = draw(json_value)
    return text.encode("utf-8", errors="surrogatepass")
