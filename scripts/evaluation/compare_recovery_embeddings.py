#!/usr/bin/env python3
"""Isolated source-recall comparison on identical parsed documents and queries.

Run inside the API container. Does not mutate the database/settings and never
sends documents to an external service. Output contains public test questions,
source filenames and aggregate metrics, not document text or credentials.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,"/app")
from app.document_processing import structured_chunks
from app.config import get_base_directory
from sentence_transformers import SentenceTransformer
import numpy as np


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--folder",type=Path,required=True)
    p.add_argument("--cases",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    texts=[]; filenames=[]; digest=hashlib.sha256()
    for path in sorted(a.folder.glob("*.md")):
        raw=path.read_text(); digest.update(raw.encode())
        for chunk in structured_chunks(raw,target_chars=900):
            if chunk.metadata["contentTypes"]==["heading"]:
                continue
            texts.append(chunk.text); filenames.append(path.name)
    cases=json.loads(a.cases.read_text())
    report={"corpusSha256":digest.hexdigest(),"chunks":len(texts),"models":[]}
    for name in ("all-MiniLM-L6-v2","mixedbread-ai/mxbai-embed-large-v1"):
        kwargs={"device":"cuda","local_files_only":True,"trust_remote_code":False,
                "model_kwargs":{"use_safetensors":True}}
        if "mixedbread" in name:
            kwargs.update(cache_folder=str(get_base_directory()/"model_cache"),revision="b33106f585b9ce46904ad7443a3b52b7a63e231c")
        model=SentenceTransformer(name,**kwargs)
        started=time.monotonic()
        docs=model.encode(texts,batch_size=32,normalize_embeddings=True,show_progress_bar=False)
        queries=[c["question"] for c in cases]
        if "mixedbread" in name:
            queries=["Represent this sentence for searching relevant passages: "+q for q in queries]
        qv=model.encode(queries,normalize_embeddings=True,show_progress_bar=False)
        results=[]
        for case,vector in zip(cases,qv):
            scores=docs@vector
            order=np.argsort(-scores)
            ranks=[i+1 for i,index in enumerate(order) if filenames[index] in case["sources"]]
            rank=min(ranks) if ranks else None
            results.append({"question":case["question"],"firstRelevantRank":rank,
                            "top5":[filenames[i] for i in order[:5]]})
        item={"model":name,"elapsedSeconds":round(time.monotonic()-started,2),
              "sourceRecallAt10":sum(r["firstRelevantRank"] is not None and r["firstRelevantRank"]<=10 for r in results)/len(results),
              "sourceRecallAt64":sum(r["firstRelevantRank"] is not None and r["firstRelevantRank"]<=64 for r in results)/len(results),
              "mrr":sum(1/r["firstRelevantRank"] if r["firstRelevantRank"] else 0 for r in results)/len(results),"results":results}
        report["models"].append(item)
        a.output.write_text(json.dumps(report,indent=2)+"\n")
        print(json.dumps({k:v for k,v in item.items() if k!="results"}),flush=True)
        del model

if __name__=="__main__":
    main()
