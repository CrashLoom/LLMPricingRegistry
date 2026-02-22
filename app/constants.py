SUPPORTED_BILLABLE_DIMENSIONS = {
    "input_tokens_uncached",
    "input_tokens_cached",
    "output_tokens",
    "reasoning_tokens",
    "embedding_tokens",
    "tool_calls",
    "image_count",
    "image_megapixels",
    "audio_input_seconds",
    "audio_output_seconds",
    "requests",
}

MAX_DIMENSION_QUANTITY = 10_000_000_000
MAX_BATCH_SIZE = 100
MAX_REQUEST_BODY_BYTES = 1_048_576
