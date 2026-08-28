# V11｜STEP 02D-3｜公開版最後操作細節整理
import re
import zipfile
import streamlit as st
from openai import OpenAI
import base64
from io import BytesIO
from PIL import Image
import random
from pathlib import Path
import json
import hashlib
import urllib.request
import urllib.error

# ------------------------------------------------------------
# V10 使用者資料本／獨立儲存區
# 不放進 app.py 內；只要這些 JSON 檔仍在專案中，更新 app.py 不會清空。
# 先讀取新的 v10_data/，若尚未建立則相容讀取舊版根目錄 JSON。
# ------------------------------------------------------------
import time
V10_DATA_DIR = Path(__file__).with_name("v10_data")
V10_DATA_DIR.mkdir(exist_ok=True)

V10_PRESET_FILE = V10_DATA_DIR / "V10_user_presets.json"
V10_CUSTOM_PHRASE_POOL_FILE = V10_DATA_DIR / "V10_custom_phrase_pool.json"

V10_LEGACY_PRESET_FILE = Path(__file__).with_name("V10_user_presets.json")
V10_LEGACY_PHRASE_POOL_FILE = Path(__file__).with_name("V10_custom_phrase_pool.json")

def _public02a_default_settings():
    return {
        "style_custom": [""] * 10,
        "style_custom_names": [f"使用者自定{i}" for i in range(1, 11)],
        "character_custom": ["", "", ""],
        "character_enabled": [False, False, False],
        "custom_phrases": [],
    }


def _public02a_normalize_settings(data):
    base = _public02a_default_settings()
    if not isinstance(data, dict):
        return base

    for key in ("style_custom", "style_custom_names"):
        value = data.get(key)
        if isinstance(value, list):
            value = [str(x) if x is not None else "" for x in value[:10]]
            value += [""] * (10 - len(value))
            base[key] = value

    value = data.get("character_custom")
    if isinstance(value, list):
        value = [str(x) if x is not None else "" for x in value[:3]]
        value += [""] * (3 - len(value))
        base["character_custom"] = value

    value = data.get("character_enabled")
    if isinstance(value, list):
        value = [bool(x) for x in value[:3]]
        value += [False] * (3 - len(value))
        base["character_enabled"] = value

    value = data.get("custom_phrases")
    if isinstance(value, list):
        base["custom_phrases"] = list(dict.fromkeys(
            str(x).strip() for x in value if str(x).strip()
        ))

    return base


def _public02a_get_settings():
    return {
        "style_custom": [
            st.session_state.get(f"v10_style_custom_{i}", "")
            for i in range(1, 11)
        ],
        "style_custom_names": [
            st.session_state.get(f"v10_style_name_{i}", f"使用者自定{i}")
            for i in range(1, 11)
        ],
        "character_custom": [
            st.session_state.get(f"v10_character_custom_{i}", "")
            for i in range(1, 4)
        ],
        "character_enabled": [
            bool(st.session_state.get(f"v10_character_enabled_{i}", False))
            for i in range(1, 4)
        ],
        "custom_phrases": list(st.session_state.get("public02a_custom_phrases", [])),
    }


def _public02a_apply_settings(data):
    # Streamlit widget keys cannot be modified after those widgets are instantiated.
    # Store the imported data as a pending payload; the next script run applies it
    # before the widgets are created.
    data = _public02a_normalize_settings(data)
    st.session_state["public02a_pending_import"] = data
    return True


def _public02a_init():
    defaults = _public02a_default_settings()

    # Apply an imported profile BEFORE the corresponding Streamlit widgets are instantiated.
    pending = st.session_state.pop("public02a_pending_import", None)
    if pending is not None:
        for i in range(1, 11):
            st.session_state[f"v10_style_custom_{i}"] = pending["style_custom"][i - 1]
            st.session_state[f"v10_style_name_{i}"] = pending["style_custom_names"][i - 1]
        for i in range(1, 4):
            st.session_state[f"v10_character_custom_{i}"] = pending["character_custom"][i - 1]
            st.session_state[f"v10_character_enabled_{i}"] = pending["character_enabled"][i - 1]
        st.session_state["public02a_custom_phrases"] = list(pending["custom_phrases"])

    if not st.session_state.get("public02a_initialized", False):
        for i in range(1, 11):
            st.session_state.setdefault(
                f"v10_style_custom_{i}", defaults["style_custom"][i - 1]
            )
            st.session_state.setdefault(
                f"v10_style_name_{i}", defaults["style_custom_names"][i - 1]
            )
        for i in range(1, 4):
            st.session_state.setdefault(
                f"v10_character_custom_{i}", defaults["character_custom"][i - 1]
            )
            st.session_state.setdefault(
                f"v10_character_enabled_{i}", defaults["character_enabled"][i - 1]
            )
        st.session_state.setdefault("public02a_custom_phrases", [])
        st.session_state["public02a_initialized"] = True



_public02a_init()

# 每個 Streamlit Session 都有自己的語詞池。
# 不再讀寫共用的 v10_data/V10_custom_phrase_pool.json。
V10_CUSTOM_PHRASE_POOL = st.session_state["public02a_custom_phrases"]


def _load_v10_phrase_pool():
    # 公開版：只從目前使用者 Session 取得。
    return list(st.session_state.get("public02a_custom_phrases", []))


def _save_v10_phrase_pool(values):
    # 公開版：只更新目前使用者 Session，不寫入共用檔案。
    values = list(dict.fromkeys(
        str(x).strip() for x in values if str(x).strip()
    ))
    st.session_state["public02a_custom_phrases"] = values
    return True


def _load_v10_presets():
    # 公開版：不讀取共用 v10_data，避免不同使用者互相看到資料。
    return {
        "style_custom": [
            st.session_state.get(f"v10_style_custom_{i}", "")
            for i in range(1, 11)
        ],
        "style_custom_names": [
            st.session_state.get(f"v10_style_name_{i}", f"使用者自定{i}")
            for i in range(1, 11)
        ],
        "character_custom": [
            st.session_state.get(f"v10_character_custom_{i}", "")
            for i in range(1, 4)
        ],
        "character_enabled": [
            bool(st.session_state.get(f"v10_character_enabled_{i}", False))
            for i in range(1, 4)
        ],
    }


def _save_v10_presets():
    # 公開版：widget 本身已經把目前輸入值保存在 Session State。
    # 這裡只讀取並驗證，不再重新寫入 widget 的 Session State key。
    # 避免 Streamlit 在 widget 建立後禁止修改同一 key 的 StreamlitAPIException。
    try:
        _snapshot = {
            "style_custom": [
                str(st.session_state.get(f"v10_style_custom_{i}", ""))
                for i in range(1, 11)
            ],
            "style_custom_names": [
                str(st.session_state.get(f"v10_style_name_{i}", f"使用者自定{i}"))
                for i in range(1, 11)
            ],
            "character_custom": [
                str(st.session_state.get(f"v10_character_custom_{i}", ""))
                for i in range(1, 4)
            ],
            "character_enabled": [
                bool(st.session_state.get(f"v10_character_enabled_{i}", False))
                for i in range(1, 4)
            ],
        }
        st.session_state["public02a_last_preset_snapshot"] = _snapshot
        return True
    except Exception:
        return False


# 舊版 v10_data/ 仍保留在專案中，作為備份資料，不由公開版讀寫。

import streamlit.components.v1 as components

def _v11_clear_generation_state() -> None:
    """Clear only transient generation UI/session flags after a terminal outcome."""
    for _key in (
        "v11_generation_pending",
        "v11_generation_in_progress",
    ):
        st.session_state.pop(_key, None)



def _v11_user_error_message(exc: Exception) -> str:
    """Return a simple Chinese message for end users; never expose traceback."""
    msg = str(exc or "").lower()

    if isinstance(exc, TimeoutError) or "timeout" in msg or "timed out" in msg:
        return "⏱️ 生成逾時，請重新操作。"

    if "api key" in msg or "authentication" in msg or "unauthorized" in msg or "401" in msg:
        return "🔑 API Key 無法使用，請確認後重新操作。"

    if "429" in msg or "rate limit" in msg or "quota" in msg:
        return "⚠️ AI 服務目前較忙，請稍後再試。"

    if "no api key" in msg or "api key" in msg:
        return "🔑 請先確認 API Key，再重新操作。"

    if "b64_json" in msg or "沒有取得有效圖片" in msg or "圖片資料不完整" in msg:
        return "🖼️ 這次沒有取得有效圖片，請重新操作。"

    if "image" in msg or "png" in msg or "pil" in msg or "base64" in msg:
        return "🖼️ 圖片處理失敗，請重新操作。"

    return "🔴 圖片生成失敗，請稍後重新操作。"


# ============================================================
# V10 STEP 10C
# 原生 HTML Canvas 滑鼠裁切版
#
# 核心：
# - 不使用 streamlit-drawable-canvas
# - 8 個裁切框同時顯示
# - 滑鼠拖曳框中央：移動
# - 拖曳四角：縮放
# - 拖曳四邊：單方向縮放
# - 顯示座標與原圖座標分離
# - 固定預覽上限，不跟 Streamlit 容器無限放大
# - Chrome 80/100/125/150% 仍以原始圖片座標計算
# - 01～08 不會送給 AI 當作圖片編號
# ============================================================

st.set_page_config(
    page_title="LINE 貼圖創作工作室｜V12",
    page_icon="🎨",
    layout="wide",
)

# ============================================================
# V10 STEP 20｜介面重新排版
# - 大標題置中、放大
# - 每個主要區域以彩虹色分隔
# - 一般控制項限制寬度，避免滿版橫跨
# - 主要內容維持中央操作區
# ============================================================
# ============================================================
# V11｜STEP 02C-1｜FIX4
# 主題顏色改由 .streamlit/config.toml 的 Streamlit 原生 Light/Dark theme 控制。
# Python 這裡不再強制覆蓋整個 App 的背景與文字顏色。


