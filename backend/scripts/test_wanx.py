"""Quick wanx API smoke test."""
from app.config import settings
import httpx

base = (settings.DASHSCOPE_NATIVE_API_BASE or "https://dashscope.aliyuncs.com/api/v1").rstrip("/")
model = (settings.IMAGE_MODEL or "wanx-v1").strip()
print("KEY set:", bool(settings.DASHSCOPE_API_KEY.strip()))
print("MODEL:", model)
print("BASE:", base)

url = f"{base}/services/aigc/text2image/image-synthesis"
body = {
    "model": model,
    "input": {"prompt": "simple blue circle on white background"},
    "parameters": {"style": "<auto>", "size": "1024*1024", "n": 1},
}
headers = {
    "Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}",
    "Content-Type": "application/json",
    "X-DashScope-Async": "enable",
}
r = httpx.post(url, headers=headers, json=body, timeout=30)
print("create status:", r.status_code)
print(r.text[:1500])
