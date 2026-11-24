#!/bin/sh
# Build the talk: sh build.sh [--script | --shots | --no-voice | --voice=NAME | --import-voice=NAME | --bundle=voice|clips|both | ...]
# (options: see the top of narrate.py). Add a --with for every package figures.py imports.
cd "$(dirname "$0")" && exec uv run --no-project --with kokoro-onnx --with soundfile --with pyyaml --with matplotlib \
    --with pillow python narrate.py "$@"
