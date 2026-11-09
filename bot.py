import os, sys, json, time, datetime, urllib.parse, urllib.request, urllib.error
from zoneinfo import ZoneInfo
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent
HISTORY, POST, OUT, DOCS = ROOT/"history.json", ROOT/"post.json", ROOT/"images", ROOT/"docs"
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
SANS = os.getenv("FONT_SANS", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc")
SERIF = os.getenv("FONT_SERIF", "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc")
W, H = 1080, 1350
GRAPH = "https://graph.facebook.com/v21.0"

def today():
    return datetime.datetime.now(ZoneInfo("Asia/Tokyo")).date()

def ask_json(prompt):
    import anthropic
    r = anthropic.Anthropic().messages.create(
        model=MODEL, max_tokens=1500, messages=[{"role": "user", "content": prompt}])
    t = r.content[0].text
    return json.loads(t[t.index("{"): t.rindex("}") + 1])

def load_history():
    return json.loads(HISTORY.read_text("utf-8")) if HISTORY.exists() else []

# ---------- 文章生成 + ファクトチェック ----------
def make_content(d, used):
    p = f"""今日は{d.month}月{d.day}日です。この日に実際に起きた出来事、または誕生・没した人物から1つ選び、
Instagram用の2枚構成コンテンツをJSONだけで出力してください。
ルール:
- 史実として確実に確認できる事実だけを使う。不確かな数字・日付・会話は書かない
- 実在の人物の発言を引用しない(格言は、このエピソードから導いたオリジナル)
- 次の題材は避ける: {used[-60:]}
JSONキー:
title(題材を一言で・20字以内), year(出来事の年), body(エピソード。180〜220字。です・ます調), 
quote(格言。40字以内), book_keyword(関連書籍を探す検索語), hashtags(5個・#付き配列)"""
    return ask_json(p)

def verify(d, c):
    p = f"""{d.month}月{d.day}日のコンテンツの事実確認をしてください。
{json.dumps(c, ensure_ascii=False)}
日付・年・人物・出来事・数字に誤りや断定できない点があれば ok=false。
JSONのみ: {{"ok": true/false, "problems": ["..."]}}"""
    return ask_json(p)

# ---------- 画像 ----------
def wrap(draw, text, font, maxw):
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=font) > maxw:
            lines.append(cur); cur = ch
        else:
            cur += ch
    return lines + [cur]

def fit(draw, text, path, size, maxw, maxh, minsize=30, lh=1.6):
    while True:
        f = ImageFont.truetype(path, size)
        lines = wrap(draw, text, f, maxw)
        if len(lines) * size * lh <= maxh or size <= minsize:
            return f, lines, size
        size -= 2

def bg(top, bottom):
    img = Image.new("RGB", (W, H)); px = img.load()
    for y in range(H):
        t = y / H
        c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        for x in range(W): px[x, y] = c
    return img

def center(draw, y, text, font, fill):
    draw.text(((W - draw.textlength(text, font=font)) / 2, y), text, font=font, fill=fill)

def render(d, c, paths):
    gold, white = (232, 196, 120), (245, 245, 245)
    # 1枚目: エピソード
    img = bg((18, 28, 56), (40, 52, 92)); dr = ImageDraw.Draw(img)
    dr.text((80, 90), f"{d.month}/{d.day}", font=ImageFont.truetype(SANS, 150), fill=gold)
    dr.text((80, 300), f"TODAY'S STORY  {c['year']}", font=ImageFont.truetype(SANS, 34), fill=white)
    ft, tl, ts = fit(dr, c["title"], SANS, 76, W - 160, 200, lh=1.3)
    y = 375
    for ln in tl: dr.text((80, y), ln, font=ft, fill=white); y += int(ts * 1.3)
    dr.line((80, y + 20, 280, y + 20), fill=gold, width=6)
    fb, bl, bs = fit(dr, c["body"], SANS, 42, W - 160, 640)
    y += 70
    for ln in bl: dr.text((80, y), ln, font=fb, fill=white); y += int(bs * 1.6)
    dr.text((W - 330, H - 100), "スワイプで格言へ  →", font=ImageFont.truetype(SANS, 32), fill=gold)
    img.save(paths[0])
    # 2枚目: 格言
    img = bg((60, 36, 30), (22, 18, 24)); dr = ImageDraw.Draw(img)
    center(dr, 150, "TODAY'S QUOTE", ImageFont.truetype(SANS, 40), gold)
    fq, ql, qs = fit(dr, c["quote"], SERIF, 84, W - 220, 700, lh=1.5)
    y = (H - len(ql) * int(qs * 1.5)) // 2 - 20
    for ln in ql: center(dr, y, ln, fq, white); y += int(qs * 1.5)
    center(dr, y + 40, f"― {c['title']} より", ImageFont.truetype(SANS, 34), gold)
    center(dr, H - 200, "保存して、毎日の習慣に", ImageFont.truetype(SANS, 38), white)
    center(dr, H - 140, "関連書籍はプロフィールのリンクから (PR)", ImageFont.truetype(SANS, 30), gold)
    img.save(paths[1])

