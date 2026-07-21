"""Email template rendering.

Templates are defined inline (Jinja2) so the service is self-contained. Each
template renders both an HTML and a plain-text body.
"""

from __future__ import annotations

from jinja2 import Environment, select_autoescape

_env = Environment(autoescape=select_autoescape(["html"]))

_BASE_HTML = """\
<div style="font-family:system-ui,sans-serif;max-width:480px;margin:auto">
  <h2>{{ heading }}</h2>
  <p>{{ intro }}</p>
  <p><a href="{{ url }}" style="background:#7c3aed;color:#fff;padding:10px 16px;
     border-radius:6px;text-decoration:none;display:inline-block">{{ cta }}</a></p>
  <p style="color:#666;font-size:12px">{{ footer }}</p>
</div>
"""

_BASE_TEXT = """\
{{ heading }}

{{ intro }}

{{ cta }}: {{ url }}

{{ footer }}
"""

_html_tmpl = _env.from_string(_BASE_HTML)
_text_tmpl = _env.from_string(_BASE_TEXT)


def render(
    *, heading: str, intro: str, cta: str, url: str, footer: str
) -> tuple[str, str]:
    """Render ``(html, text)`` bodies for a call-to-action email."""
    ctx = {"heading": heading, "intro": intro, "cta": cta, "url": url, "footer": footer}
    return _html_tmpl.render(**ctx), _text_tmpl.render(**ctx)
