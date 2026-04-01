---
title: "Mercor 遭網路攻擊，牽涉開放原始碼專案 LiteLLM 的供應鏈漏洞"
date: 2026-04-01
categories:
  - AI
  - 科技新聞
tags:
  - LiteLLM
  - Mercor
  - 網路安全
description: "Mercor 遭遇一次嚴重的網路攻擊，攻擊者利用開放原始碼專案 LiteLLM 的供應鏈漏洞，成功竊取大量敏感資料。這次事件對 Mercor 的市場聲譽造成影響，也讓開放原始碼專案的安全性問題再次受到關注。"
image: "/assets/images/mercor-supply-chain-attack-litelm_v1.png"
---

# Mercor 遭網路攻擊，牽涉開放原始碼專案 LiteLLM 的供應鏈漏洞

Mercor 遭遇一次嚴重的網路攻擊，攻擊者利用開放原始碼專案 LiteLLM 的供應鏈漏洞，成功竊取大量敏感資料。這次攻擊對 Mercor 的市場聲譽造成影響，也讓開放原始碼專案的安全性問題再次受到關注。

## 重點整理
- 攻擊者繞過 LiteLLM 的官方流程，將惡意套件上傳至 PyPI，竊取多種敏感憑證。
- 事件可能導致 Mercor 的客戶信任度下降，進而引發客戶流失。
- 建議採用多重身份驗證、代碼掃描和安全依賴管理等措施來加強安全性。
- Mercor 在 2025 年達到高峰，2026 年初完成大規模融資，攻擊可能影響其競爭力。
- 供應鏈攻擊風險增加，企業需加強安全措施以防範。

## 技術細節
LiteLLM 是一個用於在多個大型語言模型提供者間路由請求的開放原始碼庫。攻擊者劫持維護者帳戶，繞過 GitHub 的發布協議，將帶有惡意代碼的版本直接推送到 PyPI。這些受感染版本能竊取環境變量、SSH 密鑰及雲提供商憑證等敏感訊息，顯示開放原始碼專案在身份驗證和代碼審查上的脆弱性。[1][2][3]

## 產業與市場影響
Mercor 作為一家 AI 招募初創公司，這次攻擊可能對其市場聲譽造成長期影響，特別是在處理敏感資料的行業中。客戶信任度下降可能導致流失，進而影響公司未來的發展。事件也可能促使其他公司重新評估其供應鏈安全策略。[4][5]

## 不同聲音
開放原始碼專案的安全性一直是業界關注的焦點，這次事件突顯供應鏈攻擊的風險。批評者指出，開放原始碼專案應加強維護者的身份驗證和代碼審查，以減少安全漏洞的可能性。除了技術措施，社群的積極參與和監督也是確保安全的重要因素。[7][8][9]

## 對台灣的意義
這次事件提醒台灣的科技業者供應鏈安全的重要性。台灣企業應加強開放原始碼軟體的安全管理，並採取適當的防範措施以保護自身和客戶的資料安全，避免類似攻擊的發生。

## 參考來源
1. https://www.aitoday.io/litellm-hit-in-cascading-supply-chain-attack-a-31210
2. https://cycode.com/blog/lite-llm-supply-chain-attack/
3. https://www.trendmicro.com/en_us/research/26/c/inside-litellm-supply-chain-compromise.html
4. https://info.janusassociates.com/blog/10-unseen-impacts-cybersecurity-breaches-can-have-on-your-business
5. https://www.insurancebusinessmag.com/us/news/cyber/how-aifueled-cyberattacks-could-drive-a-new-wave-of-risk-clustering-569933.aspx
6. https://bigthink.com/business/inside-the-meteoric-rise-of-mercor/
7. https://opensource.guide/security-best-practices-for-your-project/
8. https://www.oligo.security/academy/open-source-security-threats-technologies-and-best-practices
9. https://openssf.org/blog/2023/09/06/strengthening-open-source-software-best-practices-for-enhanced-security/