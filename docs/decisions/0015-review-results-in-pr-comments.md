# 0015. 審查結果改留在 PR 留言

- 狀態：已採用（部分被 [0019](0019-simplify-spec-review-and-ac-derivation.md) 取代）
- 日期：2026-11-20

## 背景

規格審查與實作審查每一輪的結果，原本由主 session 照 `docs/reviews/README.md`「紀錄檔格式」整理成 `docs/reviews/specification/<功能>.md`、`docs/reviews/implementation/<功能>.md`，commit 並 push 到 PR 分支（[0005](0005-specification-review.md)、[0009](0009-docs-delivery-and-glossary.md)）。每一輪都多一次 commit 與完整的 CI；紀錄檔的格式有 60 多行規則，格式本身也會被審查挑出問題。例如 PR #153 只改 3 行文件，審查紀錄就多了 3 個 commit。

一般做法是把審查留在 PR 上：Google eng-practices〈The Standard of Code Review〉把討論的結果記成 CL 上的留言。

## 決定

1. 每一輪審查的結果貼成 PR 上的一則公開留言：reviewer 的報告，加上一節「處理」（欄位見 `docs/reviews/README.md`「處理」）。處理完這一輪的發現才貼，貼出後不修改；修正的 commit 寫在下一輪的留言；最後一輪之後的修正與決定另外貼一則補充留言。
2. 規格審查在 PR 開之前做，PR 開好後依序貼出。
3. 「漏洞」的內容照 CLAUDE.md「漏洞」改寫後才貼；PR 留言列進不能寫漏洞細節的地方。
4. 之後的讀者需要的決定：規格審查時改到驗收條件的，直接改草稿，寫在那一輪留言的「處理」；實作審查時或核准後改到驗收條件的，記在規格的「修改紀錄」；其他的決定寫在那一輪留言的「處理」。
5. 不再新增 `docs/reviews/specification/`、`docs/reviews/implementation/` 的檔案；既有的紀錄檔保留，不改寫。

## 放棄的做法

- **保留紀錄檔，只簡化格式**：每一輪仍要多一次 commit 與 CI，問題的主要來源沒有消失。
- **不公開，報告只留在 `.drafts/`**：開發結束就刪掉，之後的人看不到當時為什麼這樣改。repo 原本就公開 commit 紀錄檔，公開的程度沒有增加。留言刪除才會移除內容；編輯後舊版本仍看得到、通知也已經寄出，所以「漏洞」的改寫要在貼出前完成。
- **把既有紀錄檔搬到 PR 留言**：要逐一轉換，舊 issue 與規格也引用了這些路徑。

## 影響

- 推翻 [0005](0005-specification-review.md)「影響」裡規格審查紀錄的存放位置，以及 [0009](0009-docs-delivery-and-glossary.md) 由主 session commit 審查紀錄的分工；兩份只改狀態行。
- 審查留言只在 GitHub 上：搬離 GitHub 時要另外匯出。
- 規格審查與實作審查的結果，主 session 不再 commit 到 PR 分支；`feature-implementer` 不會再因為審查紀錄檔而碰到歸屬不明的改動。
- `acceptance-reviewer` 用 `gh pr view <PR> --json comments` 讀前幾輪的留言；允許清單加 `gh pr comment`、禁止清單擋下 `--edit-last`，不加 `gh api` 寫入類的指令。
