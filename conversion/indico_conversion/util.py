from __future__ import unicode_literals

import os


def get_pdf_title(attachment):
    name, ext = os.path.splitext(attachment.file.filename)
    if attachment.title.endswith(ext):
        return attachment.title[:-len(ext)] + '.pdf'
    else:
        return attachment.title
