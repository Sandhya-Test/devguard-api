import os
from azure.cosmos import CosmosClient, exceptions
from dotenv import load_dotenv

load_dotenv(override=True)

# Read environment variables
COSMOS_URI = os.getenv("COSMOS_URI")
COSMOS_KEY = os.getenv("COSMOS_KEY")
DATABASE_NAME = os.getenv("COSMOS_DATABASE", "devguard")
CONTAINER_NAME = os.getenv("COSMOS_CONTAINER", "audit_logs")

if not COSMOS_URI:
    print("❌ COSMOS_URI not found")
    exit()

if not COSMOS_KEY:
    print("❌ COSMOS_KEY not found")
    exit()

try:
    print("🔄 Connecting to Cosmos DB...")
    client = CosmosClient(COSMOS_URI, COSMOS_KEY)
    database = client.get_database_client(DATABASE_NAME)
    container = database.get_container_client(CONTAINER_NAME)

    # Try simple read
    list(container.read_all_items(max_item_count=1))

    print("✅ Cosmos DB connection successful!")
    print("Database:", DATABASE_NAME)
    print("Container:", CONTAINER_NAME)

except exceptions.CosmosHttpResponseError as e:
    print("❌ Cosmos HTTP Error:", e.message)

except Exception as e:
    print("❌ General Error:", str(e))
