import os
from urllib.parse import unquote, urlparse

from xhtml2pdf.files import pisaFileObject


_PATCHED = False


def _local_font_path(file_object):
    uri = getattr(file_object, 'uri', None)
    if not uri:
        return None
    if uri.startswith('file:'):
        uri = unquote(urlparse(uri).path)
    if isinstance(uri, str) and os.path.isfile(uri):
        return uri
    return None


def _get_named_file(self):
    local = _local_font_path(self)
    if local:
        return local
    tmp = self.instance.get_named_tmp_file()
    return tmp.name if tmp else None


def enable_local_font_files():
    global _PATCHED
    if _PATCHED:
        return
    pisaFileObject.getNamedFile = _get_named_file
    _PATCHED = True
