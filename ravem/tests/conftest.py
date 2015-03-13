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
