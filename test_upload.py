import requests

files = {'resume_file': ('test.txt', b'this is a test resume with some content', 'text/plain')}
data = {'job_role': 'Software Engineer'}

print("Sending request...")
try:
    response = requests.post("http://localhost:8000/api/v1/analyze/ats", files=files, data=data, timeout=30)
    print("Status:", response.status_code)
    print("Response:", response.text[:500])
except Exception as e:
    print("Error:", e)
