# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2020 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import httpretty as httpretty_
import pytest


@pytest.yield_fixture
def httpretty():
    httpretty_.reset()
    httpretty_.enable()
    try:
        yield httpretty_
    finally:
        httpretty_.disable()
