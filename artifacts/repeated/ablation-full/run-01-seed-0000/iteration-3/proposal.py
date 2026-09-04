from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)
    # STRING: use Hypothesis text with safe codepoints, escape as JSON string
    def json_string():
        # Use a limited set of safe characters to avoid control chars
        # Escape backslash and double quotes
        def escape_json_str(s: str) -> str:
            # Escape backslash and double quotes and control chars
            s = s.replace("\\", "\\\\").replace('"', '\\"')
            # Replace control chars with escape sequences
            s = s.replace("\b", "\\b").replace("\f", "\\f").replace("\n", "\\n")
            s = s.replace("\r", "\\r").replace("\t", "\\t")
            return s
        s = draw(st.text(
            alphabet=st.characters(
                blacklist_categories=('Cs', 'Cc'),  # no surrogates or control chars
                blacklist_characters=['"', '\\']
            ),
            min_size=0,
            max_size=20,
        ))
        return '"' + escape_json_str(s) + '"'

    json_string_st = st.deferred(json_string)

    # Forward declaration for recursive structures
    # We'll define value recursively with bounded depth using st.recursive

    # Base values for recursion
    base = st.one_of(
        json_string_st,
        json_number,
        json_null,
        json_true,
        json_false,
    )

    # Recursive containers: objects and arrays
    # To keep size bounded, limit max size of containers
    def json_obj():
        # pair: STRING ':' value
        # Use small dicts with max 3 pairs
        keys = st.lists(
            st.text(
                alphabet=st.characters(
                    blacklist_categories=('Cs', 'Cc'),
                    blacklist_characters=['"', '\\']
                ),
                min_size=1,
                max_size=10,
            ),
            min_size=0,
            max_size=3,
            unique=True,
        )
        def pairs(keys_list, values_list):
            # keys_list and values_list are lists of same length
            pairs_strs = []
            for k, v in zip(keys_list, values_list):
                # Escape keys same as string
                def escape_json_str(s: str) -> str:
                    s = s.replace("\\", "\\\\").replace('"', '\\"')
                    s = s.replace("\b", "\\b").replace("\f", "\\f").replace("\n", "\\n")
                    s = s.replace("\r", "\\r").replace("\t", "\\t")
                    return s
                k_esc = '"' + escape_json_str(k) + '"'
                pairs_strs.append(f"{k_esc}:{v}")
            return "{" + ",".join(pairs_strs) + "}"
        return st.tuples(keys, st.lists(value, min_size=0, max_size=3)).map(lambda kv: pairs(*kv))

    def json_arr():
        # arrays with max 4 elements
        return st.lists(value, min_size=0, max_size=4).map(lambda vs: "[" + ",".join(vs) + "]")

    # Compose value recursively
    value = st.recursive(
        base,
        lambda children: st.one_of(json_obj(), json_arr()),
        max_leaves=10,
    )

    # Draw the final JSON string and encode as bytes
    s = draw(value)
    return s.encode("utf-8")