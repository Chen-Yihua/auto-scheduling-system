# 0012. 簡化等級、審查分流與決定記錄，`/feature` 拆成階段 skill

- 狀態：已採用（審查發現的去處補上「這個 PR 清理」，見 [0013](0013-boy-scout-cleanups.md)）
- 日期：2026-11-13

## 背景

`/feature` 的 `SKILL.md` 有 420 多行，每次啟動整份載入；流程本身也累積了不少規則：

- 四個等級（文字修正、輕量、標準、高風險）和四張決策表（判斷等級、處理發現、發現處理表、審查後的規格修改）。輕量與標準的差別只剩問答、審查次數和幾個專屬例外（「未經審查」標記、升級規則、縮小的重審範圍），而問答的提問原則本來就只問會改變需求、行為或範圍的事。處理發現的兩張表回答的是同一個問題：審查員報了發現，誰來處理。
- 開發者的決定用 Context／Frontier 加 C、Q 編號追蹤，編號只在 scratchpad 有意義，所以要另外維護「不可寫進正式文件」的規則（[0009](0009-docs-delivery-and-glossary.md)），並由三個角色檢查。
- 開發者提出流程太複雜、難以閱讀（2026-11-13）。

參考的做法：Anthropic 對 skill 的建議是 `SKILL.md` 當目錄、細節放在需要時才讀的檔案；superpowers 的 brainstorming 依任務分三條路徑，流程繁簡隨任務調整、核准關卡不變，拿不準時選較重的一條、中途不降級；它的 code review 依嚴重度只分立刻修、繼續前修、以後再說三種去處；mattpocock 的 `grill-with-docs` 把術語與重要決定一確定就寫進長期文件，不另外維護編號清單；superpowers 與 mattpocock 都按工作把流程拆成獨立 skill，由只讓使用者叫出的入口串起來。

## 決定

1. **`/feature` 拆成入口加三個階段 skill**：`feature`（入口，只有使用者能叫出；流程順序、硬規則、判斷等級、重大架構決策、文字修正、回報、取消）、`clarify-requirements`（需求確認）、`write-spec`（規格與規格審查）、`implement-and-review`（核准後的交付、實作審查與漏洞的處理），另有 `feature/references/resume.md`（暫停與接續、暫存產物表、審查豁免）。階段 skill 不設 `disable-model-invocation`，讓入口能載入，用 description 限定只在 `/feature` 流程中使用。agent 與 `/issue` 用「skill 名稱加章節名稱」引用，不用章節編號。術語表的格式移到 `docs/README.md`。
2. **等級改為高風險、一般、文字修正三級**。一般涵蓋原本的輕量與標準；其餘沿用 [0007](0007-process-depth-by-risk.md)：依變更碰到什麼判斷、不確定取較高、只升不降。
3. **審查發現的去處只有四種**：漏洞暫停、交回實作、問開發者、開 issue。核准前規格草稿由主 session 直接修改，只有涉及產品行為、權限、安全性、資料處理或架構的才問開發者。
4. **規格審查最多 2 次**：第 1 次完整，第 2 次針對性審查，只審改過的部分與連帶影響。開發者要求修改驗收條件、假設或設計時再做針對性審查，不計入 2 次；只改措辭不用重審。
5. **決定的記錄**：開發者確認的決定馬上寫進規格草稿、術語表草稿或 ADR 草稿；scratchpad 只留沒有編號、分「已確認」與「待問」的 `<功能>-grill.md`，不 commit，也不被其他文件引用。
6. **一般等級也做需求問答**，深度依提問原則；文字修正仍只確認修改目標與範圍。
7. **補上「修 bug 時」的規格寫法**到 `docs/specs/README.md`：背景寫重現步驟與原因、AC1 對應重現步驟、「測試對應」填「改程式前是否失敗」。

## 放棄的做法

- **保留四級，只簡化表**：輕量的專屬例外仍要維護，複雜度的主要來源沒有消失。
- **把 `<功能>-grill.md` commit 進 repo**：repo 是公開的，內容含還沒問完的題目與被否決的選項，且和規格重複；代價是 scratchpad 遺失時要靠規格恢復（見 [0010](0010-scratchpad-loss-recovery.md)）。
- **把主 session 做成 agent（`claude --agent`）**：需求問答要多輪對話，subagent 做不到；它會取代預設的 system prompt、每次都要用旗標啟動；以 `--agent` 當主 session 時，`skills:` 欄位預載 skill 的行為有已知的回報，未驗證是否已修正。
- **拆成多個獨立入口**：[0009](0009-docs-delivery-and-glossary.md) 放棄了「拆出獨立的 grilling 或 domain-modeling skill」，理由是只有 `/feature` 使用、拆開後兩邊要各自同步。本次的階段 skill 同樣只有 `/feature` 使用，但目的是縮短每次載入的內容，不是新增入口；每條規則只寫在一處、其他地方用名稱引用，同步成本因此有限。0009 的理由對「另外提供獨立入口」仍然成立。

## 影響

- 推翻 [0008](0008-grilling-without-plan-mode.md) 放棄的「所有等級都做問答」中對輕量的判斷：一般等級的小改動也要簡述需求理解，可能多問一兩題。
- 小改動可能比原本的輕量多走一次針對性審查；標準等級的第 2 次規格審查從「再審一整輪」變成只審改過的部分，審查範圍變小。
- [0009](0009-docs-delivery-and-glossary.md) 由 `specification-reviewer`、`acceptance-reviewer`、主 session 檢查 C、Q 編號的規定全部移除；「不引用 scratchpad 的 `<功能>-grill.md`」只靠 skill 說明，沒有 agent 檢查。
- 規格審查紀錄不再有「未經審查的驗收條件」一節；合併前若有舊流程開的 PR 其紀錄含這一節，主 session 交給 `acceptance-reviewer` 時改為指定要補查的驗收條件。
- 需要同步：三個 agent、`/issue` skill、`docs/README.md`、`docs/specs/README.md`、`docs/reviews/README.md`、`docs/issues.md` 與本索引。舊 ADR 只改狀態行，本文保持原樣。
- 新增暫存產物時，照 `feature/references/resume.md` 的暫存產物表補上檔名、產生它的步驟與恢復方式（沿用 0010）。