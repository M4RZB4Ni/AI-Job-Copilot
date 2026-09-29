import requests

job_text = """paste your 

posting here"""

response = requests.post(
    "http://127.0.0.1:8000/analyze",
    json={"text": job_text}
)

print("Status code:", response.status_code)
print("Raw response:", response.text)