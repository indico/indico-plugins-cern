# This file is part of Indico.
# Copyright (C) 2002 - 2015 European Organization for Nuclear Research (CERN).
#
# Indico is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 3 of the
# License, or (at your option) any later version.
#
# Indico is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Indico; if not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

import pytest
from mock import MagicMock

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
