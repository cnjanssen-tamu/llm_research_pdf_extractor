from dotenv import load_dotenv
import google.generativeai as genai
import os
from django.conf import settings



genai.configure(api_key=settings.GEMINI_API_KEY)
genai.configure(transport='grpc')

def list_models():
    for i, m in zip(range(5), genai.list_models()):
        print(f"Name: {m.name} Description: {m.description} support: {m.supported_generation_methods}")

if __name__ == "__main__":
    list_models()