# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2023 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import pytest

from indico_cern_access.util import sanitize_license_plate


@pytest.mark.parametrize(('input', 'expected'), [
    ('1234 56', '123456'),
    ('ABC DEF', 'ABCDEF'),
    ('IAm-G0D', 'IAMG0D'),
    ('ge 58 1234', 'GE581234'),
    ('BBQ PLZ-', 'BBQPLZ')
])
def test_license_plate_handling(input, expected):
    assert sanitize_license_plate(input) == expected


def test_license_plate_handling_error():
    assert sanitize_license_plate('') is None
    assert sanitize_license_plate('------') is None
    assert sanitize_license_plate('123/456') is None
    assert sanitize_license_plate('VALID 1234 \U0001F4A9') is None
