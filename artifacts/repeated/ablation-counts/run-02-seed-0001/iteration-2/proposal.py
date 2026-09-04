from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: use Hypothesis text with safe unicode codepoints excluding control chars and quotes/backslash
    # SAFECODEPOINT ~["\\\u0000-\u001F], so exclude control chars and backslash and quote
    # We'll generate strings without control chars, backslash, or quote
    safe_char = st.characters(
        blacklist_characters=['\\', '"'],
        min_codepoint=0x20,
        max_codepoint=0x10FFFF,
    )
    json_string = st.text(safe_char).map(lambda s: '"' + s + '"')

    # NUMBER: use Hypothesis floats and ints, then convert to JSON number strings
    # We'll generate numbers as strings matching the grammar
    def number_to_json(n):
        # Convert int or float to JSON number string
        # Use repr to get minimal representation
        if isinstance(n, int):
            return str(n)
        else:
            # Use repr for floats, but ensure no trailing .0 if int-like
            s = repr(n)
            # JSON allows exponent notation, repr may produce it
            return s

    json_number = st.one_of(
        st.integers(min_value=-(10**10), max_value=10**10).map(number_to_json),
        st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e10,
            max_value=1e10,
        ).map(number_to_json),
    )

    # Recursive JSON value strategy
    # We'll use st.recursive with a max depth and max size to avoid recursion errors

    # Forward declaration for value
    # value = STRING | NUMBER | obj | arr | true | false | null

    # Base values for recursion
    base = st.one_of(json_string, json_number, json_true, json_false, json_null)

    # To build obj and arr, we need to define pair and value recursively

    # pair: STRING ':' value
    # We'll define pair as a tuple of (string, value) and then format as JSON

    # We'll define a helper composite for pair to ensure valid formatting
    @st.composite
    def pair(draw):
        k = draw(json_string)
        v = draw(value)
        return f"{k}:{v}"

    # obj: '{' pair (',' pair)* '}' | '{}'
    # arr: '[' value (',' value)* ']' | '[]'

    # We'll define obj and arr as strategies producing strings

    def obj_strategy(children):
        # children is a strategy producing pairs (strings)
        # produce either empty object or object with 1 to 3 pairs (bounded)
        return st.one_of(
            st.just("{}"),
            st.lists(children, min_size=1, max_size=3).map(
                lambda pairs: "{" + ",".join(pairs) + "}"
            ),
        )

    def arr_strategy(children):
        # children is a strategy producing values (strings)
        # produce either empty array or array with 1 to 3 values (bounded)
        return st.one_of(
            st.just("[]"),
            st.lists(children, min_size=1, max_size=3).map(
                lambda values: "[" + ",".join(values) + "]"
            ),
        )

    # Now define value recursively
    # We use st.recursive with base and extend with obj and arr

    # We need to define value before pair because pair depends on value
    # We'll use a trick: define value as a variable, then assign it after pair is defined

    # Placeholder for value strategy
    value = None

    # Define value as recursive
    def value_strategy():
        # base values
        base_values = base

        # recursive step: obj and arr
        # pair depends on value, so we define pair here with value placeholder
        @st.composite
        def pair_inner(draw):
            k = draw(json_string)
            v = draw(value)
            return f"{k}:{v}"

        obj_strat = obj_strategy(pair_inner())
        arr_strat = arr_strategy(value)

        return st.recursive(
            base_values,
            lambda children: st.one_of(obj_strat, arr_strat),
            max_leaves=10,
        )

    value = value_strategy()

    # Finally, draw a value and encode as bytes
    s = draw(value)
    return s.encode("utf-8")