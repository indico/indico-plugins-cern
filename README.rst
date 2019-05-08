CERN Indico Plugins
===================

|build-status| |license|

This repository contains all the CERN-specific plugins for `Indico`_.
If you are looking for plugins for your own Indico instance, please
go to the `indico-plugins`_ repo instead.

Note that these plugins are used for integration with specific parts of
the CERN infrastructure, so installing them on your own Indico instance
is not recommended as they will not be usable there.

We decided to make them public anyway, as they provide great examples
for more complex plugins and if you plan to write your own plugins,
you may benefit from looking at the code.

These plugins are licensed under the MIT license.

Note
----

In applying the MIT license, CERN does not waive the privileges and immunities
granted to it by virtue of its status as an Intergovernmental Organization
or submit itself to any jurisdiction.

.. _Indico: https://github.com/indico/indico
.. _indico-plugins: https://github.com/indico/indico-plugins
.. |build-status| image:: https://img.shields.io/travis/indico/indico-plugins-cern/master.svg
                   :alt: Travis Build Status
                   :target: https://travis-ci.org/indico/indico-plugins-cern
.. |license| image:: https://img.shields.io/github/license/indico/indico-plugins-cern.svg
                   :alt: License
                   :target: https://github.com/indico/indico-plugins-cern/blob/master/LICENSE
