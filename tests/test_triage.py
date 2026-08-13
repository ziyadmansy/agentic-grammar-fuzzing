from agentic_fuzzing.triage import sanitizer_signature, signature_id


def test_sanitizer_signature_removes_volatile_values() -> None:
    first = b"SUMMARY: AddressSanitizer: heap-buffer-overflow 0x1234\n#0 foo file.c:42\n"
    second = b"SUMMARY: AddressSanitizer: heap-buffer-overflow 0xabcd\n#0 foo file.c:99\n"

    assert sanitizer_signature(first) == sanitizer_signature(second)
    assert signature_id(first) == signature_id(second)