st.markdown("""
<style>
:root{
  --v10-max: 1180px;
  --v10-control: 820px;
}
.block-container{
  max-width:1180px !important;
  padding-left:2rem !important;
  padding-right:2rem !important;
}



/* V11｜02D-3｜公開版最後操作細節整理 */
.v11-section-tip{
  width:min(900px,100%);
  margin:.35rem auto .85rem;
  padding:.6rem .85rem;
  border-radius:12px;
  border:1px solid rgba(120,120,120,.14);
  background:color-mix(in srgb,#64748b 7%, transparent);
  font-size:.96rem;
  line-height:1.55;
}
.v11-success-next{
  width:min(900px,100%);
  margin:.8rem auto 1rem;
  padding:.8rem 1rem;
  border-radius:14px;
  border:1px solid rgba(22,160,133,.25);
  background:color-mix(in srgb,#16a085 9%, transparent);
  text-align:center;
  font-weight:800;
}
/* V11｜02D-2｜生成後流程導引 */
.v11-postgen-guide{
  width:min(1080px,100%);
  margin:1rem auto 1.25rem;
  padding:1rem 1.1rem;
  border-radius:18px;
  border:1px solid rgba(120,120,120,.18);
  background:color-mix(in srgb,#16a085 8%, transparent);
}
.v11-postgen-title{
  text-align:center;
  font-size:clamp(1.15rem,2.2vw,1.55rem);
  font-weight:900;
  margin:.05rem 0 .8rem;
}
.v11-postgen-steps{
  display:grid;
  grid-template-columns:repeat(3,minmax(0,1fr));
  gap:.7rem;
}
.v11-postgen-step{
  padding:.75rem .85rem;
  border-radius:14px;
  border:1px solid rgba(120,120,120,.12);
  background:color-mix(in srgb,#ffffff 58%, transparent);
}
.v11-postgen-step strong{
  display:block;
  margin-bottom:.2rem;
  font-size:1.02rem;
}
.v11-postgen-step span{
  font-size:.96rem;
  line-height:1.5;
  opacity:.9;
}
@media (max-width:720px){
  .v11-postgen-steps{grid-template-columns:1fr;}
}
/* V11｜02D-1｜首次使用導引 */
.v11-onboarding{
  width:min(1080px,100%);
  margin:0 auto 1.2rem;
  padding:1rem 1.15rem 1.1rem;
  border-radius:18px;
  border:1px solid rgba(120,120,120,.18);
  background:linear-gradient(135deg,
    color-mix(in srgb,#7c5cff 10%, transparent),
    color-mix(in srgb,#4bb3fd 8%, transparent),
    color-mix(in srgb,#31c48d 7%, transparent));
}
.v11-onboarding-title{
  text-align:center;
  font-size:clamp(1.2rem,2.3vw,1.7rem);
  font-weight:900;
  margin:.1rem 0 .8rem;
}
.v11-onboarding-grid{
  display:grid;
  grid-template-columns:repeat(3,minmax(0,1fr));
  gap:.75rem;
}
.v11-onboarding-card{
  padding:.8rem .9rem;
  border-radius:14px;
  background:color-mix(in srgb,#ffffff 62%, transparent);
  border:1px solid rgba(120,120,120,.12);
}
.v11-onboarding-step{
  font-size:1.05rem;
  font-weight:900;
  margin-bottom:.25rem;
}
.v11-onboarding-text{
  font-size:.98rem;
  line-height:1.55;
  opacity:.9;
}
@media (max-width:720px){
  .v11-onboarding-grid{grid-template-columns:1fr;}
}
.v10-main-title{
  text-align:center;
  font-size:clamp(2rem,4vw,3.15rem);
  font-weight:900;
  letter-spacing:.04em;
  margin:1.0rem auto 1.8rem;
}
.v10-section{
  position:relative;
  margin:2.8rem 0 1.4rem;
  padding:1.15rem 1rem 1rem;
  border-top:5px solid var(--accent);
  border-bottom:2px solid color-mix(in srgb,var(--accent) 45%, transparent);
  background:linear-gradient(180deg,color-mix(in srgb,var(--accent) 9%, transparent),transparent);
  border-radius:12px;
  text-align:center;
}
.v10-section::after{
  content:"";
  display:block;
  width:150px;
  height:5px;
  border-radius:99px;
  background:var(--accent);
  margin:.8rem auto 0;
}
.v10-section-title{
  font-size:clamp(1.65rem,3vw,2.35rem);
  line-height:1.2;
  font-weight:900;
  letter-spacing:.03em;
}
.v10-transparent-box{
  width:min(760px,100%);
  margin:0 auto 1rem;
  padding:.45rem .75rem;
  text-align:center;
}
/* V11｜02C-3D｜透明背景選項專用穩定 CSS scope */
.st-key-transparent_png_option{
  width:min(900px,100%);
  margin:.35rem auto 1.25rem;
  padding:.65rem 1rem;
  text-align:center;
}

.st-key-transparent_png_option [data-testid="stCheckbox"]{
  width:100% !important;
}

.st-key-transparent_png_option [data-testid="stCheckbox"] label{
  display:flex !important;
  align-items:center !important;
  justify-content:center !important;
  gap:1rem !important;
  width:100% !important;
  cursor:pointer !important;
}

.st-key-transparent_png_option [data-testid="stCheckbox"] label p{
  margin:0 !important;
  font-size:2rem !important;
  line-height:1.2 !important;
  font-weight:900 !important;
}

.st-key-transparent_png_option [data-testid="stCheckbox"] label span{
  font-size:2rem !important;
  font-weight:900 !important;
}

.st-key-transparent_png_option [data-testid="stCheckbox"] [role="checkbox"]{
  min-width:2.1rem !important;
  width:2.1rem !important;
  min-height:2.1rem !important;
  height:2.1rem !important;
  transform:scale(1.15);
  transform-origin:center;
}

.st-key-transparent_png_option [data-testid="stCheckbox"] input{
  width:2rem !important;
  height:2rem !important;
  cursor:pointer !important;
}

.v11-transparent-title{
  width:min(900px,100%);
  margin:1.25rem auto .55rem;
  padding:.7rem 1rem;
  border-left:8px solid #16a085;
  border-radius:10px;
  background:color-mix(in srgb,#16a085 10%, transparent);
  color:var(--text-color, inherit);
  font-size:2rem !important;
  line-height:1.2 !important;
  font-weight:900 !important;
  text-align:left;
}
.v10-transparent-box div[data-testid="stCheckbox"]{
  width:100% !important;
  text-align:center !important;
}
.v10-transparent-box label{
  font-size:2rem !important;
  font-weight:900 !important;
  line-height:1.25 !important;
  cursor:pointer !important;
}
.v10-transparent-box label p,
.v10-transparent-box label span{
  font-size:2rem !important;
  font-weight:900 !important;
}
.v10-transparent-box div[data-testid="stCheckbox"] input{
  width:2.25rem !important;
  height:2.25rem !important;
  transform:scale(1.35);
  transform-origin:center;
  cursor:pointer !important;
}
div[data-testid="stCheckbox"] label{
  font-size:1.12rem !important;
  font-weight:700 !important;
}
.v10-subsection{
  width:min(900px,100%);
  margin:1.25rem auto .75rem;
  padding:.65rem 1rem;
  border-left:6px solid var(--accent);
  border-radius:8px;
  background:color-mix(in srgb,var(--accent) 10%, transparent);
  font-size:1.28rem;
  font-weight:800;
  text-align:left;
}
.v10-note{
  width:min(900px,100%);
  margin:.5rem auto 1rem;
  text-align:center;
  opacity:.9;
}
.v10-control{
  width:min(var(--v10-control),100%);
  margin-left:auto !important;
  margin-right:auto !important;
}
.v10-control-wide{
  width:min(1050px,100%);
  margin-left:auto !important;
  margin-right:auto !important;
}
.v10-centered-image{
  display:flex;
  justify-content:center;
}
div[data-testid="stFileUploader"],
div[data-testid="stSelectbox"],
div[data-testid="stMultiSelect"],
div[data-testid="stTextInput"],
div[data-testid="stTextArea"],
div[data-testid="stNumberInput"]{
  width:min(var(--v10-control),100%) !important;
  margin-left:auto !important;
  margin-right:auto !important;
}
div[data-testid="stButton"]{
  width:min(520px,100%) !important;
  margin-left:auto !important;
  margin-right:auto !important;
}
.v10-small-button div[data-testid="stButton"]{
  width:min(360px,100%) !important;
  margin-left:auto !important;
  margin-right:auto !important;
}
div[data-testid="stCheckbox"],
div[data-testid="stRadio"]{
  width:min(var(--v10-control),100%) !important;
  margin-left:auto !important;
  margin-right:auto !important;
}
div[data-testid="stExpander"]{
  width:min(1000px,100%) !important;
  margin-left:auto !important;
  margin-right:auto !important;
}
@media (max-width:800px){
  .block-container{
    padding-left:.75rem !important;
    padding-right:.75rem !important;
  }
  .v10-section{margin-top:2rem;}
  .v10-section-title{font-size:1.55rem;}
}
</style>
""", unsafe_allow_html=True)

def v10_section(title, accent="#7c4dff"):
    st.markdown(
        f'<div class="v10-section" style="--accent:{accent}">'
        f'<div class="v10-section-title">{title}</div></div>',
        unsafe_allow_html=True,
    )

