"""The Pages site: docs/index.html offers both places to read, docs/article/index.html is article.md as a page.
Needs the `markdown` package, only to run this. Run it after changing article.md and commit what it writes."""
from __future__ import annotations

import html
import re
from pathlib import Path

import markdown
import yaml

HERE = Path(__file__).parent
DOCS = HERE.parent
DEV_URL = "https://dev.to/blaiselabs/a-float-broke-my-refund-rule-and-leviticus-had-an-opinion-1399"
RAW = "https://raw.githubusercontent.com/BlaiseLabs/specdeck-spirit/main/docs/article/"

GITHUB_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/></svg>'
DEV_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7.42 10.05c-.18-.16-.46-.23-.84-.23H6l.02 2.44.04 2.45.56-.02c.41 0 .63-.07.83-.26.24-.24.26-.36.26-2.2 0-1.91-.02-1.96-.29-2.18zM0 4.94v14.12h24V4.94H0zM8.56 15.3c-.44.58-1.06.77-2.53.77H4.71V8.53h1.4c1.67 0 2.16.18 2.6.9.27.43.29.6.32 2.57.05 2.23-.02 2.73-.47 3.3zm5.09-5.47h-2.47v1.77h1.52v1.28l-.72.04-.75.03v1.77l1.22.03 1.2.04v1.28h-1.6c-1.53 0-1.6-.01-1.87-.3l-.3-.28v-3.16c0-3.02.01-3.18.25-3.48.23-.31.25-.31 1.88-.31h1.64v1.3zm4.68 5.45c-.17.43-.64.79-1 .79-.18 0-.45-.15-.67-.39-.32-.32-.45-.63-.82-2.08l-.9-3.39-.45-1.67h.76c.4 0 .75.02.75.05 0 .06 1.16 4.54 1.26 4.83.04.15.32-.7.73-2.3l.66-2.52.74-.04c.4-.02.73 0 .73.04 0 .14-1.67 6.38-1.8 6.68z"/></svg>'

BASE = """:root { color-scheme: light dark; --bg: #faf8f4; --ink: #22201c; --soft: #6b665c; --line: #ddd8cc; --card: #fff; --code: #f1eee7; --link: #1f5fa8; }
@media (prefers-color-scheme: dark) { :root { --bg: #17161a; --ink: #ece9e2; --soft: #a5a097; --line: #37353a; --card: #211f24; --code: #29272c; --link: #8ab8ec; } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 18px/1.65 Georgia, "Times New Roman", serif; }
a { color: var(--link); }
"""

ROOT_CSS = BASE + """body { min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 32px 20px; }
main { width: 100%; max-width: 760px; text-align: center; }
h1 { text-wrap: balance; font-size: clamp(30px, 6vw, 46px); line-height: 1.15; margin: 0 0 12px; font-weight: normal; }
p.sub { color: var(--soft); margin: 0 0 40px; }
.choices { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 20px; }
.choice { display: block; padding: 36px 24px 30px; background: var(--card); border: 1px solid var(--line); border-radius: 10px; color: inherit; text-decoration: none; }
.choice:hover, .choice:focus-visible { border-color: var(--link); }
.choice svg { display: block; width: 72px; height: 72px; margin: 0 auto 20px; fill: currentColor; }
.choice strong { display: block; font-weight: normal; font-size: 23px; line-height: 1.3; }
.choice small { display: block; margin-top: 6px; color: var(--soft); font-size: 15px; }
"""

ARTICLE_CSS = BASE + """main { max-width: 720px; margin: 0 auto; padding: 32px 20px 72px; }
nav { font-size: 15px; margin-bottom: 28px; }
h1 { text-wrap: balance; font-size: clamp(30px, 6vw, 42px); line-height: 1.15; margin: 0 0 28px; font-weight: normal; }
h2 { font-size: 27px; line-height: 1.25; margin: 44px 0 12px; font-weight: normal; }
h3 { font-size: 21px; margin: 32px 0 8px; font-weight: normal; }
img { max-width: 100%; height: auto; border-radius: 6px; }
code { font: 0.86em/1.5 ui-monospace, Menlo, Consolas, monospace; background: var(--code); padding: 2px 4px; border-radius: 3px; }
pre { background: var(--code); padding: 14px 16px; border-radius: 6px; overflow-x: auto; }
pre code { background: none; padding: 0; }
table { display: block; overflow-x: auto; border-collapse: collapse; font-size: 16px; line-height: 1.45; }
th, td { border: 1px solid var(--line); padding: 8px 10px; text-align: left; vertical-align: top; }
"""

ROOT = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<style>
{css}</style>
</head>
<body>
<main>
<h1>{title}</h1>
<p class="sub">The same article, in two places.</p>
<div class="choices">
<a class="choice" href="article/">{github}<strong>Read on GitHub Pages</strong><small>No account needed</small></a>
<a class="choice" href="{dev}">{devicon}<strong>Read on DEV</strong><small>All likes are appreciated</small></a>
</div>
</main>
</body>
</html>
"""

ARTICLE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{dev}">
<style>
{css}</style>
</head>
<body>
<main>
<nav><a href="../">Back</a></nav>
<h1>{title}</h1>
{body}
</main>
</body>
</html>
"""


def main() -> None:
    _, front, text = (HERE / "article.md").read_text(encoding="utf-8").split("---\n", 2)
    title = html.escape(yaml.safe_load(front)["title"])
    desc = "A fork of specdeck that reads the reason behind each rule next to a spiritual text you choose, with Gemma running locally."
    text = text.replace(RAW, "")
    text = re.sub(r"\{% github (\S+) %\}", r"[github.com/\1](https://github.com/\1)", text)
    body = markdown.markdown(text, extensions=["fenced_code", "tables", "sane_lists"])

    (DOCS / ".nojekyll").write_text("")
    (HERE / "index.html").write_text(ARTICLE.format(title=title, desc=desc, dev=DEV_URL, css=ARTICLE_CSS, body=body), encoding="utf-8")
    (DOCS / "index.html").write_text(ROOT.format(title=title, desc=desc, dev=DEV_URL, css=ROOT_CSS, github=GITHUB_ICON, devicon=DEV_ICON), encoding="utf-8")


if __name__ == "__main__":
    main()