# ---------- 収益化: リンクまとめページ(プロフィールのリンク先) ----------
def build_links(hist):
    tag = os.getenv("AMAZON_TAG", "")
    items = ""
    for e in reversed(hist[-60:]):
        q = urllib.parse.quote(e["book_keyword"])
        url = f"https://www.amazon.co.jp/s?k={q}" + (f"&tag={tag}" if tag else "")
        items += (f'<li><b>{e["date"]}｜{e["title"]}</b><br>{e["quote"]}<br>'
                  f'<a href="{url}" rel="sponsored nofollow">関連書籍を探す (PR)</a></li>')
    DOCS.mkdir(exist_ok=True)
    (DOCS/"index.html").write_text(f"""<!doctype html><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>今日の物語と格言</title>
<style>body{{font-family:sans-serif;max-width:640px;margin:auto;padding:16px;line-height:1.7}}li{{margin:18px 0}}</style>
<h1>今日の物語と格言</h1><p>※当ページはアフィリエイト広告(Amazonアソシエイト)を含みます。</p><ul>{items}</ul>""", "utf-8")

def generate():
    d, hist = today(), load_history()
    used = [e["title"] for e in hist]
    for _ in range(3):
        c = make_content(d, used)
        v = verify(d, c)
        if v.get("ok"): break
        print("検証NG:", v.get("problems"))
    else:
        sys.exit("ファクトチェックを通らなかったため今日は投稿しません")
    OUT.mkdir(exist_ok=True)
    names = [f"{d.isoformat()}-{i}.png" for i in (1, 2)]
    render(d, c, [OUT/n for n in names])
    repo = os.getenv("GITHUB_REPOSITORY", "USER/REPO")
    caption = (f"{d.month}月{d.day}日｜{c['title']}\n\n{c['body']}\n\n💬 {c['quote']}\n\n"
               f"📚 関連書籍はプロフィールのリンクから (PR)\n保存＆フォローで毎日届きます\n\n{' '.join(c['hashtags'])}")
    POST.write_text(json.dumps({
        "caption": caption,
        "images": [f"https://raw.githubusercontent.com/{repo}/main/images/{n}" for n in names]},
        ensure_ascii=False), "utf-8")
    hist.append({"date": d.isoformat(), "title": c["title"], "quote": c["quote"],
                 "book_keyword": c["book_keyword"]})
    HISTORY.write_text(json.dumps(hist, ensure_ascii=False, indent=1), "utf-8")
    build_links(hist)

# ---------- Instagram投稿 ----------
def api(path, params, post=True):
    params = {**params, "access_token": os.environ["IG_ACCESS_TOKEN"]}
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{GRAPH}/{path}", data=q.encode()) if post \
        else urllib.request.Request(f"{GRAPH}/{path}?{q}")
    try:
        with urllib.request.urlopen(req, timeout=60) as r: return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(e.read().decode())

def ready(cid):
    for _ in range(30):
        if api(cid, {"fields": "status_code"}, post=False).get("status_code") == "FINISHED": return
        time.sleep(5)
    sys.exit("メディア処理がタイムアウトしました")

def post():
    p, uid = json.loads(POST.read_text("utf-8")), os.environ["IG_USER_ID"]
    kids = [api(f"{uid}/media", {"image_url": u, "is_carousel_item": "true"})["id"] for u in p["images"]]
    for k in kids: ready(k)
    parent = api(f"{uid}/media", {"media_type": "CAROUSEL", "children": ",".join(kids),
                                  "caption": p["caption"]})["id"]
    ready(parent)
    print(api(f"{uid}/media_publish", {"creation_id": parent}))

if __name__ == "__main__":
    {"generate": generate, "post": post}[sys.argv[1]]()
