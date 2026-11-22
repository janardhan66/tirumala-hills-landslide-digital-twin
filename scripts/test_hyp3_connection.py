import os
from dotenv import load_dotenv
from hyp3_sdk import HyP3

# Load credentials from .env
load_dotenv()

username = os.getenv("HYP3_USERNAME")
password = os.getenv("HYP3_PASSWORD")

if not username or not password:
    raise ValueError("HyP3 credentials are missing from .env")

# Connect to ASF HyP3
hyp3 = HyP3(
    username=username,
    password=password
)

# Retrieve existing jobs to test authentication
jobs = hyp3.find_jobs()

print("Successfully connected to ASF HyP3!")
print("Existing jobs:", len(jobs))
