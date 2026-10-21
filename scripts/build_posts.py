"""Build the static blog from trusted Markdown files in posts/."""

import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import shutil

import markdown
import yaml


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "_site"
COVERS = {"desk", "hills", "leaves", "coffee"}


def text_field(meta, key, default=None):
    value = meta.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value.strip()


def read_post(path):
    source = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    match = re.match(r"\A---\n(.*?)\n---(?:\n|\Z)(.*)\Z", source, re.S)
    if not match:
        raise ValueError("missing YAML front matter enclosed by ---")
    meta = yaml.safe_load(match[1])
    if not isinstance(meta, dict):
        raise ValueError("front matter must be a mapping")
    draft = meta.get("draft", False)
    if not isinstance(draft, bool):
        raise ValueError("draft must be true or false (without quotes)")
    if draft:
        return None
    slug = path.stem
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise ValueError("filename must use lowercase letters, digits and hyphens")
    title = text_field(meta, "title")
    date_value = meta.get("date")
    if isinstance(date_value, datetime.datetime):
        date_value = date_value.date()
    if isinstance(date_value, datetime.date):
        date_value = date_value.isoformat()
    if not isinstance(date_value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_value):
        raise ValueError("date must be YYYY-MM-DD")
    datetime.date.fromisoformat(date_value)
    tags = meta.get("tags", [])
    if not isinstance(tags, list) or any(not isinstance(t, str) or not t.strip() for t in tags):
        raise ValueError("tags must be a list of non-empty strings")
    cover = text_field(meta, "cover", "desk")
    if cover not in COVERS:
        cover_path = (ROOT / cover).resolve()
        assets_path = (ROOT / "assets").resolve()
        if (
            not cover.startswith("assets/")
            or "\\" in cover
            or not cover_path.is_relative_to(assets_path)
            or cover_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".svg"}
            or not cover_path.is_file()
        ):
            raise ValueError("cover must be a built-in name or an existing image inside assets/")
    body = match[2].strip()
    if not body:
        raise ValueError("article body is empty")
    # Raw HTML is supported: only trusted repository authors should add posts.
    rendered = markdown.markdown(body, extensions=["extra", "sane_lists"])
    return {
        "id": slug,
        "title": title,
        "date": date_value,
        "category": text_field(meta, "category", "技术手记"),
        "tags": [t.strip() for t in tags],
        "cover": cover,
        "excerpt": text_field(meta, "excerpt", title),
        "time": max(1, math.ceil(len(re.sub(r"\s+", "", body)) / 400)),
        "body": rendered,
    }


def main():
    posts = []
    for path in sorted((ROOT / "posts").glob("*.md")):
        try:
            post = read_post(path)
        except (ValueError, yaml.YAMLError) as error:
            raise SystemExit(f"{path.relative_to(ROOT)}: {error}") from error
        if post:
            posts.append(post)
    posts.sort(key=lambda p: (p["date"], p["id"]), reverse=True)
    OUTPUT.mkdir(exist_ok=True)
    for filename in ("icon.svg", ".nojekyll"):
        shutil.copy2(ROOT / filename, OUTPUT / filename)
    # Each content change gets a new URL, so browsers cannot reuse an old loader.
    index = (ROOT / "index.html").read_text(encoding="utf-8")
    for filename in ("app.js", "style.css"):
        source = ROOT / filename
        content = source.read_bytes()
        digest = hashlib.sha256(content).hexdigest()[:12]
        versioned_name = f"{source.stem}.{digest}{source.suffix}"
        (OUTPUT / versioned_name).write_bytes(content)
        index = index.replace(f'"{filename}"', f'"{versioned_name}"')
    (OUTPUT / "index.html").write_text(index, encoding="utf-8")
    shutil.copytree(ROOT / "assets", OUTPUT / "assets", dirs_exist_ok=True)
    (OUTPUT / "posts.json").write_text(
        json.dumps(posts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Prepared {len(posts)} published articles in {OUTPUT}")


if __name__ == "__main__":
    main()
