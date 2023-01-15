#!/bin/bash
# Testing the QSlang cli

# fail on error
set -e

# print commands
set -x

# set environment variable to disable plotting
export MPLBACKEND=Agg

FLAGS="--testing"

# print help
qslang $FLAGS --help

# list all substances
qslang $FLAGS substances

# print summary
qslang $FLAGS summary --substances caffeine

# list events
qslang $FLAGS events --substances caffeine

# list effectspans of common substance
qslang $FLAGS effectspan --substances caffeine

# plots
qslang $FLAGS plot --substances caffeine
qslang $FLAGS plot-calendar --substances caffeine
qslang $FLAGS plot-effectspan --substances caffeine

# old tests
qslang $FLAGS plot --substances caffeine
qslang $FLAGS plot --count --substances caffeine
qslang $FLAGS plot --days --substances caffeine
