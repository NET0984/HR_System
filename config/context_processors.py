from pathlib import Path

from django.conf import settings


def static_version(request):
    css_file = Path(settings.BASE_DIR) / 'static' / 'css' / 'style.css'
    try:
        version = int(css_file.stat().st_mtime)
    except OSError:
        version = 0
    return {'static_version': version}
