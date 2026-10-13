"""文章生成AIの呼び出し。無料で使えるものから順に試す。

- github   : GitHub Models（GitHub Actions の GITHUB_TOKEN で無料・登録不要。1日の回数制限あり）
- gemini   : Google Gemini API 無料枠（GEMINI_API_KEY が必要。登録無料・カード不要）
- anthropic: Claude（ANTHROPIC_API_KEY が必要。有料だが品質が最も高く、Web検索も使える）
"""
import json
import os
import urllib.error
import urllib.request

OPENAI_COMPAT = {
    "github": ("https://models.github.ai/inference/chat/completions", "GITHUB_TOKEN"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "GEMINI_API_KEY"),
}
KEY_ENV = {"github": "GITHUB_TOKEN", "gemini": "GEMINI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}


class LLMError(RuntimeError):
    pass


def available(providers):
    """認証情報が設定されているプロバイダだけを順番どおりに返す。"""
    return [p for p in providers if os.environ.get(KEY_ENV[p["name"]])]


def _openai_compat(p, system, prompt):
    url, env = OPENAI_COMPAT[p["name"]]
    req = urllib.request.Request(
        url,
        data=json.dumps({
            "model": p["model"],
            "max_tokens": p.get("max_tokens", 4000),
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        }).encode(),
        headers={"Authorization": f"Bearer {os.environ[env]}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        raise LLMError(f"{p['name']} HTTP {e.code}: {e.read()[:300].decode(errors='replace')}") from e
    except urllib.error.URLError as e:
        raise LLMError(f"{p['name']} 接続エラー: {e}") from e
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as e:
        raise LLMError(f"{p['name']} 応答形式が不正: {str(data)[:300]}") from e


def _anthropic(p, system, prompt, use_search):
    import anthropic

    client = anthropic.Anthropic()
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 5}] if use_search else []
    messages = [{"role": "user", "content": prompt}]
    try:
        for _ in range(5):  # web検索の pause_turn に対応
            with client.beta.messages.stream(
                model=p["model"],
                max_tokens=p.get("max_tokens", 32000),
                system=system,
                messages=messages,
                tools=tools,
                output_config={"effort": p.get("effort", "medium")},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            ) as stream:
                resp = stream.get_final_message()
            if resp.stop_reason != "pause_turn":
                break
            messages = [messages[0], {"role": "assistant", "content": resp.content}]
    except anthropic.APIError as e:
        raise LLMError(f"anthropic: {e}") from e
    if resp.stop_reason == "refusal":
        raise LLMError(f"anthropic refused: {resp.stop_details}")
    # 最後のツール結果より後の text ブロックだけを本文として使う
    last_tool = max((i for i, b in enumerate(resp.content) if b.type.endswith("tool_result")), default=-1)
    return "".join(b.text for b in resp.content[last_tool + 1:] if b.type == "text").strip()


def complete(providers, system, prompt, use_search=False):
    """使えるプロバイダを順に試し、最初に成功した結果と使ったプロバイダを返す。"""
    errors = []
    for p in available(providers):
        try:
            if p["name"] == "anthropic":
                return _anthropic(p, system, prompt, use_search), p
            return _openai_compat(p, system, prompt), p
        except LLMError as e:
            print(f"  {e} → 次のプロバイダを試します")
            errors.append(str(e))
    raise LLMError("使えるAIがありません: " + (" / ".join(errors) or "APIキー・トークンが未設定です"))
