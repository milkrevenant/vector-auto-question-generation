import chromadb
from openai import OpenAI

DB_PATH  = "./sn_csat.db"
COL_NAME = "sn_csat_openai"

openai = OpenAI()
col    = chromadb.PersistentClient(path=DB_PATH).get_collection(COL_NAME)

while True:
    try:
        q = input("\n🔍  Query (exit = quit)> ")
    except EOFError:
        print("\n⏎  EOF received — exiting.")
        break

    if q.lower() == "exit":
        break

    q_vec = openai.embeddings.create(
        model="text-embedding-3-large",
        input=q
    ).data[0].embedding

    res = col.query(query_embeddings=[q_vec], n_results=3)
    for sim, doc_id in zip(res["distances"][0], res["ids"][0]):
        print(f" • {doc_id}   sim={sim:.4f}")