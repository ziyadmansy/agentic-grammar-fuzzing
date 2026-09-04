from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.from_regex(
        r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?",
        fullmatch=True,
    )
    # STRING: roughly matching the grammar (no control chars, escapes limited)
    # We'll generate Python strings and then encode with json.dumps to get valid JSON strings.
    # But since we cannot import json (not forbidden, but let's do manual escapes),
    # we produce simple strings with safe characters and some escapes.
    # We'll produce strings with safe codepoints plus some escapes.
    def json_string():
        # safe codepoints excluding control chars and quotes/backslash
        safe_chars = (
            " !#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"
        )
        # We'll allow some escapes: \\, \", \b, \f, \n, \r, \t
        # To keep it simple, generate strings with safe chars + occasional escapes
        base_str = st.text(safe_chars, min_size=0, max_size=20)
        # Insert escapes randomly
        escapes = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Compose a string with some escapes inserted at random positions
        def insert_escapes(s):
            # Insert 0 to 3 escapes randomly
            import random
            s = list(s)
            for _ in range(random.randint(0, 3)):
                pos = random.randint(0, len(s))
                esc = draw(escapes)
                s.insert(pos, esc)
            return "".join(s)
        # We cannot use draw inside insert_escapes, so instead:
        # We'll generate a list of chunks: either safe chars or escapes
        # Compose a list of length up to 25, each element either safe char chunk or escape
        chunk = st.one_of(
            st.text(safe_chars, min_size=1, max_size=5),
            escapes,
        )
        chunks = st.lists(chunk, min_size=0, max_size=10).map("".join)
        s = draw(chunks)
        # Wrap in quotes
        return f'"{s}"'

    json_string_st = st.deferred(lambda: st.builds(lambda s: s, json_string()))

    # Recursive JSON value strategy
    # We'll use st.recursive to build nested arrays and objects
    # Limit max depth and size to keep campaign bounded

    # Base values
    base = st.one_of(
        json_string_st,
        json_number,
        json_null,
        json_true,
        json_false,
    )

    # Recursive containers
    def json_obj():
        # pair: STRING ':' value
        # We'll generate pairs as (string, value) and format as JSON text
        # Limit number of pairs to keep size bounded
        pairs = st.dictionaries(
            keys=json_string_st.map(lambda s: s[1:-1]),  # remove quotes for keys
            values=values,
            max_size=5,
            # keys must be unique, dict ensures that
        )
        def to_obj_text(d):
            if not d:
                return "{}"
            items = []
            for k, v in d.items():
                # k is unquoted string, v is JSON text string
                # re-quote k with quotes (already quoted in keys? no, we removed quotes)
                # so re-quote with json_string style
                # We can reuse json_string_st to quote keys, but simpler:
                # Escape backslash and quote in keys:
                esc_k = k.replace("\\", "\\\\").replace('"', '\\"')
                items.append(f'"{esc_k}":{v}')
            return "{" + ",".join(items) + "}"
        return pairs.map(to_obj_text)

    def json_arr():
        # array of values, max size 5
        arrs = st.lists(values, max_size=5)
        def to_arr_text(lst):
            return "[" + ",".join(lst) + "]"
        return arrs.map(to_arr_text)

    values = st.recursive(
        base,
        lambda children: st.one_of(json_obj(), json_arr()),
        max_leaves=10,
    )

    # Compose full JSON text with EOF
    json_text = values.map(lambda s: s)

    s = draw(json_text)
    return s.encode("utf-8")