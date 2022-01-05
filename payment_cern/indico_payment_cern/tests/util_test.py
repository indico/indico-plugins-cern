# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2022 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from unittest.mock import MagicMock

import pytest

from indico_payment_cern.util import get_order_id


@pytest.mark.parametrize(('event_id', 'registration_id', 'prefix', 'name', 'expected'), (
    (1,   2,   '',  'Foo Bar',                         'BARFOOc1r2'),
    (123, 456, 'x', 'Foo Bar',                         'XBARFOOc123r456'),
    (123, 456, '',  'FooVeryLongName BarVeryLongName', 'BARVERYLONGNAMEFOOVERYc123r456'),
    (123, 456, 'x', 'FooVeryLongName BarVeryLongName', 'XBARVERYLONGNAMEFOOVERc123r456'),
))
def test_get_order_id(event_id, registration_id, prefix, name, expected):
    first_name, last_name = name.split(' ', 1)
    registration = MagicMock(event_id=event_id, id=registration_id, first_name=first_name, last_name=last_name)
    order_id = get_order_id(registration, prefix)
    assert len(order_id) <= 30
    assert order_id == expected
