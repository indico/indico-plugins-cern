# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2023 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import os


def get_pdf_title(attachment):
    name, ext = os.path.splitext(attachment.file.filename)
    if attachment.title.endswith(ext):
        return attachment.title[:-len(ext)] + '.pdf'
    else:
        return attachment.title
