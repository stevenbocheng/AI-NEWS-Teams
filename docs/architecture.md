# 系統架構說明

## LangGraph 狀態機

```
START
  │
  ▼
[researcher]  ← Tavily 搜尋 AI 新聞
  │
  ▼
[writer]      ← GPT-4o 撰寫文章
  │
  ▼
[manager]     ← 品質審核 + 台灣慣用語校正
  │
  ├── 評分 < 7 且修改次數 < 2 → 退回 [writer]
  │
  └── 評分 ≥ 7 或修改次數 ≥ 2
        │
        ▼
    [publisher]  ← Git push 到 GitHub Pages
        │
        ▼
       END
```

## 共享狀態（NewsState）

所有節點透過 `NewsState` TypedDict 傳遞資料：

| 欄位 | 類型 | 說明 |
|------|------|------|
| `raw_news` | `list[dict]` | Researcher 收集的原始新聞 |
| `draft_article` | `str` | Writer 的草稿 |
| `final_article` | `str` | Manager 審核後的最終版 |
| `quality_score` | `float` | 品質評分 0-10 |
| `revision_count` | `int` | 修改次數（避免無限迴圈） |
| `metadata` | `dict` | 標題、標籤、slug 等 |
| `error` | `str` | 錯誤訊息 |

## 關鍵設計決策

### 為什麼選 LangGraph 而非 CrewAI？
- LangGraph 提供更細緻的狀態控制與條件路由
- 更容易 debug（每個節點狀態都可追蹤）
- 與 LangChain 生態完全整合

### 為什麼使用靜態詞彙表 + LLM 雙重過濾？
- 靜態詞彙表：100% 覆蓋已知詞彙，零漏改
- LLM 審核：處理語境複雜的邊緣案例
- 兩層保護確保台灣用語準確率

### GitHub Token 安全性
- 使用 GitHub Repository Secrets 儲存 Token
- Token 只給 `repo` write 權限，最小權限原則
- 絕不在程式碼中 hardcode 任何金鑰