def v10_subsection(title, accent="#4f8cff"):
    st.markdown(
        f'<div class="v10-subsection" style="--accent:{accent}">{title}</div>',
        unsafe_allow_html=True,
    )

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# ============================================================
# PUBLIC STEP 02B-2D｜Supabase 全站每日 AI 額度
# 目前階段：只讀取並顯示全站共同使用量。
# 不在這一步扣額度，也不改動原本 OpenAI 生成流程。
#
# Secrets（Streamlit Cloud）：
# SUPABASE_URL
# SUPABASE_SERVICE_ROLE_KEY
#
# service_role 只存在伺服器端 st.secrets，不會顯示給訪客。
# ============================================================
def _supabase_rpc(function_name):
    """伺服器端呼叫 Supabase RPC。只使用 Streamlit Secrets。"""
    supabase_url = str(st.secrets["SUPABASE_URL"]).rstrip("/")
    service_role_key = str(st.secrets["SUPABASE_SERVICE_ROLE_KEY"])
    endpoint = f"{supabase_url}/rest/v1/rpc/{function_name}"
    req = urllib.request.Request(
        endpoint,
        data=b"{}",
        method="POST",
        headers={
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if isinstance(payload, list):
        return payload[0] if payload else {}
    if isinstance(payload, dict):
        return payload
    return {}


def _get_daily_ai_quota():
    """從 Supabase RPC 讀取全站今日額度。失敗時回傳 None。"""
    try:
        row = _supabase_rpc("get_daily_ai_quota")
        used = int(row.get("used_count", 0))
        remaining = int(row.get("remaining", 10))
        limit = int(row.get("quota_limit", 10))

        limit = max(1, limit)
        used = max(0, min(used, limit))
        remaining = max(0, min(remaining, limit))

        return {
            "used_count": used,
            "remaining": remaining,
            "quota_limit": limit,
        }

    except Exception as exc:
        # 公開版不要把 Supabase endpoint、secret 或完整錯誤內容顯示給訪客。
        st.session_state["public_quota_error"] = type(exc).__name__
        return None


def _consume_daily_ai_quota():
    """
    真正取得 1 次全站 AI 額度。
    成功回傳 quota dict；沒有額度或 RPC 失敗則回傳 None。
    """
    try:
        row = _supabase_rpc("consume_daily_ai_quota")
        used = int(row.get("used_count", 0))
        remaining = int(row.get("remaining", 0))
        limit = int(row.get("quota_limit", 10))

        limit = max(1, limit)
        used = max(0, min(used, limit))
        remaining = max(0, min(remaining, limit))

        # consume function 若沒有取得額度，通常會回傳 remaining=0。
        # 這裡不自行修改資料庫，避免前端繞過 RPC 規則。
        granted = bool(row.get("granted", False))

        return {
            "granted": granted,
            "used_count": used,
            "remaining": remaining,
            "quota_limit": limit,
        }

    except Exception as exc:
        st.session_state["public_quota_error"] = type(exc).__name__
        return None


def _refund_daily_ai_quota():
    """OpenAI 生成失敗時，退回本次已取得的 1 次額度。"""
    try:
        row = _supabase_rpc("refund_daily_ai_quota")
        used = int(row.get("used_count", 0))
        remaining = int(row.get("remaining", 0))
        limit = int(row.get("quota_limit", 10))

        limit = max(1, limit)
        used = max(0, min(used, limit))
        remaining = max(0, min(remaining, limit))

        return {
            "used_count": used,
            "remaining": remaining,
            "quota_limit": limit,
        }
    except Exception as exc:
        st.session_state["public_quota_error"] = type(exc).__name__
        return None


def _show_daily_ai_quota():
    """顯示所有訪客共用的全站每日 AI 使用進度。"""
    quota = _get_daily_ai_quota()

    st.markdown(
        """
        <div style="
            max-width:820px;
            margin:10px auto 14px;
            padding:16px 20px;
            border:1px solid #3b4658;
            border-radius:14px;
            background:linear-gradient(135deg,#151b26,#202938);
            text-align:center;
        ">
            <div style="font-size:22px;font-weight:800;color:#ffffff;">
                🤖 今日 AI 使用量
            </div>
            <div style="font-size:14px;color:#b9c4d4;margin-top:4px;">
                全站共用每日額度
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if quota is None:
        st.warning(
            "⚠️ 目前無法讀取全站 AI 使用量。"
            "請確認 Supabase Secrets 已設定正確。"
        )
        return None

    used = quota["used_count"]
    remaining = quota["remaining"]
    limit = quota["quota_limit"]
    ratio = used / limit if limit else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("今日已使用", f"{used} 次")
    c2.metric("今日剩餘", f"{remaining} 次")
    c3.metric("每日上限", f"{limit} 次")

    st.progress(ratio)

    if remaining > 0:
        st.success(f"🟢 全站今日剩餘 **{remaining} 次** AI 生成額度")
    else:
        st.error("🔴 全站今日 AI 額度已用完，請明天再試。")

    return quota


COMMON_PHRASES = [
    "早安","晚安","午安","嗨","哈囉","加油","辛苦了","謝謝",
    "感謝","不客氣","沒問題","OK","收到","了解","好喔","好的",
    "太好了","讚","超讚","棒棒的","恭喜","祝福你","一起加油",
    "慢慢來","等等我","馬上來","我來了","出發","回來了","先這樣",
    "掰掰","再見","哈哈哈","笑死","真的嗎","真的假的","好開心",
    "好幸福","太可愛了","我愛你","想你","抱抱","親親","不要啦",
    "不要鬧","傻眼","無言","生氣","氣死我了","好累","累了",
    "忙死了","休息一下","我不行了","好餓","吃飯了嗎","等等再說",
    "拜託","求你了","可以嗎","好嗎","當然可以","當然好","隨便你",
    "沒事","沒關係","別擔心","放心","我懂","我知道","我明白",
    "太扯了","救命","完蛋了","糟糕","慘了","好可怕","不要怕","冷靜"
]

# ============================================================
# V8.6.4 資料模組移植：語詞／風格／貼圖字型／125 帶圖字型
# 資料內容沿用 V8，不改名稱與排列順序。
# ============================================================
V8_STYLES = ['Q版黏土3D', 'Q版收藏公仔', '3D收藏公仔', '軟陶公仔', '木雕玩具', '微縮場景', '療癒系Cute風', '日系可愛插畫', '韓系簡約插畫', '手繪水彩', '色鉛筆手繪', '粉彩蠟筆', '扁平插畫', '貼紙插畫風', '復古漫畫', '美式漫畫', '日系漫畫', '像素藝術', '毛氈玩偶', '羊毛氈手作', '紙雕立體', '紙黏土手作', '奶油霧面3D', '玻璃質感3D', '玩具盒收藏風', '盲盒公仔風', '電影級3D', '黏土定格動畫風', '低多邊形Low Poly', 'Dreamy夢幻療癒', '童話繪本風', '森林療癒風', '極簡精品風', '復古80年代', '復古90年代', '街頭潮流插畫', 'Emoji表情貼風', 'LINE訊息貼圖風', '透明背景貼圖風', '⭐ 自訂1', '⭐ 自訂2', '⭐ 自訂3', '⭐ 自訂4', '⭐ 自訂5']
V8_DEFAULT_CONTENT = ['早安', '晚安', '謝謝', '收到', 'OK', '加油', '辛苦了', '太棒了']
V8_RANDOM_POOLS = {'日常對話': ['你好', '哈囉', 'Hello', 'Hi', '安安', '嗨嗨', '請多多指教', '是我', '我來了', '來打聲招呼', '很高興認識你', '好久不見', '我來了', '想我了嗎', '在忙嗎？', '掰掰', 'Bye', '再聊', '再會', '再見', '晚點聊'], '生活應用': ['OK', '好的', '沒問題', '嗯嗯', '可以呀', '我可以', '收到', '了解', '知道了', '加油', '你可以的', '我相信你', '別緊張', '給你加加油', '生日快樂'], '時間問候': ['早安', '早呀', '早上好', '咕摸寧', '午安', '下午好', '晚安', '咕奈', '好好睡', '一覺好眠'], '溫暖關愛': ['愛你', '給你愛心', '給你一個小心心', '抱', '別哭', '抱一個', '給你大大的擁抱', '別擔心', '別想太多'], '歡樂笑聲': ['哈哈哈', '好好笑', '也太好笑', '笑死', '笑爛', '廢到笑', '呵呵', '嘻嘻', '噗', '開心', '耶耶耶', '耶伊', 'YEAH', '呀比', '好開心', '撒花', '讚', '棒', '100分', '優秀', '厲害', '好可愛'], '表現難過': ['哭哭', '嗚嗚', '傷心', '桑心', '難過', '難受', '崩潰', '今天心情不美麗'], '祝賀對方': ['恭喜', '可喜可賀', '以你為榮', '替你開心', '給你第一名', '你真的hen棒', '這感覺太美妙'], '帶點懷疑': ['真的嗎', '真的假的', '真假', '是喔？', '屁啦', '你騙人', '我不相信'], '尷尬反應': ['尷尬了', '好尷尬', '誤會大了', '希望沒事'], '驚訝震驚': ['哇哇哇', '哇嗚', '哇塞', '哇靠', '到底', '這…', '驚', 'OMG', '天啊', '驚訝', '好Shock', '我的天'], '無言傻眼': ['瞎', '扯', '蛤', '呃', '呿', '…', '無言', '傻眼', '暈倒', '我暈'], '誇張荒謬': ['誇張', '離譜', '有事嗎', '很有事', '很有病', '太扯了', '沒救了', '忘了吃藥', '比扯鈴還扯'], '調皮搗蛋': ['幹嘛', '幹什麼', '想幹嘛', '你怪怪的'], '衷心感謝': ['謝謝', '感謝你', '大感激', '甘溫', '乾蝦', '辛苦了', '有你真好', '好貼心'], '誠摯道歉': ['抱歉', '對不起', 'Sorry', '拍謝', '不好意思'], '不必客氣': ['不客氣', '小事啦', '一塊小蛋糕', '沒關係', '沒事的', '應該的', '別介意', 'No mind', '別放心上'], '時間行程': ['等我一下', '等等我', '等你', '我等你', '晚點見', '明天見', 'See you', '路上小心', '一路順風'], '交通出門': ['在路上了', '我快到了', 'on the way', '我出門了', '出發', '剛出發', '已離開', '走囉'], '地點詢問': ['約哪兒', '在哪', '到哪裡了'], '忙碌相關': ['好忙', '忙翻', '忙到爆', '有話快說!'], '用餐相關': ['一起吃飯吧', '吃飯', '開飯', '開動', '開吃', '好好吃', '好美味', '吃飽沒'], '休息睡覺': ['好睏', '好想睡', '我先睡了', '想睡覺', '小睡片刻', '補眠中', '補眠去'], '天氣感受': ['好熱', '好冷', '快中暑了', '瑟瑟發抖', '秋風氣爽'], '注意提醒': ['注意', '緊盯', '嗶嗶嗶', '提高警覺', '給我小心點'], '意見表達': ['YES', '沒錯', '就是這樣', '同意', 'NO', '不行啦', '不可以', '我拒絕', '放過我', '母湯'], '參與話題': ['加1', '+1', '加我一個', '一起一起', '我也要'], '表態行動': ['我會加油的', '交給我吧', '使命必達', '為你效勞'], '約定承諾': ['打勾勾', '一言為定', '成交', '說好囉', '就這麼說定', '+1+1'], '思考回應': ['這樣啊', '我想想', '晚點回', '晚點再說', '我考慮一下'], '請求拜託': ['拜託拜託', '麻煩你了', '求求你', '考慮考慮麻!'], '正向情緒': ['打起精神來', '一切都會越來越好', '一切都是最好的安排', '好感動', '好感人', '活在當下', '珍惜當下', '期待', '充滿希望', '羨慕', '好幸福', '小確幸', '真幸運'], '負面情緒': ['好累', '心累', '累歪', '已攤', '心好累', '好無奈', '別逼我', '讓我靜靜', '懷疑人生', '為什麼要逼我', '好衰', '衰衰的', '有夠衰', '好倒霉哦', '惡人退散', '也太衰了吧'], '緊張憤怒': ['生氣', '氣死', '森77', '超級不爽', '好可怕', '嚇到我', '嚇我一跳'], '逃避現實': ['裝死', '逃避', '不想面對', '不想努力', '來啊', '我就爛', '誰怕誰', '來互相傷害啊'], '職場學習': ['開會中', '忙碌中', '加班中', '信回不完', '事情做不完', '耍廢中', '休假中', '別吵我', '今天放假', '要正向', '馬上處理', '考試加油', '一起努力', '想下班', '想放假', '不想上班', '週末快樂', '放假愉快', '下班啦', '可以回家了', '現在是星期五晚上', '來杯咖啡', '打起精神吧'], '幽默趣味': ['穴穴尼', 'ㄎㄎ', 'ㄏㄏ', '喵', '哼', '啾咪', '就醬吧', '美麥', '好開勳', '轉圈圈', '棒棒der', '開玩笑的啦', '認真就輸了', '登愣', '蝦毀', '突破盲點', '我的老天鵝', '聽你在唬爛', '要不要聽聽你在說什麼', '腦波弱', '當仙女好累', '靜靜的看著你', '沒看過仙女嗎？', '給你尷尬又不失禮的微笑', '不要問 很可怕'], '戀愛表達': ['我愛你', '最愛你了', '喜歡你', '妳是最可愛的', '有妳好幸福', '啾', '親親', '抱抱', '吻你', '親一個', '好想抱抱你', '想你', '想念你', '好想你', '期待重逢', '期待見面', '期待約會', '陪我', '來接我', '一起吃飯吧']}
V8_TEXT_EFFECT_CATALOG = {1: '胖胖貼紙字', 2: '棉花糖圓字', 3: '果凍QQ字', 4: '奶油餅乾字', 5: '糖霜甜點字', 6: '蠟筆童趣字', 7: '軟萌手寫字', 8: '日系手帳圓字', 9: '韓系軟萌字', 10: '漫畫衝擊字', 11: '對話泡泡字', 12: '貼紙白邊字', 13: '泡棉玩具字', 14: '橡膠軟墊字', 15: '樹脂亮面字', 16: '壓克力透明字', 17: '珐瑯徽章字', 18: '刺繡布章字', 19: '羊毛氈字', 20: '皮革壓印字', 21: '紙雕層疊字', 22: '摺紙立體字', 23: '陶瓷裂釉字', 24: '玉石浮雕字', 25: '大理石雕字', 26: '銀鋼浮雕字', 27: '黃金立體字', 28: '青銅復古字', 29: '冰晶透明字', 30: '水晶玻璃字', 31: '霓虹發光字', 32: '香港霓虹字', 33: '燈泡招牌字', 34: '木雕質感字', 35: '石刻厚重字', 36: '毛筆書法字', 37: '印章篆刻字', 38: '剪紙藝術字', 39: '復古海報字', 40: '打字機復古字', 41: '塗鴉潮流字', 42: '街頭塗鴉字', 43: '漫畫爆炸字', 44: '熱血漫畫字', 45: '手繪塗鴉字', 46: '極簡手寫字', 47: '浪漫手寫字', 48: '粉筆黑板字', 49: '神聖光輝字', 50: '暗黑哥德字', 51: '黏土手作字', 52: '拼布縫線字', 53: '珍珠貝殼字', 54: '羽毛飄逸字', 55: '竹編工藝字', 56: '稻草編織字', 57: '苔蘚森林字', 58: '藤蔓花園字', 59: '花瓣拼貼字', 60: '水彩暈染字', 61: '墨彩渲染字', 62: '彩鉛塗層字', 63: '蠟染布紋字', 64: '馬賽克磚字', 65: '植絨絨面字', 66: '蒸汽齒輪字', 67: '像素電玩字', 68: '八位元方塊字', 69: '故障數位字', 70: '全息雷射字', 71: '雲朵蓬鬆字', 72: '海鹽砂粒字', 73: '珊瑚海洋字', 74: '星砂夢幻字', 75: '宇宙星雲字', 76: '巧克力糖漿字', 77: '爆米花零食字', 78: '棉麻編織字', 79: '牛仔布貼字', 80: '蕾絲花邊字', 81: '鈕扣拼貼字', 82: '鉤針編織字', 83: '彩窗教堂字', 84: '鐵鐵鉚釘字', 85: '鐵鏽工業字', 86: '電路晶片字', 87: '液晶螢幕字', 88: '雷達掃描字', 89: '橡皮印刷字', 90: '油畫筆觸字', 91: '膠卷電影字', 92: '報紙剪貼字', 93: '牛皮紙包裝字', 94: '露珠葉脈字', 95: '螢火森林字', 96: '星座占卜字', 97: '草本藥鋪字', 98: '珍奶Q彈字', 99: '壽司食玩字', 100: '甜甜圈糖針字', 101: '水墨毛筆字', 102: '行書連筆字', 103: '潑墨寫意字', 104: '篆刻印章字', 105: '鋼筆流線字', 106: '打字機復古字', 107: '粉筆手繪字', 108: '彩虹手繪字', 109: '塗鴉手繪字', 110: '立體貼紙字', 111: '氣球立體字', 112: '布料拼貼字', 113: '草地綠植字', 114: '沙灘沙粒字', 115: '雲朵棉花字', 116: '寒霜冰裂字', 117: '熔岩裂石字', 118: '鏽蝕金屬字', 119: '乾裂泥土字', 120: '鑽石切割字', 121: '雷射幻彩字', 122: '液態金屬字', 123: '霓虹燈管字', 124: '復古燈泡字', 125: '像素點陣字'}
V8_TEXT_STYLE_OPTIONS = ["高級立體金字","彩色漫畫爆炸","柔和立體氣泡","霓虹發光字","手寫貼紙字","清爽白底字"]
V8_TEXT_EFFECT_VALUES = [f"{i:03d}｜{V8_TEXT_EFFECT_CATALOG[i]}" for i in range(1,126)]
V8_FONT_PREVIEW_DIR = Path(__file__).with_name("font_reference") / "previews"

POPULAR_STYLES = [
    "↓ 請選擇風格","Q版黏土3D","Q版收藏公仔","3D收藏公仔",
    "療癒系Cute Wstyle","大頭小身","LINE貼圖風","柔和光影",
    "手作玩偶風","可愛漫畫風","立體卡通風",
]

CHARACTER_OPTIONS = [
    "五官比例保留","服飾配件保留","人物辨識度保留",
    "Q版收藏公仔","療癒系 Cute Wstyle","大頭小身",
    "LINE貼圖風","柔和光影",
]


# ============================================================
# V12｜STEP 01A①
# Project 基礎資料骨架
#
# 本階段只建立「目前作品」的 Session 架構與 UI 導航。
# 尚未寫入 Supabase / 伺服器 / 永久資料庫。
# API Key 絕不納入 Project。
# ============================================================
from datetime import datetime
from uuid import uuid4

def _v12_now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")

def _v12_new_project_metadata():
    now = _v12_now_iso()
    return {
        "project_id": str(uuid4()),
        "project_name": "",
        "style_name": "",
        "font_name": "",
        "text_style": "",
        "created_at": now,
        "updated_at": now,
        # 後續 STEP 01A②～⑤ 逐步填入；本階段不永久保存。
        "generation_method": "",
        "transparent_background": False,
        "sticker_texts": [""] * 8,
        "source_image": None,
        "generated_grid": None,
        "stickers": [],
        "main_image": None,
        "tab_image": None,
    }

st.session_state.setdefault("v12_current_project", _v12_new_project_metadata())
st.session_state.setdefault("v12_projects_local_index", [])

def _v12_current_project():
    project = st.session_state.get("v12_current_project")
    if not isinstance(project, dict):
        project = _v12_new_project_metadata()
        st.session_state["v12_current_project"] = project
    return project

def _v12_project_snapshot():
    """取得目前作品的可保存 metadata 快照；絕不包含 API Key。"""
    project = dict(_v12_current_project())
    project["updated_at"] = _v12_now_iso()
    project["sticker_texts"] = [
        str(st.session_state.get(f"sticker_text_{i}", ""))
        for i in range(8)
    ]
    project["transparent_background"] = bool(
        st.session_state.get("transparent_png_option", False)
    )
    project["style_name"] = str(
        st.session_state.get("v10_style_mode", project.get("style_name", ""))
    )
    project["text_style"] = str(
        st.session_state.get("v8_text_style", project.get("text_style", ""))
    )
    selected_font = st.session_state.get("v8_selected_font")
    if selected_font:
        try:
            project["font_name"] = (
                f"{int(selected_font):03d}｜"
                f"{V8_TEXT_EFFECT_CATALOG[int(selected_font)]}"
            )
        except Exception:
            project["font_name"] = str(selected_font)
    else:
        project["font_name"] = ""

    # 僅記錄生成方式，不記錄 API Key。
    api_mode = str(st.session_state.get("public_api_mode", ""))
    if "自己的" in api_mode:
        project["generation_method"] = "own_api"
    elif "免費" in api_mode or "網站" in api_mode:
        project["generation_method"] = "website_api"

    st.session_state["v12_current_project"] = project
    return dict(project)


for i in range(8):
    st.session_state.setdefault(f"sticker_text_{i}", "")
st.session_state.setdefault("uploaded_image_bytes", None)
st.session_state.setdefault("generated_4x2_bytes", None)
st.session_state.setdefault("last_prompt", "")
st.session_state.setdefault("crop_boxes", None)

def get_texts():
    return [st.session_state.get(f"sticker_text_{i}", "") for i in range(8)]

def set_texts(values):
    values = list(values)[:8] + [""] * 8
    for i in range(8):
        st.session_state[f"sticker_text_{i}"] = str(values[i])

def base_boxes(w, h):
    boxes = []
    for i in range(8):
        c, r = i % 4, i // 4
        x1 = round(c * w / 4)
        x2 = round((c + 1) * w / 4)
        y1 = round(r * h / 2)
        y2 = round((r + 1) * h / 2)
        boxes.append([x1, y1, x2, y2])
    return boxes

def build_prompt(style, custom_style, selected_character, custom_character,
                 texts, transparent):
    p = [
        "請以我提供的人物照片作為主要人物參考。",
        "保留人物身份辨識特徵，不任意改變人物核心外觀。",
        "請一次生成一張清楚的4×2八格LINE貼圖總圖。",
        "第一排四格、第二排四格；依使用者輸入順序由左至右、由上至下對應。",
        "八格人物維持同一人物身份與主要視覺風格。",
        "每格人物完整呈現，不要裁切頭部、臉部、身體或四肢。",
        "人物與該格邊界保持安全距離。",
        "不要拉伸、變形或壓縮人物。",
        "非常重要：圖片中禁止出現01、02、03、04、05、06、07、08等編號。",
        "禁止加入格號、序號、位置標籤或數字標記。",
        "只有使用者指定的貼圖文字可以出現在圖片中。",
    ]
    if style != "↓ 請選擇風格":
        p.append(f"主要貼圖風格：{style}。")
    if custom_style.strip():
        p.append(f"使用者自定風格：{custom_style.strip()}。")
    if selected_character:
        p.append("人物與畫面特色：" + "、".join(selected_character) + "。")
    if custom_character.strip():
        p.append(f"使用者自定人物／場景要求：{custom_character.strip()}。")
    for i, t in enumerate(texts):
        p.append(f"第{i+1}格的指定貼圖文字為：「{t.strip() or '（此格未指定文字）'}」。")
    if transparent:
        p.append("請使用透明背景PNG，背景保持真正透明，不要以白色或黑色填滿。")
    p.append("整體具有LINE貼圖的清楚、可讀、可愛與完整構圖感。")
    return "\n".join(p)

# ------------------------------------------------------------
# UI
# ------------------------------------------------------------
st.markdown("""<style>
.v10-rainbow-title{padding:8px 14px;border-radius:12px;margin:8px 0 12px;font-weight:700;background:linear-gradient(90deg,#fff1f2,#fff7ed,#fefce8,#f0fdf4,#eff6ff,#f5f3ff);}
.v10-soft-box{padding:8px 12px;border-radius:10px;background:#fafafa;border:1px solid #e5e7eb;}
</style>""",unsafe_allow_html=True)


# ============================================================
# V12｜STEP 01A①
# 主導航：開始製作 / 我的作品
# ============================================================
st.markdown(
    """
    <style>
    .v12-nav-wrap{
      width:min(920px,100%);
      margin:0 auto 1.1rem;
      padding:.45rem;
      border:1px solid rgba(120,120,120,.16);
      border-radius:18px;
      background:color-mix(in srgb,#64748b 6%, transparent);
    }
    </style>
    <div class="v12-nav-wrap"></div>
    """,
    unsafe_allow_html=True,
)

_v12_nav_cols = st.columns(2)
with _v12_nav_cols[0]:
    if st.button("✨ 開始製作", key="v12_nav_create", use_container_width=True):
        st.session_state["v12_view"] = "create"
        st.rerun()
with _v12_nav_cols[1]:
    if st.button("📚 我的作品", key="v12_nav_library", use_container_width=True):
        st.session_state["v12_view"] = "library"
        st.rerun()

st.session_state.setdefault("v12_view", "create")

if st.session_state["v12_view"] == "library":
    st.markdown('<div class="v10-main-title">📚 我的作品</div>', unsafe_allow_html=True)
    st.caption("這裡將顯示目前瀏覽器中保存的作品。作品不會寫入網站的每日 AI 額度資料。")

    _search_name = st.text_input(
        "🔎 搜尋作品名稱",
        placeholder="輸入作品名稱搜尋…",
        key="v12_project_search",
    )

    _projects = list(st.session_state.get("v12_projects_local_index", []))
    if _search_name.strip():
        needle = _search_name.strip().lower()
        _projects = [
            p for p in _projects
            if needle in str(p.get("project_name", "")).lower()
        ]

    if not _projects:
        st.info("📭 目前還沒有保存的作品")
        st.markdown(
            """
            完成一組貼圖後，它會出現在這裡。  
            下一步會逐步加入「作品名稱、瀏覽器本機暫存、作品縮圖與作品詳情」。
            """
        )

    st.divider()
    st.caption("V12｜STEP 01A①：目前只建立作品庫導航與 Project 資料骨架，尚未啟用永久保存。")
    st.stop()


st.markdown('<div class="v10-main-title">🎨 LINE 貼圖創作工作室</div>', unsafe_allow_html=True)
st.caption("V11｜公開版｜快速完成 LINE 貼圖創作")
st.markdown("""
<div class="v11-onboarding">
  <div class="v11-onboarding-title">✨ 第一次使用？照著 3 個步驟就可以開始</div>
  <div class="v11-onboarding-grid">
    <div class="v11-onboarding-card">
      <div class="v11-onboarding-step">① 上傳照片＋設定貼圖</div>
      <div class="v11-onboarding-text">依序選擇風格、人物特色、貼圖文字、字型與背景。</div>
    </div>
    <div class="v11-onboarding-card">
      <div class="v11-onboarding-step">② 選擇 AI 生成方式</div>
      <div class="v11-onboarding-text">可使用網站免費額度，或輸入自己的 OpenAI API Key。</div>
    </div>
    <div class="v11-onboarding-card">
      <div class="v11-onboarding-step">③ 生成 → 裁切 → 下載</div>
      <div class="v11-onboarding-text">生成八格總圖後，再調整裁切範圍並完成下載。</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)
st.markdown('<div class="v11-section-tip">💡 <b>小提醒：</b>第一次使用只要依照畫面上的 ①～⑧ 順序往下設定即可，不需要先閱讀複雜說明。</div>', unsafe_allow_html=True)
st.divider()

v10_section("📷 ① 上傳人物照片", "#ff5c7a")
st.caption("📌 先上傳一張清楚的人物照片，後續所有貼圖都會以這張照片作為主要參考。")
uploaded = st.file_uploader("選擇人物照片", type=["jpg","jpeg","png","webp"])
if uploaded:
    try:
        uploaded.seek(0)
        im = Image.open(uploaded)
        im.load()
        b = BytesIO()
        im.convert("RGBA").save(b, "PNG")
        st.session_state.uploaded_image_bytes = b.getvalue()
        _img_c1,_img_c2,_img_c3=st.columns([1,2,1])
        with _img_c2:
            st.image(im, caption="人物照片", width=420)
        st.success("✅ 人物照片已載入")
    except Exception as e:
        st.error("❌ 無法讀取人物照片")
        st.code(str(e))

st.divider()
V8_STYLE_CUSTOM_OPTION = "⭐ 自定義風格"

v10_section("🎨 ② 貼圖風格", "#ff9f43")
st.caption("🌈 預設風格與「自定義風格」二選一。選擇自定義後，才會出現可套用的 10 組儲存風格。")

# 自定義風格放在第 2 個位置，方便快速選擇。
_v8_style_items=[x for x in V8_STYLES if not x.startswith("⭐ 自訂")]
_style_options=["↓ 請選擇風格", "⭐ 自定義風格"] + _v8_style_items

style_mode=st.selectbox(
    "🌈 貼圖風格",
    _style_options,
    key="v10_style_mode",
)

if style_mode=="⭐ 自定義風格":
    style="↓ 請選擇風格"
    st.success("✨ 已切換到「自定義風格」模式")

    _custom_style_slots=[]
    for _i in range(1,11):
        _sv=st.session_state.get(f"v10_style_custom_{_i}","").strip()
        _sn=st.session_state.get(f"v10_style_name_{_i}",f"使用者自定{_i}").strip() or f"使用者自定{_i}"
        if _sv:
            _custom_style_slots.append((_i,_sn,_sv))

    _saved_labels=["✏️ 尚未選擇／新增"]+[f"{i:02d}｜{name}" for i,name,_ in _custom_style_slots]
    _saved_choice=st.selectbox(
        "💾 選擇已儲存的自定義風格",
        _saved_labels,
        key="v10_saved_custom_style_choice",
    )

    if _saved_choice!="✏️ 尚未選擇／新增":
        _pos=_saved_labels.index(_saved_choice)-1
        custom_style=_custom_style_slots[_pos][2]
        st.info(f"💾 已套用：{_custom_style_slots[_pos][0]:02d}｜{_custom_style_slots[_pos][1]}")
    else:
        custom_style=""

    with st.expander("💾 編輯／儲存自定義風格 1～10",expanded=False):
        for _i in range(1,11):
            _a,_b=st.columns([1,4])
            with _a:
                st.text_input(f"名稱 {_i:02d}",key=f"v10_style_name_{_i}")
            with _b:
                st.text_area(f"自定義風格 {_i:02d}",key=f"v10_style_custom_{_i}",height=65)

        if st.button("💾 儲存 10 組自定風格",key="v10_save_styles",use_container_width=True):
            if _save_v10_presets():
                st.success("✅ 10 組自定風格已儲存")
                st.rerun()
            else:
                st.error("❌ 儲存失敗")

    st.warning("ℹ️ 目前只使用「自定義風格」，不會同時套用其他 預設風格。")
else:
    style=style_mode
    custom_style=""

with st.expander("📚 查看全部預設風格",expanded=False):
    st.write("、".join(_style_options[2:]))

v10_section("👤 ③ 人物與畫面特色", "#2ecc71")
st.caption("可複選；以下 3 組自定義人物／場景需求，只有打勾才會啟用。")
selected_character=st.multiselect("🎯 人物／畫面特色（可複選）",CHARACTER_OPTIONS,key="v10_character_options")
for _i in range(1,4):
    _c1,_c2=st.columns([1,8])
    with _c1:
        st.checkbox("啟用",key=f"v10_character_enabled_{_i}")
    with _c2:
        st.text_area(f"自定義人物／場景需求 {_i}",key=f"v10_character_custom_{_i}",height=70)
_custom_character_values=[st.session_state.get(f"v10_character_custom_{_i}","").strip() for _i in range(1,4) if st.session_state.get(f"v10_character_enabled_{_i}",False)]
custom_character="\n".join(_custom_character_values)
if st.button("💾 儲存人物／場景設定",key="v10_save_character",use_container_width=True):
    if _save_v10_presets():
        st.success("✅ 3 組人物／場景設定已儲存")
    else:
        st.error("❌ 儲存失敗")

v10_section("💬 ④ 01～08 貼圖文字", "#3498db")
st.caption("🎲 內建語詞池＋你的專屬隨機語詞池。可新增、儲存，也可從池子隨機抽取。")

_pool_names=list(V8_RANDOM_POOLS.keys())
v10_subsection("🎲 隨機用語與自定義語詞池", "#3498db")
_pool_choice=st.selectbox(
    "🎲 隨機用語池",
    ["↓ 請選擇語詞池", "⭐ 我的自定義語詞池", "全部內建語詞"] + _pool_names,
    key="v10_phrase_pool_choice",
)

if _pool_choice=="⭐ 我的自定義語詞池":
    with st.expander("💾 我的自定義語詞池",expanded=True):
        _new_phrase=st.text_input(
            "➕ 新增一句語詞",
            key="v10_new_phrase",
            placeholder="例如：今天也要加油！",
        )
        _pa,_pb,_pc=st.columns(3)
        with _pa:
            if st.button("➕ 加入語詞池",key="v10_add_phrase",use_container_width=True):
                if _new_phrase.strip():
                    V10_CUSTOM_PHRASE_POOL.append(_new_phrase.strip())
                    V10_CUSTOM_PHRASE_POOL[:]=list(dict.fromkeys(V10_CUSTOM_PHRASE_POOL))
                    if _save_v10_phrase_pool(V10_CUSTOM_PHRASE_POOL):
                        st.success("✅ 已加入並儲存")
                        st.rerun()
                    else:
                        st.error("❌ 儲存失敗")
        with _pb:
            if st.button("🎲 從我的池子抽 8 句",key="v10_random_my_pool",use_container_width=True):
                if V10_CUSTOM_PHRASE_POOL:
                    vals=random.sample(V10_CUSTOM_PHRASE_POOL,min(8,len(V10_CUSTOM_PHRASE_POOL)))
                    while len(vals)<8:
                        vals.append(random.choice(V10_CUSTOM_PHRASE_POOL))
                    random.shuffle(vals)
                    set_texts(vals)
                    st.rerun()
                else:
                    st.warning("目前自定義語詞池是空的。")
        with _pc:
            if st.button("🗑️ 清空我的池子",key="v10_clear_my_pool",use_container_width=True):
                V10_CUSTOM_PHRASE_POOL.clear()
                if _save_v10_phrase_pool(V10_CUSTOM_PHRASE_POOL):
                    st.success("✅ 已清空")
                    st.rerun()

        if V10_CUSTOM_PHRASE_POOL:
            st.caption(f"目前共有 {len(V10_CUSTOM_PHRASE_POOL)} 句")
            st.write("、".join(V10_CUSTOM_PHRASE_POOL))
        else:
            st.info("尚未建立自定義語詞。")

    _active_pool=V10_CUSTOM_PHRASE_POOL
else:
    if _pool_choice=="↓ 請選擇語詞池":
        _active_pool=[]
        st.info("👆 請先選擇一個語詞池。")
    elif _pool_choice=="全部內建語詞":
        _active_pool=[x for vals in V8_RANDOM_POOLS.values() for x in vals]
    else:
        _active_pool=V8_RANDOM_POOLS.get(_pool_choice,[])

    a,b,c=st.columns(3)
    with a:
        if st.button("🎲 隨機填入 8 格",use_container_width=True,key="v10_random_v8"):
            if _active_pool:
                vals=random.sample(_active_pool,min(8,len(_active_pool)))
                while len(vals)<8:
                    vals.append(random.choice(_active_pool))
                random.shuffle(vals)
                set_texts(vals)
                st.rerun()
    with b:
        st.write(f"目前語詞池：{len(_active_pool)} 句")
    with c:
        st.write("內建語詞分類")

# 內建的「分類→語句→指定格」功能保留。
if _pool_choice not in ("⭐ 我的自定義語詞池", "↓ 請選擇語詞池"):
    p1,p2,p3=st.columns([1.2,2.4,0.8])
    with p1:
        _common_cat=st.selectbox("常用語分類",_pool_names,key="v8_common_cat")
    with p2:
        _common_phrase=st.selectbox("常用語參考",V8_RANDOM_POOLS.get(_common_cat,[]),key="v8_common_phrase")
    with p3:
        _target_slot=st.selectbox("放入第",[f"{i:02d}" for i in range(1,9)],key="v8_target_slot")
    if st.button("➕ 放入選定格",key="v8_insert_phrase"):
        set_texts([
            _common_phrase if i==int(_target_slot)-1 else st.session_state.get(f"sticker_text_{i}","")
            for i in range(8)
        ])
        st.rerun()

cols=st.columns(4)
for i,col in enumerate(cols):
    with col:
        st.text_input(f"{i+1:02d}",key=f"sticker_text_{i}")
cols=st.columns(4)
for i,col in enumerate(cols,start=4):
    with col:
        st.text_input(f"{i+1:02d}",key=f"sticker_text_{i}")

texts=get_texts()
filled=sum(bool(x.strip()) for x in texts)
st.info(f"已填寫 {filled} / 8 格")

with st.expander("📚 查看全部語詞分類與內容",expanded=False):
    for cat,vals in V8_RANDOM_POOLS.items():
        st.markdown(f"**{cat}**")
        st.write("、".join(vals))

st.divider()
v10_section("🔤 ⑤ 貼圖字型＋125 種帶圖字型", "#8e67d8")

v10_subsection("✏️ 一般貼圖字型效果", "#8e67d8")
text_style = st.selectbox(
    "文字貼圖效果",
    V8_TEXT_STYLE_OPTIONS,
    index=0,
    key="v8_text_style"
)

_selected_font = st.session_state.get("v8_selected_font", None)
v10_subsection("🔤 125 種帶圖字型", "#8e67d8")
st.markdown('<div id="v10-font-result-anchor"></div>', unsafe_allow_html=True)
if _selected_font:
    st.success(f"🎨 已選擇 125 字型：{_selected_font:03d}｜{V8_TEXT_EFFECT_CATALOG[_selected_font]}")
else:
    st.info("尚未指定 125 種字型；可從下方總覽選用。")

# ------------------------------------------------------------
# ------------------------------------------------------------
# 選字後真正跳回「已選字型」位置
# 使用 Streamlit Components v2 的原生 DOM JavaScript。
# ------------------------------------------------------------
if st.session_state.pop("v10_scroll_to_font_result", False):
    import streamlit.components.v2 as components
    _v10_font_scroll = components.component(
        "v10_font_scroll",
        html="<span aria-hidden='true'></span>",
        js="""
        export default function(component) {
            const anchor = document.querySelector("#v10-font-result-anchor");
            if (!anchor) return;
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    anchor.scrollIntoView({
                        behavior: "instant",
                        block: "start"
                    });
                });
            });
        }
        """,
        isolate_styles=False,
    )
    _v10_font_scroll(key="font_scroll_once")

# 125 種帶圖字型總覽
# 選中後「整個區塊不再渲染」，因此會真正收起，而不是只抖動。
# ------------------------------------------------------------
if "v10_font_gallery_open" not in st.session_state:
    st.session_state.v10_font_gallery_open = False

if st.button(
    "📚 125 種帶圖字型總覽" if not st.session_state.v10_font_gallery_open
    else "📖 關閉 125 種帶圖字型總覽",
    key="v10_font_gallery_toggle",
    use_container_width=True,
):
    st.session_state.v10_font_gallery_open = not st.session_state.v10_font_gallery_open
    st.rerun()

if st.session_state.v10_font_gallery_open:
    st.caption("🖱️ 點選字型後會立即關閉總覽，並回到目前選擇結果。")

    _font_cols = st.columns(5)
    for _i in range(1, 126):
        _p = V8_FONT_PREVIEW_DIR / f"{_i:03d}.jpg"
        if not _p.exists():
            continue

        with _font_cols[(_i - 1) % 5]:
            st.image(str(_p), use_container_width=True)
            st.caption(f"{_i:03d}｜{V8_TEXT_EFFECT_CATALOG[_i]}")

            if st.button(
                f"選用 {_i:03d}",
                key=f"font_pick_{_i}",
                use_container_width=True,
            ):
                st.session_state.v8_selected_font = _i
                st.session_state.v10_scroll_to_font_result = True

                # 核心：下一次 rerun 時完全不渲染 125 總覽。
                st.session_state.v10_font_gallery_open = False

                st.rerun()


with st.expander("🔎 已選字型大圖", expanded=False):
    if _selected_font:
        _p = V8_FONT_PREVIEW_DIR / f"{_selected_font:03d}.jpg"
        if _p.exists():
            st.image(str(_p), caption=f"{_selected_font:03d}｜{V8_TEXT_EFFECT_CATALOG[_selected_font]}", use_container_width=True)
            st.caption("以上為參考效果；實際生成會由 AI 依人物、文字與整體風格重新詮釋。")
    else:
        st.write("尚未選擇。")

st.divider()
v10_section("🌈 ⑥ 背景設定", "#16a085")
st.markdown('<div class="v11-transparent-title">🖼️ 透明背景</div>', unsafe_allow_html=True)
with st.container(key="transparent_png_option"):
    transparent = st.checkbox("使用透明背景 PNG", value=False)

v10_subsection("🌈 貼圖設定查看", "#ff9f43")
style_mode = st.session_state.get("v10_style_mode", "↓ 請選擇風格")

prompt = build_prompt(style, custom_style, selected_character,
                      custom_character, texts, transparent)

if style_mode == V8_STYLE_CUSTOM_OPTION:
    prompt += (
        "\n【V10 風格模式】目前使用「自定義風格」模式。"
        "請不要另外套用任何 預設風格，只依照使用者自定義風格描述生成。"
    )
else:
    prompt += (
        f"\n【V10 風格模式】目前使用預設風格：「{style_mode}」。"
        "不要把未選取的自定義風格加入生成。"
    )

_selected_font_for_prompt = st.session_state.get("v8_selected_font")
if text_style:
    prompt += f"\n文字貼圖效果：{text_style}。"
if _selected_font_for_prompt:
    prompt += (
        f"\n125種帶圖字型參考：{_selected_font_for_prompt:03d}｜"
        f"{V8_TEXT_EFFECT_CATALOG[_selected_font_for_prompt]}。"
        "\n請把此字型當作文字材質與視覺參考，不要照搬參考圖中的人物或其他內容。"
    )
with st.expander("🔍 點選查看貼圖設定"):
    st.markdown(
        """
        <div style="
            background:linear-gradient(135deg,#171c27,#202735);
            border:1px solid #394457;
            border-left:6px solid #58a6ff;
            border-radius:12px;
            padding:18px 22px;
            margin:8px 0 14px;
        ">
            <div style="font-size:24px;font-weight:800;color:#ffffff;margin-bottom:8px;">
                📝 AI 實際生成 Prompt（完整內容）
            </div>
            <div style="font-size:15px;color:#b9c4d4;line-height:1.6;">
                以下保留實際送給 AI 的完整 Prompt；只改善閱讀呈現，不修改生成內容。
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _prompt_text = str(prompt or "").strip()

    if _prompt_text:
        # 以「內容主題」分段，而不是只替少數標題上色。
        # 每個邏輯區塊都有自己的標題色、背景與分隔線。
        _lines = [x.strip() for x in _prompt_text.splitlines() if x.strip()]

        _groups = []
        _current = []
        _section_keywords = (
            "使用者自定義風格",
            "風格：", "角色：", "人物：", "構圖：", "色彩：",
            "整體氛圍：", "避免：", "人物與畫面特色：",
            "文字貼圖效果：", "125種帶圖字型參考：",
            "請使用透明背景PNG", "整體具有LINE貼圖",
            "第1格的指定貼圖文字", "第2格的指定貼圖文字",
            "第3格的指定貼圖文字", "第4格的指定貼圖文字",
            "第5格的指定貼圖文字", "第6格的指定貼圖文字",
            "第7格的指定貼圖文字", "第8格的指定貼圖文字",
            "目前使用",
        )

        for _line in _lines:
            # 只有真正的「主題開頭」才建立新區塊。
            # 第1～8格指定貼圖文字視為同一個「01～08 貼圖文字」區塊。
            _is_text_slot = bool(re.match(r"^第[1-8]格的指定貼圖文字", _line))
            _is_section = any(_line.startswith(k) for k in _section_keywords)

            if _is_text_slot:
                if _current and not any(
                    bool(re.match(r"^第[1-8]格的指定貼圖文字", x))
                    for x in _current
                ):
                    _groups.append(_current)
                    _current = []
                _current.append(_line)
                continue

            if _is_section and _current:
                _groups.append(_current)
                _current = []
            _current.append(_line)

        if _current:
            _groups.append(_current)

        # 若 Prompt 沒有明確換行，至少把常見主題標籤切出來。
        if len(_groups) == 1 and len(_lines) > 5:
            _raw = _lines[0]
            for _kw in _section_keywords:
                if _kw in _raw:
                    _parts = re.split(
                        r'(?=' + re.escape(_kw) + r')',
                        _raw
                    )
                    if len(_parts) > 1:
                        _groups = [[p.strip()] for p in _parts if p.strip()]
                        break

        _palette = [
            ("#67e8f9", "#10252d", "#1e5361"),  # 青
            ("#86efac", "#10281e", "#27623d"),  # 綠
            ("#f9a8d4", "#2d1726", "#70405a"),  # 粉
            ("#c4b5fd", "#211a35", "#51427c"),  # 紫
            ("#fde68a", "#2b2510", "#6b5b1e"),  # 黃
            ("#fdba74", "#2d1d11", "#704622"),  # 橘
            ("#93c5fd", "#13243a", "#365f91"),  # 藍
        ]

        _html = [
            '<div style="background:#0f141d;border:1px solid #303a4a;'
            'border-radius:14px;padding:10px 14px;'
            'font-family:Arial,Microsoft JhengHei,sans-serif;">'
        ]

        for _idx, _group in enumerate(_groups):
            _accent, _bg, _border = _palette[_idx % len(_palette)]
            _title = _group[0]

            # 01～08 指定貼圖文字統一使用一個彩色區塊。
            _is_slot_group = bool(
                re.match(r"^第[1-8]格的指定貼圖文字", _title)
            )
            if _is_slot_group:
                _heading = "01～08 指定貼圖文字"
                _rest = ""
                _title_is_custom = True
            else:
                _title_is_custom = False

            # 將「主題：內容」拆成彩色標題＋內容。
            _m = re.match(r'^([^：:]{1,24}[：:])(.*)$', _title)
            if not _title_is_custom:
                if _m:
                    _heading = _m.group(1)
                    _rest = _m.group(2).strip()
                else:
                    _heading = _title if len(_title) <= 28 else "Prompt 內容"
                    _rest = "" if _heading == _title else _title

            _safe_heading = (
                _heading.replace("&","&amp;")
                        .replace("<","&lt;")
                        .replace(">","&gt;")
            )

            _html.append(
                f'<div style="margin:10px 0 14px;background:{_bg};'
                f'border:1px solid {_border};border-left:5px solid {_accent};'
                f'border-radius:10px;overflow:hidden;">'
                f'<div style="padding:9px 14px;font-size:18px;font-weight:800;'
                f'color:{_accent};border-bottom:1px solid {_border};">'
                f'{_safe_heading}</div>'
                f'<div style="padding:9px 14px 11px;">'
            )

            if _rest:
                _safe = (
                    _rest.replace("&","&amp;")
                         .replace("<","&lt;")
                         .replace(">","&gt;")
                )
                _html.append(
                    f'<div style="font-size:16px;line-height:1.85;'
                    f'color:#f1f5f9;padding:2px 0 5px;">{_safe}</div>'
                )

            for _line in _group[1:]:
                _safe = (
                    _line.replace("&","&amp;")
                         .replace("<","&lt;")
                         .replace(">","&gt;")
                )
                _html.append(
                    f'<div style="font-size:16px;line-height:1.85;'
                    f'color:#e7edf5;padding:3px 0;">{_safe}</div>'
                )

            _html.append("</div></div>")

        _html.append("</div>")

        st.markdown(
            "".join(_html),
            unsafe_allow_html=True,
        )
    else:
        st.info("目前尚未產生 AI Prompt。")



# ============================================================
# V11 STEP 02B-3A｜使用者自有 OpenAI API
#
# 安全原則：
# 1. 預設仍使用網站免費額度。
# 2. 使用者選擇「自己的 OpenAI API」後，不扣全站 10 次。
# 3. API Key 僅放在目前 Streamlit Session。
# 4. 不寫入 Supabase / JSON / GitHub / Streamlit Secrets。
# 5. 預設隱碼；可由使用者自行切換顯示。
# ============================================================
v10_section("🤖 ⑦ AI 生成方式", "#6366f1")
st.caption("📌 選擇一種方式即可：使用網站免費額度，或使用自己的 OpenAI API。")

_api_mode = st.radio(
    "請選擇生成方式",
    [
        "🆓 使用網站免費額度",
        "🔑 使用自己的 OpenAI API",
    ],
    key="v11_api_mode",
)

_v11_user_api_key = ""

if _api_mode == "🆓 使用網站免費額度":
    st.caption(
        "🎁 使用網站提供的免費額度，所有訪客共用每日 10 次。"
    )
    _daily_quota = _show_daily_ai_quota()

else:
    st.caption(
        "💡 適合需要較多生成次數的使用者；使用自己的 API 時，"
        "不受網站每日 10 次額度限制。"
    )

    st.info(
        "🔐 **隱私提醒**\n\n"
        "本網站設計，只將這組 Key 提供目前這個瀏覽器暫時使用。"
    )

    _show_v11_key = st.checkbox(
        "👁️ 顯示 API Key（再次點擊即可隱藏）",
        value=False,
        key="v11_show_api_key",
    )

    _v11_user_api_key = st.text_input(
        "OpenAI API Key",
        type="default" if _show_v11_key else "password",
        placeholder="sk-••••••••••••••••••••",
        key="v11_user_api_key",
        help="請輸入你自己的 OpenAI API Key。",
    ).strip()

    if _v11_user_api_key:
        st.success(
            "🔒 已取得本次 Session 的 API Key。"
            "使用「自己的 API」時，不受網站每日 10 次額度限制。"
        )
    else:
        st.warning("⚠️ 請先輸入自己的 OpenAI API Key。")

v10_section("✨ ⑧ 生成 4×2 原始總圖", "#e67e22")
st.markdown('<div class="v11-section-tip">📌 <b>準備完成後：</b>按一次生成即可。生成期間按鈕會自動鎖定，請耐心等待。</div>', unsafe_allow_html=True)

# ============================================================
# V11｜STEP 02C-2｜兩階段生成鎖定（正式版）
#
# 核心設計：
# ① 使用者第一次按下生成：只設定 pending lock，立即 st.rerun()
#    → 本次不呼叫 AI。
# ② 下一次 rerun：先把真正的 st.button 以 disabled=True 畫出來，
#    → 此時按鈕已經是不可點擊狀態，再開始 AI 生成。
# ③ 成功／失敗後解除 lock。
#
# 不依賴 JavaScript，不嘗試修改 Streamlit DOM。
# 後端 Session Lock + Supabase quota / RPC / RLS 仍是安全主防線。
# ============================================================
st.session_state.setdefault("v11_generation_pending", False)
st.session_state.setdefault("v11_generation_in_progress", False)

_generation_pending = bool(st.session_state.get("v11_generation_pending", False))
_generation_in_progress = bool(st.session_state.get("v11_generation_in_progress", False))
_generation_locked = _generation_pending or _generation_in_progress

# ------------------------------------------------------------
# 第一階段：使用者按下按鈕
# 只做必要的輸入檢查，設定 pending lock，立即 rerun。
# 這樣下一次畫面重繪時，按鈕會先以 disabled=True 呈現，
# 然後才進入長時間 AI 工作。
# ------------------------------------------------------------
if st.button(
    "🔄 AI 正在生成，請稍候……" if _generation_locked else "✨ 生成 4×2 八格總圖",
    type="primary",
    use_container_width=True,
    disabled=_generation_locked,
    key="v11_generate_4x2",
):
    if not st.session_state.uploaded_image_bytes:
        st.warning("請先上傳人物照片。")
        st.stop()

    if not filled:
        st.warning("請至少輸入一格貼圖文字。")
        st.stop()

    if _api_mode == "🔑 使用自己的 OpenAI API" and not _v11_user_api_key:
        st.error("❌ 請先輸入自己的 OpenAI API Key。")
        st.stop()

    # 先鎖定，再立即重新繪製畫面；本次不呼叫 AI。
    st.session_state["v11_generation_pending"] = True
    st.session_state["v11_generation_started_at"] = __import__("time").time()
    st.rerun()

# ------------------------------------------------------------
# 第二階段：只有 pending lock 存在時才進入真正生成。
# 此時上面的 st.button 已經先以 disabled=True 呈現。
# 因此使用者看到的是「不可按」的生成中按鈕，再開始 AI 工作。
# ------------------------------------------------------------
if st.session_state.get("v11_generation_pending", False):
    st.session_state["v11_generation_pending"] = False
    st.session_state["v11_generation_in_progress"] = True
    _generation_locked = True

    st.info("🔒 AI 生成進行中，本次操作已鎖定，請稍候……")

    # ========================================================
    # V11 STEP 02B-3A
    # API 路徑分流：
    # A. 網站免費額度：先原子取得 1 次額度，再呼叫網站 API。
    # B. 使用自己的 OpenAI API：不扣網站每日 10 次額度。
    # ========================================================
    _ai_quota_claimed = False

    try:
        if _api_mode == "🔑 使用自己的 OpenAI API":
            if not _v11_user_api_key:
                st.error("❌ 請先輸入自己的 OpenAI API Key。")
                raise RuntimeError("missing_user_api_key")

            _generation_client = OpenAI(api_key=_v11_user_api_key)

        else:
            with st.spinner("正在確認全站 AI 額度……"):
                _quota_claim = _consume_daily_ai_quota()

            if _quota_claim is None:
                st.error(
                    "❌ 目前無法確認全站 AI 額度，因此為了保護系統與 API 費用，"
                    "本次不會執行 AI 生成。請稍後再試。"
                )
                raise RuntimeError("quota_unavailable")

            _granted = bool(_quota_claim.get("granted", False))
            _remaining_after_claim = int(_quota_claim.get("remaining", 0))
            _limit_after_claim = int(_quota_claim.get("quota_limit", 10))

            if _limit_after_claim <= 0:
                st.error("❌ AI 額度設定異常，本次不執行生成。")
                raise RuntimeError("invalid_quota_limit")

            if _remaining_after_claim < 0 or _remaining_after_claim > _limit_after_claim:
                st.error("❌ AI 額度資料異常，本次不執行生成。")
                raise RuntimeError("invalid_quota_remaining")

            if not _granted:
                st.error("🔴 全站今日 AI 額度已用完，請明天再試。")
                raise RuntimeError("quota_exhausted")

            _ai_quota_claimed = True
            _generation_client = client

        with st.spinner("AI 正在生成 4×2 原始總圖……"):
            ib = BytesIO(st.session_state.uploaded_image_bytes)
            # V11｜STEP 02C-4②
            # 等待提示是「等待體驗」，不代表 OpenAI 真實完成百分比。
            # 180 秒後逾時；不自動 retry，沿用原本的例外／退款路徑。
            _progress = st.progress(0)
            _status = st.empty()
            _started_at = time.monotonic()
            _progress.progress(0.05)
            _status.info("🎨 正在分析你的照片……")

            try:
                _progress.progress(0.18)
                _status.info("🖌️ 正在準備貼圖構圖……")

                # OpenAI SDK timeout：最長等待 180 秒。
                result = _generation_client.with_options(timeout=180).images.edit(
                model="gpt-image-2",
                image=("person.png", ib, "image/png"),
                prompt=(
                    prompt
                    + "\n\n【透明背景強制要求】"
                    + "\n輸出必須是真正的透明 PNG Alpha 背景。"
                    + "\n背景區域必須為 Alpha=0，不得繪製白色、灰色或任何棋盤格圖案。"
                    + "\n絕對不要用棋盤格、灰白方格或任何圖案來模擬透明背景。"
                    + "\n人物、物件與文字保留正常不透明像素，只有背景透明。"
                ),
                size="1536x1024",
                background="transparent",
                output_format="png",
            )

                # V11｜02C-4④｜異常回應資料防護
                # API 呼叫成功不代表一定取得有效圖片；空 data / 缺少 b64_json
                # 必須視為生成失敗，交回原本的 exception / refund 流程。
                if not getattr(result, "data", None):
                    raise RuntimeError("AI 回應成功，但沒有取得有效圖片資料，請重新操作。")
                
                _image_item = result.data[0]
                _b64_json = getattr(_image_item, "b64_json", None)
                if not _b64_json:
                    raise RuntimeError("AI 回應成功，但圖片資料不完整，請重新操作。")

                _progress.progress(0.88)
                _status.info("🖼️ 原始總圖處理中……")
                _progress.progress(0.96)
                _status.info("✂️ 正在準備 8 張貼圖……")
                _progress.progress(1.0)
                _status.success("🎉 AI 生成完成，正在進行最後圖片處理……")
            except Exception as _gen_exc:
                _elapsed = time.monotonic() - _started_at
                if _elapsed >= 180:
                    _v11_clear_generation_state()
                raise TimeoutError("AI 生成逾時（超過 3 分鐘），請重新操作。") from _gen_exc
                raise
            raw = base64.b64decode(result.data[0].b64_json)
            img = Image.open(BytesIO(raw)).convert("RGBA")
            out = BytesIO()
            img.save(out, "PNG")
            st.session_state.generated_4x2_bytes = out.getvalue()
            st.session_state.crop_boxes = None
            st.success("🎉 4×2 原始總圖生成成功！")

            # 生成成功：本次 quota 保留，不退款。
            _fresh_quota = _get_daily_ai_quota()
            if _fresh_quota is not None:
                st.session_state["public_last_quota"] = _fresh_quota


    except Exception as e:
        # 只有網站免費額度模式且已成功扣額度時才退款。
        # 使用者自己的 API 不涉及網站額度。
        if _api_mode == "🆓 使用網站免費額度" and _ai_quota_claimed:
            _refund_result = _refund_daily_ai_quota()
            if _refund_result is not None:
                st.info("↩️ AI 生成失敗，本次網站 AI 額度已退回。")
            else:
                st.warning(
                    "⚠️ AI 生成失敗，而且系統目前無法確認額度退款狀態；"
                    "請檢查 Supabase 後再繼續測試。"
                )
        elif str(e) not in {"missing_user_api_key", "quota_unavailable", "invalid_quota_limit", "invalid_quota_remaining", "quota_exhausted"}:
            st.info(
                "ℹ️ 這次使用的是你自己的 OpenAI API；"
                "沒有扣除網站每日 10 次額度，因此不需要網站額度退款。"
            )

        # 前面若已顯示明確的額度／Key 錯誤，就不要重複顯示「生成失敗」。
        if str(e) not in {"missing_user_api_key", "quota_unavailable", "invalid_quota_limit", "invalid_quota_remaining", "quota_exhausted"}:
            st.error("❌ 生成失敗")
            st.caption(f"錯誤類型：{type(e).__name__}")

    finally:
        # 成功、失敗、額度不足、例外都解除鎖定。
        # 下一次正常 rerun 時，生成按鈕恢復可用。
        st.session_state["v11_generation_in_progress"] = False
        st.session_state["v11_generation_pending"] = False
        st.session_state["v11_generation_finished_at"] = __import__("time").time()

# ------------------------------------------------------------
# STEP 10C native component
# ------------------------------------------------------------
# ------------------------------------------------------------
if st.session_state.generated_4x2_bytes:
    st.divider()
    v10_section("✂️ ⑦ 直接用滑鼠調整 8 個裁切框", "#e74c3c")

    src = Image.open(BytesIO(st.session_state.generated_4x2_bytes)).convert("RGBA")
    w, h = src.size

    if st.session_state.crop_boxes is None:
        st.session_state.crop_boxes = base_boxes(w, h)

    st.info(
        "直接拖曳：移動裁切框。拖曳四角：改變大小。"
        "拖曳四邊：單方向調整。8 個框同時顯示，不需要逐張打開。"
    )

    # --------------------------------------------------------
    # 明確顯示原始 4×2 圖
    # 不依賴 Canvas 是否成功載入圖片。
    # 固定預覽寬度，避免隨網頁容器無限放大。
    # --------------------------------------------------------
    v10_subsection("🖼️ 原始 4×2 圖片", "#e74c3c")
    st.markdown('<div class="v10-centered-image">', unsafe_allow_html=True)
    st.image(
    st.session_state.generated_4x2_bytes,
    caption=f"原始生成圖：{w} × {h} px",
    width=900,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    st.caption(
        "上方是原始圖片預覽；下方 Canvas 才是可直接拖曳的裁切操作區。"
    )

    _CROP_HTML_TEMPLATE = '<!doctype html>\n<html><head><meta charset="utf-8">\n<style>\n*{box-sizing:border-box}\nbody{margin:0;font-family:Arial,"Microsoft JhengHei",sans-serif;color:#333}\n.help{font-size:14px;line-height:1.6;background:#f5f7fa;padding:10px;border-radius:8px}\n.viewer{position:relative;width:720px;max-width:100%;margin:10px auto 0;border:1px solid #bbb;border-radius:8px;overflow:hidden;background:#eee}\n#cv{display:block;width:720px;max-width:100%;height:auto;touch-action:none;user-select:none}\n.status{font-size:28px;line-height:1.45;font-weight:700;padding:12px 0;color:#fff;text-align:center}\n.actions{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}\nbutton{border:0;border-radius:8px;padding:9px 13px;cursor:pointer}\nbutton.primary{background:#222;color:#fff}\nbutton.lock{background:#333;color:#fff}\nbutton:disabled{opacity:.45;cursor:not-allowed}\n.coords{font:20px/1.6 Consolas,monospace;white-space:pre-wrap;background:#1b2028;color:#fff;padding:14px;border-radius:10px;text-align:center}\n.legend{font-size:26px;line-height:1.5;font-weight:700;padding:10px 0;color:#fff;text-align:center}\n</style></head><body>\n<div class="help">\n<b>📍 定位點裁切</b><br>\n3 條上半部＋3 條下半部垂直定位線＋1 條水平定位線。\n上下 6 條藍色垂直線可各自獨立拖曳；按「🔒 鎖定定位」後產生 01～08 裁切框。\n</div>\n<div class="viewer"><canvas id="cv"></canvas></div>\n<div class="status" id="status">正在建立定位線……</div>\n<div class="legend">🔴 固定外框\u3000🔵 上下 6 條獨立垂直分隔線\u3000🟠 水平分隔線\u3000｜\u3000🔒 鎖定後可進行裁切</div>\n<div class="actions">\n<button onclick="resetGuides()">↩️ 恢復分隔線位置</button>\n<button id="lockBtn" class="lock" onclick="toggleLock()">🔒 鎖定定位</button>\n<button id="downloadBtn" class="primary" onclick="downloadAll()" disabled>✂️ 裁切並依序下載01～08(手機下載)</button>\n</div>\n\n<script>\nconst B64="__IMAGE_B64__", IW=__IW__, IH=__IH__;\nconst cv=document.getElementById("cv"),ctx=cv.getContext("2d");\nconst statusEl=document.getElementById("status"),coordsEl=document.getElementById("coords");\nconst lockBtn=document.getElementById("lockBtn"),downloadBtn=document.getElementById("downloadBtn");\nconst colors=["#ff4040","#3987ff","#32ad61","#ff922e"];\nlet scale=1,locked=false,active=-1,startX=0,startY=0,snap=null;\n\nfunction clamp(v,a,b){return Math.max(a,Math.min(b,v))}\nfunction guidesDefault(){\n  return {\n    xTop:[IW/4,IW/2,3*IW/4],\n    xBottom:[IW/4,IW/2,3*IW/4],\n    y:[0,IH/2,IH]\n  };\n}\nlet g=guidesDefault();\n\nconst image=new Image();\nimage.src="data:image/png;base64,"+B64;\n\nfunction resize(){\n  const viewer=cv.parentElement;\n  const mw=Math.min(720,Math.max(320,viewer.clientWidth||720));\n  cv.width=Math.round(mw);\n  cv.height=Math.round(mw*IH/IW);\n  scale=cv.width/IW;\n  draw();\n}\n\nfunction boxes(){\n  const out=[];\n  const xt=[0,g.xTop[0],g.xTop[1],g.xTop[2],IW];\n  const xb=[0,g.xBottom[0],g.xBottom[1],g.xBottom[2],IW];\n  for(let c=0;c<4;c++) out.push([xt[c],g.y[0],xt[c+1],g.y[1]]);\n  for(let c=0;c<4;c++) out.push([xb[c],g.y[1],xb[c+1],g.y[2]]);\n  return out;\n}\n\nfunction draw(){\n  ctx.clearRect(0,0,cv.width,cv.height);\n  ctx.drawImage(image,0,0,cv.width,cv.height);\n\n  // Slight guide shading.\n  ctx.save();\n  ctx.fillStyle="rgba(255,255,255,.08)";\n  ctx.fillRect(0,0,cv.width,cv.height);\n  ctx.restore();\n\n  // 上下各 3 條：六條垂直線完全獨立。\n  for(let i=0;i<3;i++){\n    const xt=g.xTop[i]*scale;\n    const xb=g.xBottom[i]*scale;\n    ctx.save();\n    ctx.strokeStyle="#3987ff";\n    ctx.lineWidth=2.5;\n    ctx.setLineDash([10,7]);\n    ctx.beginPath();ctx.moveTo(xt,0);ctx.lineTo(xt,g.y[1]*scale);ctx.stroke();\n    ctx.beginPath();ctx.moveTo(xb,g.y[1]*scale);ctx.lineTo(xb,cv.height);ctx.stroke();\n    ctx.setLineDash([]);\n    ctx.fillStyle="#3987ff";\n    ctx.fillRect(xt-5,4,10,18);\n    ctx.fillRect(xb-5,g.y[1]*scale+4,10,18);\n    ctx.restore();\n  }\n\n  // 左右外框固定。\n  ctx.save();\n  ctx.strokeStyle="#ff4040";\n  ctx.lineWidth=2.5;\n  ctx.setLineDash([10,7]);\n  ctx.beginPath();ctx.moveTo(0,0);ctx.lineTo(0,cv.height);ctx.stroke();\n  ctx.beginPath();ctx.moveTo(cv.width,0);ctx.lineTo(cv.width,cv.height);ctx.stroke();\n  ctx.setLineDash([]);\n  ctx.fillStyle="#ff4040";\n  ctx.fillRect(0,4,10,18);\n  ctx.fillRect(cv.width-10,4,10,18);\n  ctx.restore();  // Draw 3 horizontal guide lines.\n  for(let i=0;i<3;i++){\n    const y=g.y[i]*scale;\n    ctx.save();\n    ctx.strokeStyle="#ff922e";\n    ctx.lineWidth=i===1?2.5:2;\n    ctx.setLineDash([10,7]);\n    ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(cv.width,y);ctx.stroke();\n    ctx.setLineDash([]);\n    ctx.fillStyle="#ff922e";\n    ctx.fillRect(4,y-5,22,10);\n    ctx.restore();\n  }\n\n  // Number each derived cell; these are guide labels only.\n  const b=boxes();\n  const cellColors=["#ff4040","#3987ff","#32ad61","#a04bd0","#ff922e","#25aeb0","#db3f9b","#956c3c"];\n  for(let i=0;i<8;i++){\n    const x=b[i][0]*scale,y=b[i][1]*scale;\n    ctx.save();\n    ctx.font="bold 17px Arial";\n    ctx.lineWidth=3;\n    ctx.strokeStyle="rgba(255,255,255,.95)";\n    ctx.strokeText(String(i+1).padStart(2,"0"),x+8,y+21);\n    ctx.fillStyle=cellColors[i];\n    ctx.fillText(String(i+1).padStart(2,"0"),x+8,y+21);\n    ctx.restore();\n  }\n\n  updateCoords();\n}\n\nfunction updateCoords(){\n  // 座標資訊已從使用者介面移除；保留函式避免影響既有裁切流程。\n}\n\nfunction pointerPos(e){\n  const r=cv.getBoundingClientRect();\n  return {x:(e.clientX-r.left)*IW/r.width,y:(e.clientY-r.top)*IH/r.height};\n}\n\nfunction nearestGuide(p){\n  const tol=Math.max(18,18/scale);\n  let best=-1,bd=Infinity,type="";\n  const arr=p.y<g.y[1] ? g.xTop : g.xBottom;\n  const segType=p.y<g.y[1] ? "xTop" : "xBottom";\n  for(let i=0;i<3;i++){\n    const d=Math.abs(p.x-arr[i]);\n    if(d<tol&&d<bd){best=i;bd=d;type=segType;}\n  }\n  const dy=Math.abs(p.y-g.y[1]);\n  if(dy<tol&&dy<bd){best=1;bd=dy;type="y";}\n  return {index:best,type:type};\n}cv.addEventListener("pointerdown",e=>{\n  if(locked)return;\n  const p=pointerPos(e),h=nearestGuide(p);\n  if(h.index<0)return;\n  e.preventDefault();\n  try{cv.setPointerCapture(e.pointerId)}catch(_){}\n  active=h.index;startX=p.x;startY=p.y;snap={xTop:[...g.xTop],xBottom:[...g.xBottom],y:[...g.y],type:h.type};\n  statusEl.textContent="🖱️ 正在調整定位線……";\n});\n\ncv.addEventListener("pointermove",e=>{\n  if(active<0||locked)return;\n  e.preventDefault();\n  const p=pointerPos(e);\n  if(snap.type==="xTop" || snap.type==="xBottom"){\n    const arr=snap.type==="xTop" ? g.xTop : g.xBottom;\n    const snapArr=snap.type==="xTop" ? snap.xTop : snap.xBottom;\n    const min=30;\n    const lo=(active===0 ? 0 : arr[active-1])+min;\n    const hi=(active===2 ? IW : arr[active+1])-min;\n    arr[active]=clamp(snapArr[active]+(p.x-startX),lo,hi);\n  }else{\n    const min=30;\n    g.y[1]=clamp(snap.y[1]+(p.y-startY),g.y[0]+min,g.y[2]-min);\n  }\n  draw();\n});\n\ncv.addEventListener("pointerup",e=>{\n  if(active>=0){try{cv.releasePointerCapture(e.pointerId)}catch(_){}}\n  active=-1;\n  if(!locked)statusEl.textContent="✅ 定位線已更新";\n});\n\nfunction resetGuides(){\n  locked=false;\n  g=guidesDefault();\n  lockBtn.textContent="🔒 鎖定定位";\n  downloadBtn.disabled=true;\n  statusEl.textContent="↩️ 已恢復標準4×2定位";\n  draw();\n}\n\nfunction toggleLock(){\n  locked=!locked;\n  if(locked){\n    lockBtn.textContent="🔓 解鎖定位";\n    downloadBtn.disabled=false;\n    statusEl.textContent="🔒 定位已鎖定，可以開始裁切";\n  }else{\n    lockBtn.textContent="🔒 鎖定定位";\n    downloadBtn.disabled=true;\n    statusEl.textContent="🛠️ 定位已解鎖，可以繼續微調";\n  }\n  draw();\n}\n\nfunction saveBlob(blob,name){\n  const u=URL.createObjectURL(blob),a=document.createElement("a");\n  a.href=u;a.download=name;document.body.appendChild(a);a.click();a.remove();\n  setTimeout(()=>URL.revokeObjectURL(u),1000);\n}\n\n// V10 STEP 10C.6：移植 V8「邊界連通背景移除」邏輯。\n// 只移除從圖片邊緣連通、且接近背景色的區域；不整片刪除人物/文字中的白色。\nfunction removeConnectedBackground(canvas, tolerance=30){\n  const ctx2=canvas.getContext("2d",{willReadFrequently:true});\n  const W=canvas.width,H=canvas.height;\n  const img=ctx2.getImageData(0,0,W,H);\n  const px=img.data;\n\n  const pts=[\n    [0,0],[W-1,0],[0,H-1],[W-1,H-1],\n    [Math.min(4,W-1),Math.min(4,H-1)],\n    [Math.max(0,W-5),Math.min(4,H-1)],\n    [Math.min(4,W-1),Math.max(0,H-5)],\n    [Math.max(0,W-5),Math.max(0,H-5)]\n  ];\n\n  let sr=0,sg=0,sb=0,count=0;\n  for(const [x,y] of pts){\n    const k=(y*W+x)*4;\n    if(px[k+3]===0) continue;\n    sr+=px[k]; sg+=px[k+1]; sb+=px[k+2]; count++;\n  }\n  if(count===0) return;\n\n  const bg=[sr/count,sg/count,sb/count];\n  const tol2=tolerance*tolerance;\n\n  function nearBg(k){\n    if(px[k+3]===0) return true;\n    const dr=px[k]-bg[0],dg=px[k+1]-bg[1],db=px[k+2]-bg[2];\n    return dr*dr+dg*dg+db*db<=tol2;\n  }\n\n  const seen=new Uint8Array(W*H);\n  const qx=[],qy=[];\n  let head=0;\n\n  function push(x,y){\n    if(x<0||x>=W||y<0||y>=H) return;\n    const n=y*W+x;\n    if(seen[n]) return;\n    seen[n]=1;\n    qx.push(x);qy.push(y);\n  }\n\n  for(let x=0;x<W;x++){push(x,0);push(x,H-1);}\n  for(let y=0;y<H;y++){push(0,y);push(W-1,y);}\n\n  while(head<qx.length){\n    const x=qx[head],y=qy[head++];\n    const k=(y*W+x)*4;\n    if(!nearBg(k)) continue;\n    px[k+3]=0;\n    push(x-1,y);push(x+1,y);push(x,y-1);push(x,y+1);\n  }\n\n  ctx2.putImageData(img,0,0);\n}\n\nfunction makeSticker(i){\n  const b=boxes()[i].map(v=>Math.round(v));\n  const x1=clamp(b[0],0,IW-2),y1=clamp(b[1],0,IH-2);\n  const x2=clamp(b[2],x1+2,IW),y2=clamp(b[3],y1+2,IH);\n  const cw=370,ch=320,sw=x2-x1,sh=y2-y1;\n  const rat=Math.min(cw/sw,ch/sh),nw=Math.max(1,Math.round(sw*rat)),nh=Math.max(1,Math.round(sh*rat));\n\n  const o=document.createElement("canvas");\n  o.width=cw;o.height=ch;\n  const octx=o.getContext("2d",{willReadFrequently:true});\n  octx.clearRect(0,0,cw,ch);\n\n  // 保留 V10 原本的定位點裁切、等比例縮放、置中。\n  octx.drawImage(\n    image,x1,y1,sw,sh,\n    Math.round((cw-nw)/2),Math.round((ch-nh)/2),nw,nh\n  );\n\n  // 只有勾選「透明背景 PNG」時才套用 V8 邏輯。\n  if(__TRANSPARENT__){\n    removeConnectedBackground(o,30);\n  }\n\n  return new Promise(r=>o.toBlob(r,"image/png"));\n}\n\nasync function downloadAll(){\n  if(!locked)return;\n  statusEl.textContent="⏳ 正在製作01～08 PNG……";\n  for(let i=0;i<8;i++){\n    saveBlob(await makeSticker(i),String(i+1).padStart(2,"0")+".png");\n    await new Promise(r=>setTimeout(r,180));\n  }\n  statusEl.textContent="🎉 01～08 已全部裁切並下載！";\n}\n\nimage.onload=()=>{\n  resize();\n  statusEl.textContent="✅ 定位線已建立：上 3 條＋下 3 條藍色垂直線可獨立拖曳";\n};\nwindow.addEventListener("resize",resize);\n</script></body></html>'
    _image_b64 = base64.b64encode(st.session_state.generated_4x2_bytes).decode("ascii")
    _boxes_json = __import__("json").dumps(st.session_state.crop_boxes, ensure_ascii=False)
    _crop_html = _CROP_HTML_TEMPLATE.replace("__IMAGE_B64__", _image_b64).replace("__IW__", str(int(w))).replace("__IH__", str(int(h))).replace("__BOXES__", _boxes_json).replace("__TRANSPARENT__", "true" if transparent else "false")
    import streamlit.components.v1 as components
    components.html(
        _crop_html,
        height=760,
        scrolling=False,
    )


    # ============================================================
    # V10 STEP 11B.1
    # 直接從 01～08 選擇 MAIN / TAB＋一鍵打包
    #
    # 設計原則：
    # 1. 不重新上傳 01～08。
    # 2. 不修改 STEP 10C.8 的 AI 生成、透明、定位核心。
    # 3. 使用目前原始 4×2 圖＋定位座標直接在伺服器端裁切。
    # 4. main/tab 選擇與裁切在同一頁完成。
    # ============================================================
    st.divider()
    v10_section("⭐ STEP 11B｜選擇 MAIN / TAB（電腦版下載）", "#9b59b6")
    st.markdown(
        '<div style="font-size:28px;line-height:1.5;font-weight:700;'
        'text-align:center;color:#fff;margin:10px 0 22px;">'
        '調整好定位線後，直接指定哪一格做 MAIN、哪一格做 TAB。'
        '</div>',
        unsafe_allow_html=True,
    )

    # The browser editor keeps the guide coordinates in JS. For this first
    # stable version, provide a simple 01～08 selector tied to the standard
    # 4×2 positions. The final crop package still uses the original image.
    _main_tab_cols = st.columns(4)
    _main_tab_options = [f"{i:02d}" for i in range(1,9)]

    if "step11b1_main" not in st.session_state:
        st.session_state.step11b1_main = "01"
    if "step11b1_tab" not in st.session_state:
        st.session_state.step11b1_tab = "02"

    with _main_tab_cols[0]:
        st.markdown("### ⭐ MAIN")
    with _main_tab_cols[1]:
        st.markdown("### 🏷️ TAB")
    with _main_tab_cols[2]:
        st.markdown("### 📦 完整套件")
    with _main_tab_cols[3]:
        st.markdown("### 🖼️ 透明背景")

    cmain, ctab = st.columns(2)
    with cmain:
        main_no = st.selectbox(
            "選擇 MAIN",
            _main_tab_options,
            index=_main_tab_options.index(st.session_state.step11b1_main),
            key="step11b1_main_select",
            help="此格會製作 main.png（240×240）"
        )
        st.session_state.step11b1_main = main_no

    with ctab:
        tab_choices = [x for x in _main_tab_options if x != main_no]
        if st.session_state.step11b1_tab not in tab_choices:
            st.session_state.step11b1_tab = tab_choices[0]
        tab_no = st.selectbox(
            "選擇 TAB",
            tab_choices,
            index=tab_choices.index(st.session_state.step11b1_tab),
            key="step11b1_tab_select",
            help="此格會製作 tab.png（96×74）"
        )
        st.session_state.step11b1_tab = tab_no

    st.info(
        f"目前設定：⭐ MAIN = {main_no}　｜　🏷️ TAB = {tab_no}　｜　"
        f"其他 6 張照正常 01～08 輸出"
    )

    # Server-side crop helper based on the current original 4x2 image.
    # The initial guide grid is standard 4x2; this is intentionally isolated
    # so the successful STEP 10C.8 browser editor is not changed.
    def _v11b1_crop_cell(sheet, idx):
        sw, sh = sheet.size
        col = idx % 4
        row = idx // 4
        x1 = round(col * sw / 4)
        x2 = round((col + 1) * sw / 4)
        y1 = round(row * sh / 2)
        y2 = round((row + 1) * sh / 2)

        crop = sheet.crop((x1, y1, x2, y2)).convert("RGBA")
        out = Image.new("RGBA", (370, 320), (255,255,255,0))
        scale = min(370 / crop.width, 320 / crop.height)
        nw = max(1, round(crop.width * scale))
        nh = max(1, round(crop.height * scale))
        crop = crop.resize((nw, nh), Image.Resampling.LANCZOS)
        out.alpha_composite(crop, ((370-nw)//2, (320-nh)//2))
        return out

    def _v11b1_special(im, size):
        out = Image.new("RGBA", size, (255,255,255,0))
        scale = min(size[0]/im.width, size[1]/im.height)
        nw=max(1,round(im.width*scale))
        nh=max(1,round(im.height*scale))
        im=im.resize((nw,nh),Image.Resampling.LANCZOS)
        out.alpha_composite(im,((size[0]-nw)//2,(size[1]-nh)//2))
        return out

    if st.button("📦 完成裁切＋製作貼圖檔案＋一鍵打包", type="primary", use_container_width=True):
        try:
            _sheet = Image.open(BytesIO(st.session_state.generated_4x2_bytes)).convert("RGBA")
            _zipbuf = BytesIO()

            with zipfile.ZipFile(_zipbuf, "w", zipfile.ZIP_DEFLATED) as _zip:
                cropped_images = {}
                for i in range(8):
                    im = _v11b1_crop_cell(_sheet, i)
                    cropped_images[i+1] = im
                    _b = BytesIO()
                    im.save(_b, "PNG", optimize=True)
                    _zip.writestr(f"{i+1:02d}.png", _b.getvalue())

                main_im = _v11b1_special(cropped_images[int(main_no)], (240,240))
                tab_im = _v11b1_special(cropped_images[int(tab_no)], (96,74))

                _mb=BytesIO(); _tb=BytesIO()
                main_im.save(_mb,"PNG",optimize=True,dpi=(72,72))
                tab_im.save(_tb,"PNG",optimize=True,dpi=(72,72))
                _zip.writestr("main.png",_mb.getvalue())
                _zip.writestr("tab.png",_tb.getvalue())

            _zipbuf.seek(0)
            st.success(
                f"🎉 完成！MAIN={main_no}、TAB={tab_no}，"
                "已將 01～08＋main.png＋tab.png 打包。"
            )
            st.download_button(
                "⬇️ 下載完整 LINE 套件 ZIP",
                data=_zipbuf.getvalue(),
                file_name="LINE_Sticker_01-08_MAIN_TAB.zip",
                mime="application/zip",
                use_container_width=True,
                key="step11b1_download"
            )
        except Exception as e:
            st.error(f"打包失敗：{e}")
    st.caption("")
st.divider()
st.caption("")


# ─────────────────────────────────────────────
# LINE 貼圖官方網站
# ─────────────────────────────────────────────
st.markdown("""
<style>
div[data-testid="stLinkButton"] > a,
div[data-testid="stLinkButton"] > a:visited,
div[data-testid="stLinkButton"] > a:hover,
div[data-testid="stLinkButton"] > a:active {
    width: 100% !important;
    min-height: 52px !important;
    border-radius: 10px !important;
    font-size: 18px !important;
    font-weight: 800 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    background: #FF4B4B !important;
    background-color: #FF4B4B !important;
    background-image: none !important;
    color: #FFFFFF !important;
    border: 1px solid #FF4B4B !important;
    box-shadow: none !important;
    text-decoration: none !important;
    opacity: 1 !important;
}
div[data-testid="stLinkButton"] > a span,
div[data-testid="stLinkButton"] > a p {
    color: #FFFFFF !important;
    font-weight: 800 !important;
}
div[data-testid="stLinkButton"] > a:hover {
    background: #FF3333 !important;
    background-color: #FF3333 !important;
    border-color: #FF3333 !important;
    color: #FFFFFF !important;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# ============================================================
# V11｜STEP 02C-1 FIX4｜UI 主題交給 Streamlit 原生 Light/Dark
# 不在 Python 內硬覆蓋 App 背景；避免「文字已變白、背景仍是白色」。
# ============================================================
st.markdown("""
<style>
/* 只處理我們自己建立的舊版自訂元件；不接管整個 Streamlit App。 */
.v10-soft-box{
  background:var(--secondary-background-color, #fafafa) !important;
  border-color:var(--border-color, #e5e7eb) !important;
}

.v10-section-title,
.v10-subsection,
.v10-note{
  color:var(--text-color, inherit);
}

/* section 的彩色框線保留原本設計，不設定整頁背景。 */
</style>
""", unsafe_allow_html=True)



st.markdown('<div style="height: 20px;"></div>', unsafe_allow_html=True)
_link_col = st.columns([1, 2, 1])[1]
with _link_col:
    st.link_button(
        "🔗 連結 LINE 貼圖網頁",
        "https://creator.line.me/zh-hant/",
        use_container_width=True,
    )


# ============================================================
# PUBLIC STEP 02A｜個人設定匯出／匯入
# ============================================================
def _public02a_settings_panel():
    st.markdown(
        """
        <div style="
            max-width:760px;
            margin:28px auto 12px;
            padding:16px 20px;
            border-radius:14px;
            border:2px solid #4b5563;
            background:#151b26;
            text-align:center;
        ">
            <div style="font-size:24px;font-weight:800;color:#ffffff;">
                🔐 我的個人設定
            </div>
            <div style="font-size:15px;color:#cbd5e1;margin-top:6px;">
                自定義風格、詞語與人物／場景需求只屬於目前使用者。
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    export_data = json.dumps(
        _public02a_get_settings(),
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")

    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "📤 匯出我的設定",
            data=export_data,
            file_name="LINE貼圖工具_我的設定.json",
            mime="application/json",
            use_container_width=True,
            key="public02a_export_settings",
        )

    with c2:
        imported = st.file_uploader(
            "📥 匯入我的設定",
            type=["json"],
            key="public02a_import_settings",
            help="選擇之前匯出的 LINE貼圖工具_我的設定.json",
        )
        if imported is not None:
            try:
                raw = imported.getvalue()
                import_hash = hashlib.sha256(raw).hexdigest()
                last_hash = st.session_state.get("public02a_last_import_hash")

                # Streamlit keeps the uploader value across reruns.  Only process
                # a newly selected file; otherwise the same file would call
                # st.rerun() forever.
                if import_hash != last_hash:
                    data = json.loads(raw.decode("utf-8"))
                    _public02a_apply_settings(data)
                    st.session_state["public02a_last_import_hash"] = import_hash
                    st.session_state["public02a_import_success"] = True
                    st.rerun()
                elif st.session_state.get("public02a_import_success"):
                    st.success("✅ 我的設定已匯入")
            except Exception as exc:
                st.error(f"❌ 匯入失敗：{exc}")

# PUBLIC STEP 02A｜顯示個人設定匯出／匯入
_public02a_settings_panel()
