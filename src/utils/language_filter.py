"""
台灣慣用語過濾器
將中國大陸用語替換為台灣慣用語
"""
import re

# 詞彙對照表：{大陸用語: 台灣用語}
TAIWAN_TERMS: dict[str, str] = {
    # 科技術語
    "智能": "智慧",
    "軟件": "軟體",
    "硬件": "硬體",
    "優化": "最佳化",
    "網絡": "網路",
    "視頻": "影片",
    "鏈接": "連結",
    "超鏈接": "超連結",
    "算法": "演算法",
    "數據": "資料",
    "雲計算": "雲端運算",
    "應用程序": "應用程式",
    "應用軟件": "應用軟體",
    "開源": "開放原始碼",
    "服務器": "伺服器",
    "客戶端": "用戶端",
    "接口": "介面",
    "端口": "連接埠",
    "內存": "記憶體",
    "芯片": "晶片",
    "程序員": "工程師",
    "攻城獅": "工程師",

    # 帳號相關
    "登錄": "登入",
    "賬號": "帳號",
    "賬戶": "帳戶",
    "密碼找回": "重設密碼",

    # 日常用語
    "手機": "手機",           # 兩岸相同，保留
    "打車": "叫車",
    "出租車": "計程車",
    "地鐵": "捷運",
    "高鐵": "高鐵",           # 兩岸相同，保留
    "點贊": "按讚",
    "視頻通話": "視訊通話",
    "網購": "網路購物",
    "快遞": "宅配",

    # 商業用語
    "互聯網": "網際網路",
    "電商": "電子商務",
    "創投": "創業投資",
    "估值": "估值",           # 兩岸相同，保留
}

# 不應替換的情境（英文術語中出現的中文字）
SKIP_PATTERNS = [
    r'[A-Za-z]+智能[A-Za-z]+',   # 如 "AI智能X" 品牌名
]


def filter_taiwan_terms(text: str) -> str:
    """
    將文章中的大陸用語替換為台灣慣用語

    Args:
        text: 原始文章內容

    Returns:
        替換後的文章內容
    """
    if not text:
        return text

    result = text
    for cn_term, tw_term in TAIWAN_TERMS.items():
        if cn_term == tw_term:
            continue  # 跳過兩岸相同的詞彙
        result = result.replace(cn_term, tw_term)

    return result


def get_replacement_report(original: str, filtered: str) -> list[dict]:
    """回傳替換報告，列出所有被替換的詞彙"""
    replacements = []
    for cn_term, tw_term in TAIWAN_TERMS.items():
        if cn_term == tw_term:
            continue
        if cn_term in original and tw_term in filtered:
            count = original.count(cn_term)
            replacements.append({
                "original": cn_term,
                "replacement": tw_term,
                "count": count
            })
    return replacements
