# Instagram 毎日自動投稿(日付の物語 + 格言 / 2枚カルーセル)

## セットアップ
1. Instagramを「プロアカウント」にし、Facebookページと連携
2. Meta for Developers でアプリ作成 → 長期アクセストークン取得 → ページトークン(期限なし)を使う
3. このフォルダを**公開**GitHubリポジトリに push(画像をraw URLで配信するため)
4. Settings > Secrets に登録: `ANTHROPIC_API_KEY` / `IG_USER_ID` / `IG_ACCESS_TOKEN` / `AMAZON_TAG`(任意)
5. Settings > Pages で `main` ブランチの `/docs` を公開 → そのURLをプロフィールのリンクに設定
6. Actions タブから `daily-post` を手動実行してテスト(以後は毎朝7:00 JST)

## 安全装置
- 生成後にClaudeが事実確認し、NGなら3回まで作り直し→それでもNGならその日は投稿せず失敗通知
- 格言は実在人物の引用ではなくオリジナル(偽の名言の拡散を防ぐ)
- 過去の題材は history.json で重複回避
