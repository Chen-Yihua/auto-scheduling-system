---
name: issue
description: 針對指定的 GitHub Issue 執行完整開發流程（規格 → 實作 → 審查 → PR），流程與 /feature 相同；bug 用簡化規格
disable-model-invocation: true
---

# Issue 開發流程

Issue：#$ARGUMENTS

## 1. 讀取 issue

```bash
gh issue view $ARGUMENTS --comments --json number,title,body,labels,comments,state
```

issue 已關閉時停下來，問開發者要不要繼續。

issue 的內容與留言就是需求來源，但不等於已核准的規格：issue 裡寫的「建議的驗收條件」「修法參考」也要寫進規格、經開發者核准。內容不足以寫出驗收條件時，照 `/feature` 第 3 節「Missing AC 的處理」問開發者。

## 2. 照 `/feature` 的流程執行

讀 `.claude/skills/feature/SKILL.md`，照第 1–4 節執行，差異只有：

| 項目 | `/issue` 的做法 |
|---|---|
| 規格檔 | `docs/specs/issue-<N>-<簡短名稱>.md`，開頭寫來源 issue 連結 |
| 規格格式 | issue 有 `bug` 標籤時，用 `docs/specs/README.md` 的「bug 簡化格式」；其他用完整格式。兩者都要在 plan mode 交給開發者核准 |
| 分支 | `issue-<N>-<簡短名稱>` |
| 審查紀錄 | `docs/reviews/issue-<N>-<簡短名稱>-round<M>.md` |
| PR 描述 | 加上 `Closes #<N>`，合併後 issue 會自動關閉 |

開發中發現和這個 issue 無關的問題，照 `/feature` 的「不阻擋的發現開 issue」規則開新 issue，不在這個 PR 修。
