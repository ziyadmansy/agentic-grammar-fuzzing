from hypothesis import strategies as st

# Iteration 5: iteration 4 targeted parson's internal error-cleanup free path
# in isolation -- a single wide, already-rehashed object failing on its final
# duplicate key, or a single deep chain missing its outermost bracket -- and
# found 0 crashes (85/500 accepted, since these are deliberately-broken
# inputs; 0 crashes; 214/500 structural fingerprints). This iteration combines
# those two untested shapes instead of testing them in isolation, and adds a
# third combination iteration 4 didn't cover: a *sibling cascade* free, where
# an array contains several already fully-built, structurally diverse
# children (deep chains, wide objects, long/escaped strings) followed by one
# deliberately duplicate-keyed object -- when parse_array_value sees its
# child fail, it frees the whole array via json_value_free(output_value),
# which in turn frees every already-built sibling recursively in one call,
# not just the single failing object. Specifically:
#   - a chain nested to within a few levels of MAX_NESTING=2048 whose
#     bottom-most element is a wide, multiply-rehashed object that fails on
#     a final duplicate key -- so the free cascades through ~2048 levels of
#     array frees *and* a large json_object_deinit() in one unwind
#   - arrays of several diverse, already-successfully-parsed siblings (some
#     with long/escaped/surrogate string content) followed by one
#     duplicate-keyed object, freed together as soon as the sibling fails
#   - duplicate keys planted at a randomly chosen depth inside a recursive
#     structure, rather than always at the top level or a fixed depth

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
long_string_body = _join(st.lists(safe_char, min_size=200, max_size=4000))
escaped_string_body = st.sampled_from(
    ["\\n\\t\\r\\b\\f", "\\u0000", "\\uffff", "\\ud800\\udc00", "\\ud83d\\ude00"]
)
json_string = st.one_of(safe_string_body, long_string_body, escaped_string_body).map(
    lambda body: '"' + body + '"'
)

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

wide_object_text = st.integers(min_value=10, max_value=1200).flatmap(
    lambda n: st.lists(unique_key, min_size=n, max_size=n, unique_by=lambda k: k).map(
        lambda keys: "{" + ",".join(k + ":0" for k in keys) + "}"
    )
)
wide_object_dup_last = st.integers(min_value=10, max_value=1200).flatmap(
    lambda n: st.lists(unique_key, min_size=n, max_size=n, unique_by=lambda k: k).map(
        lambda keys: "{" + ",".join(k + ":0" for k in keys) + "," + keys[0] + ":1}"
    )
)

# deep chain (near MAX_NESTING) whose bottom is a wide, rehashed object that
# fails on its own final duplicate key: the free cascades through ~2048
# array frees and one large json_object_deinit() in a single unwind.
deep_chain_ending_in_dup_object = st.tuples(
    st.integers(min_value=1900, max_value=2040), wide_object_dup_last
).map(lambda t: ("[" * t[0]) + t[1] + ("]" * (t[0] - 1)))

def small_object_dup(key_strategy):
    return st.lists(key_strategy, min_size=2, max_size=6, unique_by=lambda k: k).map(
        lambda keys: "{" + ",".join(k + ":0" for k in keys) + "," + keys[0] + ":9}"
    )


# array of several already-valid, structurally diverse siblings followed by
# one duplicate-keyed object: the whole array (with all its live siblings)
# is freed together the moment the failing sibling is encountered.
diverse_sibling = st.one_of(json_value, wide_object_text, long_string_body.map(lambda b: '"' + b + '"'))
sibling_cascade = st.lists(diverse_sibling, min_size=3, max_size=12).flatmap(
    lambda siblings: small_object_dup(unique_key).map(
        lambda dup: "[" + ",".join(siblings) + "," + dup + "]"
    )
)

# duplicate key planted at a randomly chosen array- or object-nesting depth,
# rather than always at a fixed depth or only at the top level.
random_depth_array_dup = st.tuples(st.integers(min_value=0, max_value=64), small_object_dup(unique_key)).map(
    lambda t: ("[" * t[0]) + t[1] + ("]" * t[0])
)
random_depth_object_dup = st.tuples(st.integers(min_value=0, max_value=64), small_object_dup(unique_key)).map(
    lambda t: ('{"w":' * t[0]) + t[1] + ("}" * t[0])
)
random_depth_dup_object = st.one_of(random_depth_array_dup, random_depth_object_dup)


@st.composite
def generated_json(draw):
    mode = draw(
        st.sampled_from(
            [
                "value",
                "deep_chain_dup",
                "sibling_cascade",
                "sibling_cascade",
                "random_depth_dup",
                "wide_object_dup_last",
            ]
        )
    )
    if mode == "deep_chain_dup":
        text = draw(deep_chain_ending_in_dup_object)
    elif mode == "sibling_cascade":
        text = draw(sibling_cascade)
    elif mode == "random_depth_dup":
        text = draw(random_depth_dup_object)
    elif mode == "wide_object_dup_last":
        text = draw(wide_object_dup_last)
    else:
        text = draw(json_value)
    return text.encode("utf-8", errors="surrogatepass")
