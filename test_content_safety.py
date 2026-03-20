import os
from azure.ai.contentsafety import ContentSafetyClient
from azure.core.credentials import AzureKeyCredential
from azure.ai.contentsafety.models import AnalyzeTextOptions

endpoint = os.getenv("AZURE_CONTENT_SAFETY_ENDPOINT")
key = os.getenv("AZURE_CONTENT_SAFETY_KEY")

print("🔄 Connecting to Azure Content Safety...")

client = ContentSafetyClient(endpoint, AzureKeyCredential(key))

text_to_check = "I will destroy everything and hurt people."

try:
    response = client.analyze_text(
        AnalyzeTextOptions(text=text_to_check)
    )

    print("\n✅ Content Safety Response:\n")

    for category in response.categories_analysis:
        print(f"{category.category}: severity {category.severity}")

except Exception as e:
    print("❌ Error:", e)