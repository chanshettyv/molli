"""
Throwaway spike: upsert one fake vector into Vertex AI Vector Search
and retrieve it by nearest-neighbor search.

Usage:
    uv run python scripts/spikes/vector_search_test.py

Prerequisites:
    - VECTOR_INDEX_ID and VECTOR_INDEX_ENDPOINT in .env
    - gcloud auth application-default login
    - Index deployed to endpoint (molli_knowledge_stream)
"""

import os

from dotenv import load_dotenv
from google.cloud import aiplatform_v1

load_dotenv()

PROJECT_ID = os.environ["GCP_PROJECT_ID"]
REGION = "us-central1"
INDEX_ENDPOINT_ID = os.environ["VECTOR_INDEX_ENDPOINT"]
DEPLOYED_INDEX_ID = "molli_knowledge_stream"

# One fake 768-dimension vector (text-embedding-004 output shape)
FAKE_VECTOR = [0.01] * 768
FAKE_DATAPOINT_ID = "test-doc-001"


def main():
    endpoint = f"projects/{PROJECT_ID}/locations/{REGION}/indexEndpoints/{INDEX_ENDPOINT_ID}"

    # Upsert
    index_id = os.environ["VECTOR_INDEX_ID"]
    index_name = f"projects/{PROJECT_ID}/locations/{REGION}/indexes/{index_id}"
    index_client = aiplatform_v1.IndexServiceClient(
        client_options={"api_endpoint": f"{REGION}-aiplatform.googleapis.com"}
    )
    upsert_request = aiplatform_v1.UpsertDatapointsRequest(
        index=index_name,
        datapoints=[
            aiplatform_v1.IndexDatapoint(
                datapoint_id=FAKE_DATAPOINT_ID,
                feature_vector=FAKE_VECTOR,
            )
        ],
    )
    index_client.upsert_datapoints(request=upsert_request)
    print(f"Upserted datapoint: {FAKE_DATAPOINT_ID}")

    # Query
    query_client = aiplatform_v1.MatchServiceClient(
        client_options={"api_endpoint": "163164439.us-central1-719635778769.vdb.vertexai.goog"}
    )
    query_request = aiplatform_v1.FindNeighborsRequest(
        index_endpoint=endpoint,
        deployed_index_id=DEPLOYED_INDEX_ID,
        queries=[
            aiplatform_v1.FindNeighborsRequest.Query(
                datapoint=aiplatform_v1.IndexDatapoint(feature_vector=FAKE_VECTOR),
                neighbor_count=3,
            )
        ],
    )
    response = query_client.find_neighbors(request=query_request)
    print("Nearest neighbors:")
    for neighbor in response.nearest_neighbors[0].neighbors:
        print(f"  id={neighbor.datapoint.datapoint_id}  distance={neighbor.distance}")


if __name__ == "__main__":
    main()
